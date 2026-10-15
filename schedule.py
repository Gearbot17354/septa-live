"""Regional Rail timetable from a GTFS zip. No Home Assistant and no network."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import zipfile
from datetime import date, datetime
from pathlib import Path

try:
    from .dynamic import parse_valid_until, select_schedule
except ImportError:  # loaded by file path in unit tests
    import importlib.util

    _spec = importlib.util.spec_from_file_location("septa_dynamic_sched", Path(__file__).with_name("dynamic.py"))
    _dynamic = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_dynamic)
    parse_valid_until = _dynamic.parse_valid_until
    select_schedule = _dynamic.select_schedule

MAX_BYTES = 50 * 1024 * 1024
MIN_STATION_RATIO = 0.5
REFRESH_WITHIN_DAYS = 7
NEAR_EXPIRY_DAYS = 2

_WANTED = {
    "stops.txt": "stops",
    "trips.txt": "trips",
    "stop_times.txt": "stop_times",
    "calendar.txt": "calendar",
    "calendar_dates.txt": "calendar_dates",
    "feed_info.txt": "feed_info",
    "shapes.txt": "shapes",
    "routes.txt": "routes",
}


def _csv(text: str) -> list[dict]:
    if not text:
        return []
    return list(csv.DictReader(io.StringIO(text)))


def _day_mask(row: dict) -> int:
    bits = {
        "sunday": 1,
        "monday": 2,
        "tuesday": 4,
        "wednesday": 8,
        "thursday": 16,
        "friday": 32,
        "saturday": 64,
    }
    mask = 0
    for name, bit in bits.items():
        if str(row.get(name) or "0").strip() in {"1", "true", "yes"}:
            mask |= bit
    return mask or 127


def _yyyymmdd(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[:8] if len(digits) >= 8 else ""


def _texts(blob: bytes) -> dict[str, str]:
    found: dict[str, str] = {}

    def read(archive: zipfile.ZipFile) -> None:
        for name in archive.namelist():
            base = name.rsplit("/", 1)[-1]
            key = _WANTED.get(base)
            if key and key not in found:
                found[key] = archive.read(name).decode("utf-8", "replace")

    with zipfile.ZipFile(io.BytesIO(blob)) as outer:
        inner = next((name for name in outer.namelist() if name.endswith("google_rail.zip")), "")
        if inner:
            with zipfile.ZipFile(io.BytesIO(outer.read(inner))) as rail:
                read(rail)
        else:
            read(outer)
    return found


def build_schedule(zip_bytes: bytes) -> dict:
    """GTFS zip (or gtfs_public.zip containing google_rail.zip) → rail-schedule.json shape."""
    if not isinstance(zip_bytes, (bytes, bytearray)) or not zip_bytes:
        raise ValueError("parse")
    if len(zip_bytes) > MAX_BYTES:
        raise ValueError("too_large")
    try:
        files = _texts(bytes(zip_bytes))
    except zipfile.BadZipFile as err:
        raise ValueError("parse") from err
    if "stops" not in files or "stop_times" not in files or "trips" not in files:
        raise ValueError("parse")
    stops = {row.get("stop_id"): row.get("stop_name") or row.get("stop_id") for row in _csv(files.get("stops") or "")}
    services = {row.get("service_id"): _day_mask(row) for row in _csv(files.get("calendar") or "")}
    trips = {row.get("trip_id"): row for row in _csv(files.get("trips") or "")}
    stations: dict[str, dict] = {}
    for row in _csv(files.get("stop_times") or ""):
        trip = trips.get(row.get("trip_id") or "")
        if not trip:
            continue
        name = stops.get(row.get("stop_id") or "")
        clock = str(row.get("arrival_time") or row.get("departure_time") or "")
        parts = clock.split(":")
        if not name or len(parts) < 2:
            continue
        try:
            hour, minute = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        extra = hour // 24
        hour %= 24
        stamp = f"{hour:02d}:{minute:02d}"
        train = str(trip.get("trip_short_name") or trip.get("trip_id") or "").strip()
        direction = "N" if str(trip.get("direction_id") or "0").strip() == "1" else "S"
        pack = stations.setdefault(str(name), {"N": [], "S": []})
        pack[direction].append(
            {
                "t": stamp,
                "d": str(trip.get("trip_headsign") or ""),
                "n": train,
                "line": str(trip.get("route_id") or ""),
                "days": services.get(trip.get("service_id") or "", 127),
                "seq": int(row.get("stop_sequence") or 0) + extra * 10000,
            }
        )
    dates: list[str] = []
    for row in _csv(files.get("calendar") or ""):
        stamp = _yyyymmdd(row.get("end_date"))
        if stamp:
            dates.append(stamp)
    for row in _csv(files.get("calendar_dates") or ""):
        if str(row.get("exception_type") or "").strip() != "1":
            continue
        stamp = _yyyymmdd(row.get("date"))
        if stamp:
            dates.append(stamp)
    info = _csv(files.get("feed_info") or "")
    feed = ""
    if info:
        feed = str(info[0].get("feed_version") or "").strip()
        if not dates:
            stamp = _yyyymmdd(info[0].get("feed_end_date"))
            if stamp:
                dates.append(stamp)
    if not feed:
        feed = hashlib.sha256(bytes(zip_bytes)).hexdigest()[:16]
    return {"feed": feed, "validUntil": max(dates) if dates else "", "stations": stations}


def read_schedule_file(path: Path | str) -> dict | None:
    """Cached download, or None when the file is missing or corrupt."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    schedule = raw.get("schedule") if isinstance(raw.get("schedule"), dict) else raw
    if isinstance(schedule, dict) and isinstance(schedule.get("stations"), dict) and schedule.get("stations"):
        return schedule
    return None


def write_schedule_file(path: Path | str, payload: dict) -> None:
    """Atomic replace. Callers pass a storage path, never the package file."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, dest)


def needs_download(schedule: dict | None, today: date, within_days: int = REFRESH_WITHIN_DAYS, etag_changed: bool = False, force: bool = False) -> bool:
    if force or etag_changed:
        return True
    until = parse_valid_until(schedule)
    if until is None:
        return True
    return (until - today).days <= int(within_days)


def acceptable(new: dict | None, current: dict | None, today: date, ratio: float = MIN_STATION_RATIO) -> tuple[bool, str]:
    stations = (new or {}).get("stations") if isinstance(new, dict) else None
    if not isinstance(stations, dict) or not stations:
        return False, "parse"
    until = parse_valid_until(new)
    if until is None or until < today:
        return False, "expired"
    have = (current or {}).get("stations") if isinstance(current, dict) else None
    if isinstance(have, dict) and have and len(stations) < float(ratio) * len(have):
        return False, "too_small"
    return True, ""


class ScheduleBook:
    """Which timetable is active, and whether a refresh should replace it."""

    def __init__(self) -> None:
        self.schedule: dict = {"stations": {}}
        self.origin = "missing"
        self.expired = True
        self.last_check = None
        self.last_success = None
        self.last_error = None
        self.etag = None
        self.modified = None

    def load(self, bundled: dict | None, cached: dict | None, today: date) -> None:
        chosen, source = select_schedule(bundled, cached, today)
        self.schedule = chosen if isinstance(chosen, dict) else {"stations": {}}
        if source == "downloaded":
            self.origin = "downloaded"
            self.expired = False
        elif source == "bundled":
            self.origin = "bundled"
            self.expired = False
        elif source == "expired":
            self.origin = "downloaded" if chosen is cached else "bundled"
            self.expired = True
        else:
            self.origin = "missing"
            self.expired = True

    def timetable_source(self) -> str:
        if self.expired:
            return "expired"
        if self.origin in {"downloaded", "bundled"} and (self.schedule or {}).get("stations"):
            return self.origin
        return "missing"

    def should_fetch(self, today: date, within_days: int = REFRESH_WITHIN_DAYS, etag_changed: bool = False, force: bool = False) -> bool:
        return needs_download(self.schedule, today, within_days, etag_changed, force)

    def note_not_modified(self, now) -> None:
        self.last_check = now

    def fail(self, now, error: str) -> None:
        self.last_check = now
        self.last_error = str(error or "download")

    def accept(self, new: dict, now, today: date) -> bool:
        self.last_check = now
        ok, reason = acceptable(new, self.schedule, today)
        if not ok:
            self.last_error = reason
            return False
        self.schedule = new
        self.origin = "downloaded"
        self.expired = False
        self.last_success = now
        self.last_error = None
        return True

    def needs_repair(self, today: date, near_days: int = NEAR_EXPIRY_DAYS) -> bool:
        if not self.last_error:
            return False
        until = parse_valid_until(self.schedule)
        if until is None:
            return True
        return (until - today).days < int(near_days)

    def sensor(self, today: date) -> dict:
        until = parse_valid_until(self.schedule)
        source = self.origin if self.origin in {"bundled", "downloaded"} else "missing"
        return {
            "state": None if until is None else until.isoformat(),
            "feed": (self.schedule or {}).get("feed"),
            "source": source,
            "last_check": self.last_check,
            "last_success": self.last_success,
            "last_error": self.last_error,
            "days_remaining": None if until is None else (until - today).days,
        }


def stamp(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
