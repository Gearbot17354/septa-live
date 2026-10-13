"""Origin-to-destination trips. No Home Assistant imports."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

# NextToArrive rejects some names the rest of SEPTA uses.
_NTA_ALIASES = {
    "gray 30th street": "30th Street Station",
    "30th street gray": "30th Street Station",
    "30th street": "30th Street Station",
    "william h gray iii 30th street": "30th Street Station",
    "9th street": "9th St",
    "ninth street": "9th St",
    "fern rock": "Fern Rock Transportation Center",
    "fern rock tc": "Fern Rock Transportation Center",
    "norristown": "Norristown Transportation Center",
    "norristown tc": "Norristown Transportation Center",
    "jefferson": "Jefferson Station",
    "market east": "Jefferson Station",
    "suburban": "Suburban Station",
    "penn medicine": "Penn Medicine Station",
    "temple": "Temple University",
    "trenton": "Trenton Transit Center",
}


def station_key(name: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower())
    text = re.sub(r"\bstation\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def nta_station(name: object) -> str:
    """Name NextToArrive will accept. Unknown names are sent through unchanged."""
    raw = str(name or "").strip()
    key = station_key(raw)
    if key in _NTA_ALIASES:
        return _NTA_ALIASES[key]
    return raw


def clean_trips(raw: object) -> list[dict]:
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.splitlines() if part.strip()]
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str) and ">" in item:
            origin, _, dest = item.partition(">")
            item = {"origin": origin.strip(), "destination": dest.strip()}
        if not isinstance(item, dict):
            continue
        origin = str(item.get("origin") or "").strip()[:80]
        dest = str(item.get("destination") or "").strip()[:80]
        if not origin or not dest or station_key(origin) == station_key(dest):
            continue
        tid = re.sub(r"[^a-z0-9]", "", str(item.get("id") or "").lower())[:12]
        if not tid:
            tid = re.sub(r"[^a-z0-9]", "", station_key(origin) + station_key(dest))[:12]
        if not tid or tid in seen:
            continue
        seen.add(tid)
        try:
            count = int(item.get("count") if item.get("count") not in (None, "") else 4)
        except (TypeError, ValueError):
            count = 4
        count = min(10, max(1, count))
        label = str(item.get("label") or "").strip()[:40]
        out.append(
            {
                "id": tid,
                "origin": origin,
                "destination": dest,
                "count": count,
                "label": label,
            }
        )
        if len(out) >= 8:
            break
    return out


def trip_ids(entry_id: str, trip_id: str) -> tuple[str, str]:
    """Unique id and entity id. Neither includes the station names."""
    key = re.sub(r"[^a-z0-9]", "", str(trip_id or "").lower())[:12]
    return f"{entry_id}_trip_{key}", f"sensor.septa_trip_{key}"


def parse_delay_min(text: object) -> int | None:
    raw = str(text or "").strip().lower()
    if not raw:
        return None
    if "on time" in raw or raw in {"ontime", "0"}:
        return 0
    match = re.search(r"-?\d+", raw)
    if not match:
        return None
    return int(match.group(0))


def _clock(text: object, now: datetime) -> datetime | None:
    raw = str(text or "").strip().upper().replace(" ", "")
    match = re.match(r"^(\d{1,2}):(\d{2})(AM|PM)?$", raw)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    ap = match.group(3)
    if ap == "PM" and hour < 12:
        hour += 12
    if ap == "AM" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    base = now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)
    when = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if when < base - timedelta(hours=3):
        when += timedelta(days=1)
    return when


def _iso(when: datetime | None) -> str | None:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=NY)
    return when.astimezone(NY).isoformat()


def _direct(item: dict) -> bool:
    flag = str(item.get("isdirect") if item.get("isdirect") is not None else "").strip().lower()
    if flag in {"true", "y", "yes", "1"}:
        return True
    if flag in {"false", "n", "no", "0"}:
        return False
    term = str(item.get("term_train") or "").strip()
    orig = str(item.get("orig_train") or "").strip()
    return not term or term == orig


def _connection(item: dict, now: datetime) -> dict | None:
    if _direct(item):
        return None
    depart = _clock(item.get("term_depart_time") or item.get("term_departure_time"), now)
    station = str(item.get("Connection") or item.get("connection") or item.get("term_station") or "").strip()
    return {
        "station": station,
        "train": str(item.get("term_train") or "").strip(),
        "line": str(item.get("term_line") or "").strip(),
        "depart": _iso(depart),
    }


def parse_next_to_arrive(raw: object, now: datetime, limit: int = 4) -> tuple[list[dict], str | None]:
    """Turn a NextToArrive payload into trip rows. A non-list is a rejection."""
    if isinstance(raw, list):
        rows = [item for item in raw if isinstance(item, dict)]
    else:
        message = ""
        if isinstance(raw, dict):
            message = str(raw.get("error") or raw.get("message") or raw.get("Error") or "").strip()
        elif isinstance(raw, str):
            message = raw.strip()
        return [], message or "NextToArrive rejected the station pair"
    out: list[dict] = []
    for item in rows:
        delay = parse_delay_min(item.get("orig_delay"))
        if delay is None:
            delay = 0
        depart = _clock(item.get("orig_departure_time"), now)
        arrive = _clock(item.get("orig_arrival_time"), now)
        depart_est = None if depart is None else depart + timedelta(minutes=delay)
        arrive_est = None if arrive is None else arrive + timedelta(minutes=delay)
        minutes = None
        if depart_est is not None:
            minutes = int(round((depart_est - now.astimezone(depart_est.tzinfo)).total_seconds() / 60))
        if minutes is not None and minutes < 0:
            continue
        out.append(
            {
                "train": str(item.get("orig_train") or "").strip(),
                "line": str(item.get("orig_line") or "").strip(),
                "depart_sched": _iso(depart),
                "depart_est": _iso(depart_est),
                "arrive_sched": _iso(arrive),
                "arrive_est": _iso(arrive_est),
                "delay_min": delay,
                "minutes": minutes,
                "direct": _direct(item),
                "connection": _connection(item, now),
            }
        )
        if len(out) >= max(1, limit):
            break
    return out, None


def _weekday_bit(day) -> int:
    return 1 << ((day.weekday() + 1) % 7)


def _hhmm(day, clock: str):
    try:
        hour, minute = str(clock).split(":")
        return datetime(day.year, day.month, day.day, int(hour), int(minute), tzinfo=NY)
    except (TypeError, ValueError):
        return None


def _station_rows(schedule: dict | None, name: str) -> list[tuple[str, dict]]:
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    if not isinstance(stations, dict):
        return []
    want = station_key(name)
    pack = None
    for key, value in stations.items():
        if station_key(key) == want:
            pack = value
            break
    if pack is None:
        for key, value in stations.items():
            got = station_key(key)
            if want and (want in got or got in want):
                pack = value
                break
    if not isinstance(pack, dict):
        return []
    found: list[tuple[str, dict]] = []
    for direction in ("N", "S"):
        rows = pack.get(direction) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                found.append((direction, row))
    return found


def timetable_trips(
    schedule: dict | None,
    origin: str,
    destination: str,
    now: datetime,
    limit: int = 4,
    line_names: dict | None = None,
) -> list[dict]:
    """Direct trains that stop at both stations after now. delay_min stays null."""
    names = line_names or {}
    by_origin: dict[tuple, datetime] = {}
    origin_line: dict[tuple, str] = {}
    origin_train: dict[tuple, str] = {}
    base = now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)
    for offset in (0, 1):
        day = (base + timedelta(days=offset)).date()
        bit = _weekday_bit(day)
        for _direction, row in _station_rows(schedule, origin):
            days = int(row.get("days") or 0)
            if days and not (days & bit):
                continue
            train = str(row.get("n") or "").strip()
            when = _hhmm(day, str(row.get("t") or ""))
            if not train or when is None or when <= base:
                continue
            key = (day.isoformat(), train)
            if key not in by_origin or when < by_origin[key]:
                by_origin[key] = when
                code = str(row.get("line") or "")
                origin_line[key] = str(names.get(code, code))
                origin_train[key] = train
    arrivals: dict[tuple, datetime] = {}
    for offset in (0, 1):
        day = (base + timedelta(days=offset)).date()
        bit = _weekday_bit(day)
        for _direction, row in _station_rows(schedule, destination):
            days = int(row.get("days") or 0)
            if days and not (days & bit):
                continue
            train = str(row.get("n") or "").strip()
            when = _hhmm(day, str(row.get("t") or ""))
            if not train or when is None:
                continue
            key = (day.isoformat(), train)
            if key in by_origin and when > by_origin[key]:
                if key not in arrivals or when < arrivals[key]:
                    arrivals[key] = when
    ordered = sorted((by_origin[key], key) for key in arrivals)
    out: list[dict] = []
    for depart, key in ordered:
        arrive = arrivals[key]
        minutes = int(round((depart - base).total_seconds() / 60))
        if minutes < 0:
            continue
        out.append(
            {
                "train": origin_train[key],
                "line": origin_line[key],
                "depart_sched": _iso(depart),
                "depart_est": _iso(depart),
                "arrive_sched": _iso(arrive),
                "arrive_est": _iso(arrive),
                "delay_min": None,
                "minutes": minutes,
                "direct": True,
                "connection": None,
            }
        )
        if len(out) >= max(1, limit):
            break
    return out
