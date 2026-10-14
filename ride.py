"""Phone-to-train matching. No Home Assistant imports."""

from __future__ import annotations

import json
import logging
import math
import re
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_LOGGER = logging.getLogger(__name__)
_OFF_LOOP_LOGGED = False

EARTH_M = 6_371_000.0
METERS_PER_DEG_LAT = 111_320.0
NY = ZoneInfo("America/New_York")
CORRIDOR_M = 300.0
CORRIDOR_REACH_M = 3500.0
FAST_MPH = 15.0
STALE_POLLS = 3
_CENTER = ("suburban", "jefferson", "30th", "gray 30th", "temple university")
try:
    from .const import (
        APART_FIXES,
        APART_M,
        ARRIVAL_RADIUS_M,
        MAX_RIDE_SECONDS,
        REBOARD_COOLDOWN_S,
        SLOW_MPH,
        SLOW_SECONDS,
        SPEED_CONFIRM_FIXES,
        SPEED_CONFIRM_MPH,
        SPEED_MATCH_M,
        ESTIMATE_SLACK_M,
        FRESH_TRAINVIEW_S,
        TERMINAL_GRACE_S,
    )
except ImportError:
    ARRIVAL_RADIUS_M = 250
    SLOW_MPH = 5
    SLOW_SECONDS = 180
    APART_M = 600
    APART_FIXES = 2
    MAX_RIDE_SECONDS = 3 * 3600
    REBOARD_COOLDOWN_S = 600
    TERMINAL_GRACE_S = 120
    FRESH_TRAINVIEW_S = 60
    SPEED_CONFIRM_MPH = 20
    SPEED_CONFIRM_FIXES = 2
    SPEED_MATCH_M = 1500
    ESTIMATE_SLACK_M = 500


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_M * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _along_line(lat: float, lon: float, points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Return along-track meters and cross-track meters for the nearest segment."""
    best = None
    walked = 0.0
    for index in range(len(points) - 1):
        lat1, lon1 = points[index]
        lat2, lon2 = points[index + 1]
        scale = METERS_PER_DEG_LAT * max(0.2, math.cos(math.radians(lat1)))
        bx = (lon2 - lon1) * scale
        by = (lat2 - lat1) * METERS_PER_DEG_LAT
        seg = math.hypot(bx, by)
        if seg < 1:
            continue
        px = (lon - lon1) * scale
        py = (lat - lat1) * METERS_PER_DEG_LAT
        t = max(0.0, min(1.0, (px * bx + py * by) / (seg * seg)))
        cross = math.hypot(px - bx * t, py - by * t)
        along = walked + seg * t
        if best is None or cross < best[1]:
            best = (along, cross)
        walked += seg
    return best


def write_state_on_loop(hass, write) -> None:
    """Write entity state on Home Assistant's event loop, even if a dispatcher ran us in a thread."""
    global _OFF_LOOP_LOGGED
    loop_id = getattr(hass, "loop_thread_id", None)
    if loop_id is not None and loop_id != threading.get_ident():
        if not _OFF_LOOP_LOGGED:
            _OFF_LOOP_LOGGED = True
            _LOGGER.debug("SEPTA state write left the event loop\n%s", "".join(traceback.format_stack(limit=8)))
        hass.loop.call_soon_threadsafe(write)
        return
    write()


def replay_fixes(samples: list[dict], **kwargs) -> dict:
    """Replay fixes on a new matcher. Does not touch any live matcher."""
    hint = kwargs.pop("expected_train", None)
    matcher = RideMatcher(**kwargs)
    if hint:
        matcher.set_expected(hint if isinstance(hint, dict) else {"train": str(hint)})
    steps = []
    events = []
    for sample in samples:
        sample_fix = sample["fix"]
        rows = sample.get("trains") or []
        trains_ts = sample.get("trains_ts", sample_fix.ts)
        event = matcher.update(sample_fix, rows, trains_ts, now=sample.get("now", sample_fix.ts))
        if event is not None:
            events.append(
                {
                    "kind": event.kind,
                    "train": event.payload.get("train"),
                    "reason": event.payload.get("reason"),
                }
            )
        riding = matcher.riding_train.trainno if matcher.riding_train else None
        steps.append(
            {
                "reason": matcher.last_reason,
                "riding": matcher.riding,
                "train": riding,
                "speed_source": matcher.speed_source,
                "phone_speed_mph": matcher.phone_speed_mph,
                "match_count": matcher.match_count,
                "position_source": matcher.position_source,
                "confidence": matcher.confidence,
            }
        )
    return {
        "events": events,
        "steps": steps,
        "riding": matcher.riding,
        "train": matcher.riding_train.trainno if matcher.riding_train else None,
        "position_source": matcher.position_source,
        "confidence": matcher.confidence,
        "candidates": list(matcher.candidates),
        "accepted_fix_count": matcher.accepted_fix_count,
        "skipped_fix_count": matcher.skipped_fix_count,
    }


def _float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _consist(raw: object) -> list[str]:
    text = str(raw or "").strip()
    if not text or text.upper() == "TBD":
        return []
    return [part.strip() for part in text.split(",") if part.strip() and part.strip().upper() != "TBD"]


@dataclass
class Train:
    trainno: str
    lat: float
    lon: float
    heading: float | None
    dest: str = ""
    line: str = ""
    service: str = ""
    currentstop: str = ""
    nextstop: str = ""
    late: int = 0
    consist: list[str] = field(default_factory=list)
    track: str = ""


@dataclass
class Fix:
    lat: float
    lon: float
    acc_m: float | None
    speed_mps: float | None
    course: float | None
    ts: float


@dataclass
class RideEvent:
    kind: str
    payload: dict


def parse_trainview(rows: object) -> list[Train]:
    if not isinstance(rows, list):
        return []
    out: list[Train] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        lat = _float(item.get("lat"))
        lon = _float(item.get("lon"))
        if lat is None or lon is None:
            continue
        late = item.get("late")
        try:
            late_min = int(late) if late not in (None, "") else 0
        except (TypeError, ValueError):
            late_min = 0
        out.append(
            Train(
                trainno=str(item.get("trainno") or "").strip(),
                lat=lat,
                lon=lon,
                heading=_float(item.get("heading")),
                dest=str(item.get("dest") or ""),
                line=str(item.get("line") or ""),
                service=str(item.get("service") or ""),
                currentstop=str(item.get("currentstop") or ""),
                nextstop=str(item.get("nextstop") or ""),
                late=late_min,
                consist=_consist(item.get("consist")),
                track=str(item.get("TRACK") or ""),
            )
        )
    return [train for train in out if train.trainno]


def _stop_key(name: object) -> str:
    """Compare stop names. 'Gray 30th Street' matches '30th Street Gray'."""
    text = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower())
    text = re.sub(r"\bstation\b", " ", text)
    return " ".join(sorted(tok for tok in text.split() if tok))


def _passed_act(value: object) -> bool:
    act = str(value or "").strip().lower()
    return bool(act) and act not in {"na", "n/a", "null", "none"}


def _pack_stop(row: dict) -> dict:
    return {
        "station": str(row.get("station") or ""),
        "sched": str(row.get("sched_tm") or row.get("sched") or ""),
        "est": str(row.get("est_tm") or row.get("est") or ""),
    }


def _cut_index(rows: list[dict], currentstop: str | None) -> int | None:
    """Last stop the train has already reached. None means it has not departed."""
    want = _stop_key(currentstop)
    if want:
        for index, row in enumerate(rows):
            if _stop_key(row.get("station")) == want:
                return index
    last = None
    for index, row in enumerate(rows):
        if _passed_act(row.get("act_tm")):
            last = index
    return last


def align_remaining(rows: list[dict], nextstop: str | None) -> list[dict]:
    """Start the list at TrainView's next stop when that stop is still ahead."""
    want = _stop_key(nextstop)
    if not want:
        return rows
    for index, row in enumerate(rows):
        if _stop_key(row.get("station")) == want:
            return rows[index:]
    return rows


def remaining_stops(
    rows: object,
    currentstop: str | None = None,
    nextstop: str | None = None,
    until: str | None = None,
) -> list[dict]:
    """Stops after the train's current position, in schedule order.

    A blank act_tm does not mean the train has not been there. SEPTA leaves
    act_tm as "na" on stops the train already passed.
    """
    if not isinstance(rows, list):
        return []
    clean = [row for row in rows if isinstance(row, dict)]
    cut = _cut_index(clean, currentstop)
    start = 0 if cut is None else cut + 1
    pending = [_pack_stop(row) for row in clean[start:]]
    pending = align_remaining(pending, nextstop)
    if until and _stop_key(until):
        want = _stop_key(until)
        for index, row in enumerate(pending):
            if _stop_key(row.get("station")) == want:
                return pending[: index + 1]
    return pending


def approaching_connection(remaining: list[dict], station: str | None) -> bool:
    want = _stop_key(station)
    if not want:
        return False
    for row in list(remaining or [])[:2]:
        if _stop_key(row.get("station")) == want:
            return True
    return False


def weekday_bit(weekday: int) -> int:
    """Sunday is bit 0. Python weekday is Monday=0."""
    return 1 << ((weekday + 1) % 7)


def remaining_from_timetable(
    schedule: dict | None,
    trainno: str,
    weekday: int,
    after_minutes: int | None = None,
    currentstop: str | None = None,
    nextstop: str | None = None,
) -> list[dict]:
    """Stop order for a train number from the bundled timetable."""
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    if not isinstance(stations, dict):
        return []
    bit = weekday_bit(weekday)
    found: list[tuple[int, str, str]] = []
    want = str(trainno)
    for name, dirs in stations.items():
        if not isinstance(dirs, dict):
            continue
        for key in ("N", "S"):
            rows = dirs.get(key) or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict) or str(row.get("n") or "") != want:
                    continue
                days = int(row.get("days") or 0)
                if days and not (days & bit):
                    continue
                clock = str(row.get("t") or "")
                try:
                    hour, minute = clock.split(":")
                    mins = int(hour) * 60 + int(minute)
                except ValueError:
                    continue
                found.append((mins, str(name), clock))
    found.sort()
    matched = False
    if _stop_key(currentstop):
        needle = _stop_key(currentstop)
        for index, row in enumerate(found):
            if _stop_key(row[1]) == needle:
                found = found[index + 1 :]
                matched = True
                break
    if not matched and after_minutes is not None:
        found = [row for row in found if row[0] >= after_minutes]
    pending = [{"station": name, "sched": clock, "est": clock} for _, name, clock in found]
    return align_remaining(pending, nextstop)


def project_position(
    lat: float,
    lon: float,
    heading_deg: float | None,
    speed_mps: float,
    seconds: float,
) -> tuple[float, float]:
    if heading_deg is None or speed_mps <= 0 or seconds == 0:
        return lat, lon
    dist = speed_mps * seconds
    br = math.radians(heading_deg)
    dlat = (dist * math.cos(br)) / METERS_PER_DEG_LAT
    denom = METERS_PER_DEG_LAT * max(0.2, math.cos(math.radians(lat)))
    dlon = (dist * math.sin(br)) / denom
    return lat + dlat, lon + dlon


_GEO = None
_TIMES = None
_PRELOADED = False
_COLD_WARNED = False


def _warn_cold(name: str) -> None:
    global _COLD_WARNED
    if _PRELOADED or _COLD_WARNED:
        return
    _COLD_WARNED = True
    _LOGGER.debug("SEPTA %s was read before async_preload", name)


def _load_geo() -> dict:
    global _GEO
    if _GEO is not None:
        return _GEO
    _warn_cold("rail-geo.json")
    path = Path(__file__).with_name("rail-geo.json")
    raw = json.loads(path.read_text()) if path.is_file() else {"stops": {}, "lines": {}}
    by_key = {}
    by_coord = {}
    for name, pair in (raw.get("stops") or {}).items():
        if not isinstance(pair, list) or len(pair) < 2:
            continue
        by_key[_stop_key(name)] = (str(name), float(pair[0]), float(pair[1]))
        by_coord.setdefault((round(float(pair[0]), 4), round(float(pair[1]), 4)), str(name))
    lines = {}
    for code, stops in (raw.get("lines") or {}).items():
        if isinstance(stops, list):
            lines[str(code)] = [item for item in stops if isinstance(item, dict)]
    _GEO = {"by_key": by_key, "by_coord": by_coord, "lines": lines}
    return _GEO


def _load_times() -> dict:
    global _TIMES
    if _TIMES is not None:
        return _TIMES
    _warn_cold("rail-schedule.json")
    path = Path(__file__).with_name("rail-schedule.json")
    index: dict[str, list[tuple[str, int, int]]] = {}
    if path.is_file():
        raw = json.loads(path.read_text())
        for name, pack in (raw.get("stations") or {}).items():
            if not isinstance(pack, dict):
                continue
            key = _stop_key(name)
            for rows in pack.values():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    train = str(row.get("n") or "").strip()
                    clock = str(row.get("t") or "")
                    if not train or ":" not in clock:
                        continue
                    hour, minute = clock.split(":", 1)
                    try:
                        minutes = int(hour) * 60 + int(minute)
                        days = int(row.get("days") or 0)
                    except ValueError:
                        continue
                    index.setdefault(train, []).append((key, minutes, days))
    _TIMES = index
    return _TIMES


async def async_preload(hass) -> None:
    """Read the bundled geo and timetable files off the event loop."""
    await hass.async_add_executor_job(_load_geo)
    await hass.async_add_executor_job(_load_times)
    global _PRELOADED
    _PRELOADED = True


def _same_stop(left: object, right: object) -> bool:
    a, b = _stop_key(left), _stop_key(right)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _coord_station(lat: float, lon: float) -> str | None:
    return _load_geo()["by_coord"].get((round(lat, 4), round(lon, 4)))


def _center_or_terminal(name: str) -> bool:
    text = str(name or "").lower()
    return any(part in text for part in _CENTER)


def _fix_fingerprint(fix: Fix) -> tuple:
    def num(value: float | None) -> float | None:
        return None if value is None else round(float(value), 3)

    return (round(fix.lat, 6), round(fix.lon, 6), num(fix.speed_mps), num(fix.acc_m))


def classify_fix(fix: Fix, last: Fix | None, now: float) -> tuple[str, Fix]:
    """Accept a fix whose timestamp repeated but whose position or speed changed.

    A truly identical sample is ``duplicate_ts``. A repeated timestamp that
    moved uses ``max(last.ts + 1, now)`` so a derived speed is not infinite.
    """
    if last is None or fix.ts > last.ts:
        return "ok", fix
    if _fix_fingerprint(fix) == _fix_fingerprint(last):
        return "duplicate_ts", fix
    bumped = max(float(last.ts) + 1.0, float(now))
    return "ok", Fix(fix.lat, fix.lon, fix.acc_m, fix.speed_mps, fix.course, bumped)


def stale_reason(train: Train, trace: list[tuple] | None = None) -> str | None:
    """Why TrainView's lat/lon should not be trusted, or None."""
    station = _coord_station(train.lat, train.lon)
    current = str(train.currentstop or "").strip()
    if station and current and not _same_stop(station, current):
        return "station_mismatch"
    rows = list(trace or [])[-STALE_POLLS:]
    if len(rows) >= STALE_POLLS and len({row[0] for row in rows}) == 1:
        if len({(row[1], row[2], row[3]) for row in rows}) > 1:
            return "frozen_trace"
    return None


def position_is_stale(train: Train, trace: list[tuple] | None = None) -> bool:
    """True when TrainView's lat/lon should not be trusted."""
    return stale_reason(train, trace) is not None


def _line_stops(line: str) -> list[dict]:
    code = _line_code(line) or ""
    return list(_load_geo()["lines"].get(code) or [])


def _span(line: str, current: str, nxt: str) -> list[dict] | None:
    stops = _line_stops(line)
    if len(stops) < 2:
        return None
    keys = [_stop_key(item.get("n")) for item in stops]
    cur, end = _stop_key(current), _stop_key(nxt)
    if cur not in keys or end not in keys:
        return None
    start_at = keys.index(cur)
    stop_at = keys.index(end)
    if start_at == stop_at:
        return None
    if start_at < stop_at:
        return stops[start_at : stop_at + 1]
    return list(reversed(stops[stop_at : start_at + 1]))


def _point_along(stops: list[dict], fraction: float) -> tuple[float, float, float] | None:
    if len(stops) < 2:
        return None
    fraction = max(0.0, min(1.0, fraction))
    lengths = [0.0]
    for left, right in zip(stops, stops[1:]):
        lengths.append(lengths[-1] + haversine_m(left["lat"], left["lon"], right["lat"], right["lon"]))
    total = lengths[-1]
    if total < 1:
        return None
    target = fraction * total
    for index in range(len(stops) - 1):
        if lengths[index] <= target <= lengths[index + 1]:
            span = lengths[index + 1] - lengths[index]
            mix = 0 if span < 1 else (target - lengths[index]) / span
            left, right = stops[index], stops[index + 1]
            lat = left["lat"] + mix * (right["lat"] - left["lat"])
            lon = left["lon"] + mix * (right["lon"] - left["lon"])
            return lat, lon, bearing_deg(left["lat"], left["lon"], right["lat"], right["lon"])
    return None


def _schedule_fraction(train: Train, when: datetime) -> float | None:
    rows = _load_times().get(str(train.trainno)) or []
    if not rows:
        return None
    bit = weekday_bit(when.weekday())
    cur, nxt = _stop_key(train.currentstop), _stop_key(train.nextstop)
    starts = [minutes for key, minutes, days in rows if key == cur and (not days or days & bit)]
    ends = [minutes for key, minutes, days in rows if key == nxt and (not days or days & bit)]
    if not starts or not ends:
        return None
    now_m = when.hour * 60 + when.minute + when.second / 60
    pair = None
    for start in starts:
        for end in ends:
            if 0 < end - start <= 180:
                if pair is None or abs(((start + end) / 2) - now_m) < abs(((pair[0] + pair[1]) / 2) - now_m):
                    pair = (start, end)
    if pair is None:
        return None
    start = pair[0] + int(train.late or 0)
    end = pair[1] + int(train.late or 0)
    if end <= start:
        return None
    return max(0.0, min(1.0, (now_m - start) / (end - start)))


def estimate_position(train: Train, when: datetime) -> tuple[float, float, float] | None:
    span = _span(train.line, train.currentstop, train.nextstop)
    if not span:
        return None
    fraction = _schedule_fraction(train, when)
    if fraction is None:
        return None
    return _point_along(span, fraction)


def _corridor_gap(lat: float, lon: float, line: str) -> tuple[float, float] | None:
    stops = _line_stops(line)
    points = [(float(item["lat"]), float(item["lon"])) for item in stops if "lat" in item and "lon" in item]
    if len(points) < 2:
        return None
    best = None
    for left, right in zip(points, points[1:]):
        scale = METERS_PER_DEG_LAT * max(0.2, math.cos(math.radians(left[0])))
        bx = (right[1] - left[1]) * scale
        by = (right[0] - left[0]) * METERS_PER_DEG_LAT
        seg = math.hypot(bx, by)
        if seg < 1:
            continue
        px = (lon - left[1]) * scale
        py = (lat - left[0]) * METERS_PER_DEG_LAT
        mix = max(0.0, min(1.0, (px * bx + py * by) / (seg * seg)))
        cross = math.hypot(px - bx * mix, py - by * mix)
        if best is None or cross < best[0]:
            best = (cross, bearing_deg(left[0], left[1], right[0], right[1]))
    return best


class RideMatcher:
    """Stateful matcher. All ride memory lives here so it can be unit tested."""

    def __init__(
        self,
        radius_m: float = 300,
        min_speed_mps: float = 6.7056,
        need_matches: int = 2,
        max_accuracy_m: float = 100,
        preferred_line: str = "",
        max_fix_age_s: float = 600,
        glitch_m: float = 3000,
        glitch_s: float = 60,
        arrival_radius_m: float = ARRIVAL_RADIUS_M,
        slow_mph: float = SLOW_MPH,
        slow_seconds: float = SLOW_SECONDS,
        apart_m: float = APART_M,
        apart_fixes: int = APART_FIXES,
        max_ride_seconds: float = MAX_RIDE_SECONDS,
        reboard_cooldown_s: float = REBOARD_COOLDOWN_S,
    ) -> None:
        self.radius_m = radius_m
        self.min_speed_mps = min_speed_mps
        self.need_matches = max(1, int(need_matches))
        self.max_accuracy_m = max_accuracy_m
        self.preferred_line = preferred_line or ""
        self.max_fix_age_s = max_fix_age_s
        self.glitch_m = glitch_m
        self.glitch_s = glitch_s
        self.arrival_radius_m = float(arrival_radius_m)
        self.slow_mps = float(slow_mph) * 0.44704
        self.slow_seconds = float(slow_seconds)
        self.apart_m = float(apart_m)
        self.apart_fixes = max(1, int(apart_fixes))
        self.max_ride_seconds = float(max_ride_seconds)
        self.reboard_cooldown_s = float(reboard_cooldown_s)
        self.candidate: str | None = None
        self.match_count = 0
        self.misses = 0
        self.last_fix: Fix | None = None
        self.riding_train: Train | None = None
        self.boarded_at: str | None = None
        self.boarded_ts: float | None = None
        self.switch_train: str | None = None
        self.switch_count = 0
        self.stationary_since: float | None = None
        self.last_good_fix_ts: float | None = None
        self.gps_gap = False
        self.distance_m: float | None = None
        self.confidence = ""
        self.tracker_status = "ok"
        self.last_reason = ""
        self.speed_source = "none"
        self.phone_speed_mph = None
        self.fix_gap_s = None
        self.trainview_age_s = None
        self.candidates: list[dict] = []
        self.expected: dict | None = None
        self.leg = 1
        self._service_hint = False
        self.position_source = "gps"
        self.stale_gps = False
        self._match_via = ""
        self._fast_count = 0
        self.accepted_fix_count = 0
        self.skipped_fix_count = 0
        self.last_fix_ts = None
        self._trace: dict[str, list[tuple]] = {}
        self.leg = 1
        self._service_hint = False
        self.reason_log: list[str] = []
        self.activity_moving = False
        self.stops: list[dict] = []
        self.events: list[RideEvent] = []
        self._history: dict[str, tuple[float, float, float]] = {}
        self._prev_pos: dict[str, tuple[float, float]] = {}
        self._speed: dict[str, float] = {}
        self._glitch: set[str] = set()
        self._last_seen: dict[str, float] = {}
        self._hold_miss = 0
        self._now: float | None = None
        self.ended_reason: str | None = None
        self.ended_at: float | None = None
        self.remaining_stops: list | None = None
        self._slow_since: float | None = None
        self._slow_anchor: tuple[float, float] | None = None
        self._apart_count = 0
        self._off_count = 0
        self._on_corridor = False
        self._at_destination: str | None = None
        self._terminal_since: float | None = None
        self._cooldown: dict[str, float] = {}

    @property
    def riding(self) -> bool:
        return self.riding_train is not None

    def set_stops(self, stops: list[dict]) -> None:
        self.stops = stops or []

    def _remember(self, trains: list[Train], trains_ts: float) -> None:
        for train in trains:
            prev = self._history.get(train.trainno)
            if prev is not None:
                self._prev_pos[train.trainno] = (prev[1], prev[2])
                dt = trains_ts - prev[0]
                dist = haversine_m(prev[1], prev[2], train.lat, train.lon)
                if 0 < dt < self.glitch_s and dist > self.glitch_m:
                    self._glitch.add(train.trainno)
                elif dt > 0 and train.trainno not in self._glitch:
                    self._speed[train.trainno] = dist / dt
                elif dt > 0 and dist <= self.glitch_m:
                    self._glitch.discard(train.trainno)
                    self._speed[train.trainno] = dist / dt
            self._history[train.trainno] = (trains_ts, train.lat, train.lon)
            self._last_seen[train.trainno] = trains_ts
            spot = (round(train.lat, 4), round(train.lon, 4))
            row = (spot, _stop_key(train.currentstop), _stop_key(train.nextstop), int(train.late or 0))
            trace = self._trace.setdefault(train.trainno, [])
            trace.append(row)
            del trace[:-STALE_POLLS]

    def _projected(self, train: Train, trains_ts: float, fix_ts: float, phone_speed: float) -> tuple[float, float] | None:
        if train.trainno in self._glitch:
            return None
        dt = fix_ts - trains_ts
        speed = self._speed.get(train.trainno)
        if speed is None:
            speed = phone_speed if phone_speed and phone_speed > 0 else 0.0
        return project_position(train.lat, train.lon, train.heading, speed, dt)

    def _note(self, reason: str) -> None:
        self.last_reason = reason
        self.reason_log.append(reason)
        del self.reason_log[:-20]

    def _derived_speed(self, fix: Fix) -> float | None:
        if self.last_fix is None:
            return None
        dt = fix.ts - self.last_fix.ts
        if dt < 10 or dt > 600:
            return None
        dist = haversine_m(self.last_fix.lat, self.last_fix.lon, fix.lat, fix.lon)
        noise = (fix.acc_m or 0) + (self.last_fix.acc_m or 0)
        if dist < max(30.0, noise):
            return None
        return dist / dt

    def _phone_speed(self, fix: Fix) -> float | None:
        reported = fix.speed_mps if fix.speed_mps is not None and fix.speed_mps > 0.5 else None
        derived = self._derived_speed(fix)
        if reported is None and derived is None:
            self.speed_source = "none"
            return None
        if reported is not None and (derived is None or reported >= derived):
            self.speed_source = "reported"
            return reported
        self.speed_source = "derived"
        return derived

    def _course(self, fix: Fix, speed: float | None) -> float | None:
        reported = fix.speed_mps if fix.speed_mps is not None else -1.0
        if fix.course is not None and fix.course >= 0 and reported > 1:
            return fix.course % 360
        if self.last_fix is None:
            return None
        dist = haversine_m(self.last_fix.lat, self.last_fix.lon, fix.lat, fix.lon)
        if dist < 30:
            return None
        return bearing_deg(self.last_fix.lat, self.last_fix.lon, fix.lat, fix.lon)

    def _travel_bearing(self, train: Train) -> float | None:
        prev = self._prev_pos.get(train.trainno)
        if prev is None:
            return None
        if haversine_m(prev[0], prev[1], train.lat, train.lon) < 30:
            return None
        return bearing_deg(prev[0], prev[1], train.lat, train.lon)

    def _line_gap(self, plat: float, plon: float, tlat: float, tlon: float) -> float | None:
        points: list[tuple[float, float]] = []
        for stop in self.stops:
            lat = _float(stop.get("lat"))
            lon = _float(stop.get("lng") if stop.get("lng") is not None else stop.get("lon"))
            if lat is None or lon is None:
                continue
            points.append((lat, lon))
        if len(points) < 2:
            return None
        phone = _along_line(plat, plon, points)
        train = _along_line(tlat, tlon, points)
        if phone is None or train is None or phone[1] > 400:
            return None
        return phone[1] + abs(phone[0] - train[0])

    def _nearest_stop(self, lat: float, lon: float) -> str | None:
        best_name = None
        best = 800.0
        for stop in self.stops:
            try:
                slat = float(stop.get("lat"))
                slon = float(stop.get("lng") if stop.get("lng") is not None else stop.get("lon"))
            except (TypeError, ValueError):
                continue
            dist = haversine_m(lat, lon, slat, slon)
            if dist <= best:
                best = dist
                best_name = str(stop.get("stopname") or stop.get("name") or "")
        return best_name or None

    def _line_bonus(self, train: Train) -> int:
        if not self.preferred_line:
            return 0
        blob = f"{train.line} {train.dest}".lower()
        pref = self.preferred_line.lower()
        return -100 if pref in blob else 0

    def _view(self, train: Train, when: datetime) -> tuple[float, float, float | None, bool, str]:
        stale = position_is_stale(train, self._trace.get(train.trainno))
        if not stale:
            return train.lat, train.lon, None, False, "gps"
        estimated = estimate_position(train, when)
        if estimated is None:
            return train.lat, train.lon, None, True, "gps"
        return estimated[0], estimated[1], estimated[2], True, "estimated"

    def _prefer(self, train: Train, stale: bool, via: str) -> int:
        prefer = 0
        if self.riding_train and train.trainno == self.riding_train.trainno:
            prefer = -10000
        elif self.candidate and train.trainno == self.candidate:
            prefer = -5000
        hint = self.active_expected()
        if hint and train.trainno == hint:
            prefer -= 3000
        if stale or via == "corridor":
            prefer += 4000
        return prefer + self._line_bonus(train)

    def _on_preferred(self, train: Train) -> bool:
        hint = self.active_expected()
        if hint and train.trainno == hint:
            return True
        if not self.preferred_line:
            return False
        blob = f"{train.line} {train.dest}".lower()
        return self.preferred_line.lower() in blob

    def _speed_confirm(self, fix: Fix, scored: list[dict], views: dict, speed: float | None, tol: float):
        """Board a stale estimated train when the phone is clearly moving with it.

        Needs a fresh TrainView, two fast fixes, a heading inside tolerance, and
        a distance inside 1500 m plus accuracy plus extra slack for an estimate.
        """
        age = self.trainview_age_s
        if age is None or age >= FRESH_TRAINVIEW_S:
            return None
        if self._fast_count < SPEED_CONFIRM_FIXES:
            return None
        if (speed or 0) < SPEED_CONFIRM_MPH * 0.44704:
            return None
        pool = []
        for row in scored:
            train = row.get("_train")
            if train is None:
                continue
            view = views.get(train.trainno)
            if not view:
                continue
            stale, source = view[3], view[4]
            if not stale and source != "estimated":
                continue
            hdiff = row.get("heading_diff")
            if hdiff is not None and hdiff > tol:
                row["last_reject_reason"] = "heading"
                row["_reject"] = True
                continue
            slack = ESTIMATE_SLACK_M if stale or source == "estimated" else 0.0
            limit = SPEED_MATCH_M + (fix.acc_m or 0.0) + slack
            if row["_dist"] > limit:
                row["last_reject_reason"] = "stale" if stale else "distance"
                row["_reject"] = True
                continue
            pool.append(row)
        if not pool:
            return None
        preferred = [row for row in pool if self._on_preferred(row["_train"])]
        if preferred:
            chosen = min(preferred, key=lambda row: row["_dist"])
        elif len({row["_train"].line for row in pool}) == 1:
            chosen = min(pool, key=lambda row: row["_dist"])
        else:
            for row in pool:
                row["last_reject_reason"] = "line"
            return None
        chosen["_reject"] = False
        chosen["last_reject_reason"] = None
        chosen["_via"] = "estimated"
        chosen["limit_m"] = round(SPEED_MATCH_M + (fix.acc_m or 0.0) + ESTIMATE_SLACK_M)
        return chosen["_train"], chosen["_dist"], "estimated"

    def _pick(self, fix: Fix, trains: list[Train], trains_ts: float, speed: float | None, course: float | None) -> tuple[Train | None, float | None, str]:
        phone_speed = speed or 0.0
        gap = abs(fix.ts - trains_ts)
        tol = 75.0 if self.speed_source == "derived" else 60.0
        when = datetime.fromtimestamp(fix.ts, NY)
        views = {train.trainno: self._view(train, when) for train in trains}
        scored: list[dict] = []
        best: Train | None = None
        best_dist: float | None = None
        best_key: tuple | None = None
        best_via = ""
        heading_blocked = False
        for train in trains:
            if self._ignore_board(train, fix.ts):
                scored.append(
                    {
                        "train": train.trainno,
                        "line": train.line,
                        "dist_m": None,
                        "limit_m": round(self.radius_m),
                        "heading_diff": None,
                        "stale_gps": False,
                        "position_source": "gps",
                        "stale_reason": None,
                        "last_reject_reason": "cooldown",
                        "_train": train,
                        "_dist": 1e12,
                        "_limit": self.radius_m,
                        "_reject": True,
                        "_via": "cooldown",
                    }
                )
                continue
            lat, lon, route_heading, stale, source = views[train.trainno]
            if stale and source == "estimated":
                pos = (lat, lon)
            else:
                pos = self._projected(train, trains_ts, fix.ts, phone_speed)
            if pos is None:
                continue
            euclid = haversine_m(fix.lat, fix.lon, pos[0], pos[1])
            along = None if stale else self._line_gap(fix.lat, fix.lon, pos[0], pos[1])
            dist = min(euclid, along) if along is not None else euclid
            pace = max(phone_speed, self._speed.get(train.trainno) or 0.0)
            limit = self.radius_m + min(1500.0, gap * pace * 0.5) + (fix.acc_m or 0.0)
            if stale and route_heading is not None:
                heading = route_heading
            else:
                travel = self._travel_bearing(train)
                heading = travel if travel is not None else train.heading
            hdiff = None if course is None or heading is None else angle_diff(course, heading)
            reject = False
            reason = None
            if hdiff is not None and hdiff > tol:
                reject = True
                reason = "heading"
                if dist <= limit:
                    heading_blocked = True
            elif dist > limit:
                reject = True
                reason = "stale" if stale else "distance"
            scored.append(
                {
                    "train": train.trainno,
                    "line": train.line,
                    "dist_m": round(dist),
                    "limit_m": round(limit),
                    "heading_diff": None if hdiff is None else round(hdiff),
                    "stale_gps": stale,
                    "position_source": source if stale else "gps",
                    "stale_reason": stale_reason(train, self._trace.get(train.trainno)),
                    "last_reject_reason": reason,
                    "_train": train,
                    "_dist": dist,
                    "_limit": limit,
                    "_reject": reject,
                    "_via": "radius",
                }
            )
            if reject:
                continue
            prefer = self._prefer(train, stale, "radius")
            key = (prefer, dist)
            if best_key is None or key < best_key:
                best = train
                best_dist = dist
                best_key = key
                best_via = "radius" if source == "gps" else "estimated"
        if best is None:
            picked = self._speed_confirm(fix, scored, views, speed, tol)
            if picked is not None:
                best, best_dist, best_via = picked
        if best is None and self._fast_count >= SPEED_CONFIRM_FIXES and (speed or 0) >= FAST_MPH * 0.44704:
            for train in trains:
                if self._ignore_board(train, fix.ts):
                    continue
                lat, lon, _route_heading, stale, source = views[train.trainno]
                corridor = _corridor_gap(fix.lat, fix.lon, train.line)
                if corridor is None or corridor[0] > CORRIDOR_M:
                    continue
                if course is not None and angle_diff(course, corridor[1]) > 75:
                    continue
                reach_at = (lat, lon) if source == "estimated" else (train.lat, train.lon)
                reach = haversine_m(fix.lat, fix.lon, reach_at[0], reach_at[1])
                if reach > CORRIDOR_REACH_M:
                    continue
                prefer = self._prefer(train, True, "corridor")
                key = (prefer, reach)
                if best_key is None or key < best_key:
                    best = train
                    best_dist = reach
                    best_key = key
                    best_via = "corridor"
                    stale = True
                    source = "estimated" if source == "estimated" or stale else "gps"
                for row in scored:
                    if row["train"] == train.trainno:
                        row["dist_m"] = round(reach)
                        row["limit_m"] = round(CORRIDOR_REACH_M)
                        row["stale_gps"] = stale or row["stale_gps"]
                        row["position_source"] = "estimated" if row["stale_gps"] else "gps"
                        row["_dist"] = reach
                        row["_reject"] = False
                        row["last_reject_reason"] = None
                        row["_via"] = "corridor"
                        break
                else:
                    scored.append(
                        {
                            "train": train.trainno,
                            "line": train.line,
                            "dist_m": round(reach),
                            "limit_m": round(CORRIDOR_REACH_M),
                            "heading_diff": None if course is None else round(angle_diff(course, corridor[1])),
                            "stale_gps": True,
                            "position_source": "estimated",
                            "stale_reason": stale_reason(train, self._trace.get(train.trainno)),
                            "last_reject_reason": None,
                            "_train": train,
                            "_dist": reach,
                            "_limit": CORRIDOR_REACH_M,
                            "_reject": False,
                            "_via": "corridor",
                        }
                    )
        scored.sort(key=lambda row: row["_dist"])
        self.candidates = [
            {
                "train": row["train"],
                "line": row["line"],
                "dist_m": row["dist_m"],
                "limit_m": row["limit_m"],
                "heading_diff": row["heading_diff"],
                "stale_gps": row["stale_gps"],
                "position_source": row["position_source"],
                "last_reject_reason": row.get("last_reject_reason"),
                "stale_reason": row.get("stale_reason"),
            }
            for row in scored[:3]
        ]
        self._scored = scored
        if best is not None:
            chosen = views.get(best.trainno, (0, 0, None, False, "gps"))
            self.stale_gps = bool(chosen[3]) or best_via in {"corridor", "estimated"}
            self.position_source = "estimated" if self.stale_gps else "gps"
            self._match_via = best_via if best_via in {"corridor", "estimated"} else "radius"
            _LOGGER.debug(
                "SEPTA ride accept train=%s source=%s stale=%s via=%s dist_m=%s",
                best.trainno,
                self.position_source,
                self.stale_gps,
                self._match_via,
                None if best_dist is None else round(best_dist),
            )
            return best, best_dist, ""
        self._match_via = ""
        self.position_source = "gps"
        self.stale_gps = False
        reason = "heading_mismatch" if heading_blocked and any(row["_dist"] <= row["_limit"] for row in scored) else "no_train_in_radius"
        _LOGGER.debug("SEPTA ride reject reason=%s trains=%s", reason, len(trains))
        return None, None, reason

    def _candidate_held(self) -> bool:
        if not self.candidate:
            return False
        for row in getattr(self, "_scored", []):
            if row["train"] == self.candidate and row["_dist"] <= 2 * row["_limit"]:
                return True
        return False

    def active_expected(self) -> str | None:
        if not self.expected:
            return None
        if self.leg == 2 and self.expected.get("connection_train"):
            return str(self.expected["connection_train"])
        return str(self.expected.get("train") or "") or None

    def planned_trip(self) -> dict | None:
        exp = self.expected
        if not exp:
            return None
        connection = None
        if exp.get("connection_train") or exp.get("connection_station"):
            connection = {
                "station": exp.get("connection_station"),
                "train": exp.get("connection_train"),
                "line": exp.get("connection_line"),
                "depart_est": exp.get("connection_depart_est"),
                "arrive_est": exp.get("connection_arrive_est"),
                "wait_min": exp.get("wait_min"),
                "at_risk": exp.get("at_risk"),
            }
        return {
            "origin": exp.get("origin"),
            "destination": exp.get("destination"),
            "train": exp.get("first_train") or exp.get("train"),
            "connection": connection,
        }

    def set_expected(self, hint: dict | None, now: float | None = None) -> None:
        if not hint or not str(hint.get("train") or "").strip():
            self.expected = None
            self.leg = 1
            return
        train = str(hint.get("train") or "").strip()
        valid = hint.get("valid_until")
        if valid is None and now is not None:
            valid = float(now) + 3 * 3600
        self.expected = {
            "train": train,
            "first_train": train,
            "origin": hint.get("origin") or None,
            "destination": hint.get("destination") or None,
            "connection_train": str(hint.get("connection_train") or "").strip() or None,
            "connection_station": hint.get("connection_station") or None,
            "connection_line": hint.get("connection_line") or None,
            "connection_depart_est": hint.get("connection_depart_est"),
            "connection_arrive_est": hint.get("connection_arrive_est"),
            "wait_min": hint.get("wait_min"),
            "at_risk": hint.get("at_risk"),
            "valid_until": valid,
        }
        self.leg = 1

    def clear_expected(self, reason: str) -> RideEvent:
        train = self.active_expected()
        self.expected = None
        self.leg = 1
        event = RideEvent("expected_cleared", {"reason": reason, "train": train, "expected_train": train})
        self.events.append(event)
        return event

    def note_train_status(self, trainno: str, cancelled: bool = False, late: int | None = None) -> RideEvent | None:
        if self.active_expected() != str(trainno):
            return None
        if cancelled:
            return self.clear_expected("cancelled")
        if late is not None and int(late) > 60:
            return self.clear_expected("delay")
        return None

    def _expire_expected(self, now: float) -> None:
        valid = None if not self.expected else self.expected.get("valid_until")
        if valid is not None and now > float(valid):
            self.clear_expected("expired")

    def _maybe_handover(self) -> None:
        exp = self.expected
        if not exp or self.leg != 1 or self.riding_train is None:
            return
        if self.riding_train.trainno != str(exp.get("train") or ""):
            return
        station = exp.get("connection_station")
        if not station or not exp.get("connection_train"):
            return
        if _stop_key(self.riding_train.currentstop) == _stop_key(station):
            self.leg = 2

    def _same_trip(self, trainno: str) -> bool:
        exp = self.expected
        if not exp or not exp.get("connection_train"):
            return False
        return str(trainno) == str(exp.get("connection_train")) and (self.leg == 2 or _stop_key(getattr(self.riding_train, "currentstop", "")) == _stop_key(exp.get("connection_station")))

    def payload(self) -> dict:
        train = self.riding_train
        riding = train is not None
        consist = list(train.consist) if train else []
        return {
            "riding": riding,
            "train": train.trainno if train else None,
            "line": train.line if train else None,
            "line_code": _line_code(train.line) if train else None,
            "destination": train.dest if train else None,
            "service": train.service if train else None,
            "current_stop": train.currentstop if train else None,
            "next_stop": train.nextstop if train else None,
            "late_min": train.late if train else None,
            "consist": consist,
            "cars": len(consist),
            "distance_m": None if self.distance_m is None else round(self.distance_m),
            "heading": train.heading if train else None,
            "match_count": self.match_count if not riding else self.need_matches,
            "confidence": (
                "gps_gap"
                if self.gps_gap and riding
                else (
                    "estimated"
                    if riding and self.position_source == "estimated"
                    else ("riding" if riding else ("candidate" if self.candidate else ""))
                )
            ),
            "boarded_at": self.boarded_at,
            "boarded_time": self.boarded_ts,
            "gps_gap": bool(self.gps_gap and riding),
            "tracker_status": self.tracker_status,
            "last_reason": self.last_reason,
            "phone_speed_mph": self.phone_speed_mph,
            "speed_source": self.speed_source,
            "fix_gap_s": None if self.fix_gap_s is None else round(self.fix_gap_s, 1),
            "trainview_age_s": None if self.trainview_age_s is None else round(self.trainview_age_s, 1),
            "accepted_fix_count": self.accepted_fix_count,
            "skipped_fix_count": self.skipped_fix_count,
            "last_fix_ts": self.last_fix_ts,
            "candidates": list(self.candidates),
            "expected_train": self.active_expected(),
            "planned_trip": self.planned_trip(),
            "transfer_next": False,
            "leg": self.leg if self.expected else 1,
            "final_destination": None if not self.expected else self.expected.get("destination"),
            "next_stop_track": None,
            "next_stop_platform": None,
            "connection_track": None,
            "connection_platform": None,
            "position_source": self.position_source if riding or self.candidate or self.ended_reason else None,
            "stale_gps": bool(self.stale_gps) if riding else False,
            "ended_reason": self.ended_reason,
            "ended_at": None if self.ended_at is None else datetime.fromtimestamp(self.ended_at, NY).isoformat(),
        }

    def _event(self, kind: str, extra: dict | None = None) -> RideEvent:
        payload = self.payload()
        if extra:
            payload.update(extra)
        return RideEvent(kind, payload)

    def _board(self, train: Train, fix: Fix, dist: float | None) -> RideEvent:
        self.riding_train = train
        self.candidate = train.trainno
        self.match_count = self.need_matches
        self.misses = 0
        self.switch_train = None
        self.switch_count = 0
        self.distance_m = dist
        self.gps_gap = False
        self.confidence = "estimated" if self._match_via in {"corridor", "estimated"} else "riding"
        gap = _corridor_gap(fix.lat, fix.lon, train.line)
        if gap is not None and gap[0] <= CORRIDOR_M:
            self._on_corridor = True
        self.ended_reason = None
        self.ended_at = None
        self._slow_since = None
        self._slow_anchor = None
        self._apart_count = 0
        self._off_count = 0
        self._at_destination = None
        self._terminal_since = None
        if self.boarded_ts is None:
            where = self._nearest_stop(fix.lat, fix.lon) or train.currentstop or None
            self.boarded_at = where
            self.boarded_ts = fix.ts
        event = self._event("boarded")
        self.events.append(event)
        return event

    def _exit(self, ts: float, reason: str) -> RideEvent:
        started = self.boarded_ts
        duration = None if started is None else max(0, int(ts - started))
        exited_at = None
        if self.last_fix is not None:
            exited_at = self._nearest_stop(self.last_fix.lat, self.last_fix.lon)
        if not exited_at and self.riding_train:
            exited_at = self.riding_train.currentstop or None
        extra = {"exited_at": exited_at, "duration": duration, "reason": reason}
        self.ended_reason = reason
        self.ended_at = ts
        if self.riding_train is not None:
            self._cooldown[self.riding_train.trainno] = ts
        event = self._event("exited", extra)
        self.events.append(event)
        _LOGGER.debug(
            "SEPTA ride end reason=%s train=%s speed_mph=%s dist_m=%s stale=%s duration_s=%s",
            reason,
            None if self.riding_train is None else self.riding_train.trainno,
            self.phone_speed_mph,
            None if self.distance_m is None else round(self.distance_m),
            self.stale_gps,
            duration,
        )
        self.riding_train = None
        self.candidate = None
        self.match_count = 0
        self.misses = 0
        self.switch_train = None
        self.switch_count = 0
        self.boarded_at = None
        self.boarded_ts = None
        self.stationary_since = None
        self._slow_since = None
        self._apart_count = 0
        self._off_count = 0
        self._on_corridor = False
        self._at_destination = None
        self._terminal_since = None
        self.gps_gap = False
        self.confidence = ""
        self.distance_m = None
        return event

    def _cooled(self, trainno: str, now: float) -> bool:
        ts = self._cooldown.get(str(trainno))
        if ts is None:
            return False
        if now - ts >= self.reboard_cooldown_s:
            self._cooldown.pop(str(trainno), None)
            return False
        return True

    def _ignore_board(self, train: Train, now: float) -> bool:
        if self.riding_train is not None and train.trainno == self.riding_train.trainno:
            return False
        if self._same_trip(train.trainno):
            return False
        return self._cooled(train.trainno, now)

    def _active_cooldown(self) -> tuple[str, float] | None:
        now = self._now
        chosen: tuple[str, float] | None = None
        for trainno, ts in list(self._cooldown.items()):
            if now is not None and now - ts >= self.reboard_cooldown_s:
                self._cooldown.pop(trainno, None)
                continue
            if chosen is None or ts >= chosen[1]:
                chosen = (trainno, ts)
        return chosen

    @property
    def cooldown_train(self) -> str | None:
        item = self._active_cooldown()
        return None if item is None else item[0]

    @property
    def cooldown_until(self) -> float | None:
        item = self._active_cooldown()
        if item is None:
            return None
        return item[1] + self.reboard_cooldown_s

    def _train_point(self, train: Train, ts: float) -> tuple[float, float, bool]:
        stale = position_is_stale(train, self._trace.get(train.trainno))
        if not stale:
            return train.lat, train.lon, False
        estimated = estimate_position(train, datetime.fromtimestamp(ts, NY))
        if estimated is None:
            return train.lat, train.lon, True
        return estimated[0], estimated[1], True

    def _following(self, fix: Fix, train: Train, speed: float | None) -> bool:
        if speed is None or speed < self.min_speed_mps:
            return False
        gap = _corridor_gap(fix.lat, fix.lon, train.line)
        return gap is not None and gap[0] <= CORRIDOR_M

    def _near_any_stop(self, lat: float, lon: float) -> bool:
        for _name, slat, slon in _load_geo()["by_key"].values():
            if haversine_m(lat, lon, float(slat), float(slon)) <= self.arrival_radius_m:
                return True
        return False

    def _arrival_name(self) -> str | None:
        exp = self.expected
        if not exp:
            return None
        if exp.get("destination"):
            return str(exp["destination"])
        if self.leg == 1 and exp.get("connection_station"):
            return str(exp["connection_station"])
        return None

    def _is_terminal(self, train: Train) -> bool:
        current = str(train.currentstop or "").strip()
        if not current:
            return False
        remaining = self.remaining_stops
        if remaining:
            last = str(remaining[-1].get("station") or "")
            return bool(last) and _same_stop(current, last)
        dest = str(train.dest or "").strip()
        return bool(dest) and _same_stop(current, dest)

    def _ride_limit(self) -> float:
        limit = self.max_ride_seconds
        train = self.riding_train
        if train is None:
            return limit
        minutes = [item[1] for item in (_load_times().get(str(train.trainno)) or [])]
        if len(minutes) < 2:
            return limit
        span = (max(minutes) - min(minutes)) * 60
        if span <= 0:
            return limit
        return max(limit, span + 3600)

    def _maybe_end(self, fix: Fix, trains: list[Train], speed: float | None, prev_ts: float) -> str | None:
        train = self.riding_train
        if train is None:
            return None
        fresh = next((item for item in trains if item.trainno == train.trainno), train)
        train = fresh
        lat, lon, stale = self._train_point(train, fix.ts)
        dist = haversine_m(fix.lat, fix.lon, lat, lon)
        self.distance_m = dist
        if stale:
            self.stale_gps = True
            self.position_source = "estimated" if (lat, lon) != (train.lat, train.lon) else self.position_source
        target = self._arrival_name()
        if target:
            spot = _load_geo()["by_key"].get(_stop_key(target))
            if spot is not None and haversine_m(fix.lat, fix.lon, spot[1], spot[2]) <= self.arrival_radius_m:
                left = bool(train.currentstop) and not _same_stop(train.currentstop, target)
                left = left or haversine_m(train.lat, train.lon, spot[1], spot[2]) > self.apart_m
                if self._at_destination == _stop_key(target) and left:
                    return "arrived"
                self._at_destination = _stop_key(target)
            else:
                self._at_destination = None
        slow = speed is None or speed < self.slow_mps
        if slow:
            if self._slow_since is None:
                self._slow_since = prev_ts
                self._slow_anchor = (train.lat, train.lon)
        elif not stale or self._following(fix, train, speed):
            self._slow_since = None
            self._slow_anchor = None
        if self._slow_since is not None and fix.ts - self._slow_since >= self.slow_seconds:
            if stale:
                return "slow"
            if dist >= self.apart_m or self._near_any_stop(fix.lat, fix.lon):
                return "stationary" if speed is None or speed < 2.0 else "slow"
        if dist > self.apart_m and stale:
            self._apart_count += 1
        elif not stale or self._following(fix, train, speed):
            self._apart_count = 0
        if self._apart_count >= self.apart_fixes:
            return "separated"
        gap = _corridor_gap(fix.lat, fix.lon, train.line)
        if gap is not None and gap[0] <= CORRIDOR_M:
            self._on_corridor = True
            if not stale or self._following(fix, train, speed):
                self._off_count = 0
        elif self._on_corridor and gap is not None and gap[0] > CORRIDOR_M:
            self._off_count += 1
            if self._off_count >= self.apart_fixes:
                return "left_corridor"
        if self._is_terminal(train):
            if self._terminal_since is None:
                self._terminal_since = fix.ts
            elif fix.ts > self._terminal_since:
                return "terminal"
        else:
            self._terminal_since = None
        if self.boarded_ts is not None and fix.ts - self.boarded_ts > self._ride_limit():
            return "max_duration"
        return None

    def update(self, fix: Fix, trains: list[Train], trains_ts: float, now: float | None = None) -> RideEvent | None:
        self.events = []
        self._now = now if now is not None else fix.ts
        self._expire_expected(self._now)
        self._remember(trains, trains_ts)
        kind, fix = classify_fix(fix, self.last_fix, self._now)
        self.trainview_age_s = abs(fix.ts - trains_ts)
        self.fix_gap_s = None if self.last_fix is None else fix.ts - self.last_fix.ts
        if fix.acc_m is not None and fix.acc_m > self.max_accuracy_m:
            self.skipped_fix_count += 1
            self._note("accuracy")
            return None
        if kind != "ok":
            self.skipped_fix_count += 1
            self._note(kind)
            return None
        if self._now - fix.ts > self.max_fix_age_s:
            self.skipped_fix_count += 1
            self._note("stale_fix")
            return None
        self.accepted_fix_count += 1
        self.last_fix_ts = fix.ts
        speed = self._phone_speed(fix)
        course = self._course(fix, speed)
        self.phone_speed_mph = None if speed is None else round(speed / 0.44704, 1)
        prev_ts = self.last_fix.ts if self.last_fix is not None else fix.ts
        self.last_fix = fix
        self.last_good_fix_ts = fix.ts
        self.gps_gap = False
        moving = speed is not None and speed >= self.min_speed_mps
        if not moving and self.activity_moving and self.speed_source == "none":
            moving = True
        if speed is not None and speed >= FAST_MPH * 0.44704:
            self._fast_count += 1
        else:
            self._fast_count = 0
        best, dist, reject = self._pick(fix, trains, trains_ts, speed, course)
        if self.riding:
            reason = self._maybe_end(fix, trains, speed, prev_ts)
            if reason:
                self._note(reason)
                return self._exit(fix.ts, reason)
        if not moving:
            if not self.riding:
                self._note("not_moving")
                return None
            near = (
                best is not None
                and self.riding_train is not None
                and best.trainno == self.riding_train.trainno
                and (dist or 0) <= 2 * self.radius_m
            )
            stale_ride = self.riding_train is not None and position_is_stale(self.riding_train, self._trace.get(self.riding_train.trainno))
            if near and not stale_ride:
                self.misses = 0
                self.riding_train = best
                self.distance_m = dist
                if speed is not None and speed >= self.slow_mps:
                    self._slow_since = None
                    self.stationary_since = None
                self._note("riding")
                return None
            if near and stale_ride:
                self.riding_train = best
                self.distance_m = dist
                self._note("riding")
                return None
            self._note("not_moving")
            return None
        self.stationary_since = None
        if best is None:
            if self._candidate_held() and self._hold_miss == 0 and not self.riding:
                self._hold_miss = 1
                self._note("misses")
                return None
            self._hold_miss = 0
            self.candidate = None
            self.match_count = 0
            self.switch_count = 0
            self.switch_train = None
            self._note(reject or "no_train_in_radius")
            if self.riding:
                self.misses += 1
                if self.misses >= 3:
                    return self._exit(fix.ts, "misses")
            return None
        self._hold_miss = 0
        self.misses = 0
        self.distance_m = dist
        if self.riding and best.trainno == self.riding_train.trainno:
            self.riding_train = best
            self.switch_count = 0
            self.switch_train = None
            self.confidence = "estimated" if self._match_via in {"corridor", "estimated"} else "riding"
            self._maybe_handover()
            self._note("riding")
            return None
        if self.riding and best.trainno != self.riding_train.trainno:
            if self.switch_train == best.trainno:
                self.switch_count += 1
            else:
                self.switch_train = best.trainno
                self.switch_count = 1
            if self.switch_count >= self.need_matches:
                if self._same_trip(best.trainno):
                    self.leg = 2
                    self.riding_train = None
                    self.candidate = None
                    self.match_count = 0
                    self.switch_count = 0
                    self.switch_train = None
                    self._note("boarded")
                    return self._board(best, fix, dist)
                self._exit(fix.ts, "transfer")
                self._note("boarded")
                return self._board(best, fix, dist)
            self._note("candidate")
            return None
        if self.candidate == best.trainno:
            self.match_count += 1
        else:
            self.candidate = best.trainno
            if self._match_via in {"corridor", "estimated"}:
                self.match_count = min(self.need_matches, max(1, self._fast_count))
            else:
                self.match_count = 1
        self.confidence = "candidate"
        if self.match_count >= self.need_matches:
            self._note("boarded")
            return self._board(best, fix, dist)
        self._note("candidate")
        return None

    def tick(self, now: float, trains: list[Train], trains_ts: float) -> RideEvent | None:
        self.events = []
        self._now = now
        self._remember(trains, trains_ts)
        if not self.riding or self.riding_train is None:
            return None
        if self.boarded_ts is not None and now - self.boarded_ts > self._ride_limit():
            return self._exit(now, "max_duration")
        if self._is_terminal(self.riding_train):
            if self._terminal_since is None:
                self._terminal_since = now
            elif now - self._terminal_since >= TERMINAL_GRACE_S or now > self._terminal_since:
                return self._exit(now, "terminal")
        else:
            self._terminal_since = None
        number = self.riding_train.trainno
        seen = next((train for train in trains if train.trainno == number and train.trainno not in self._glitch), None)
        if seen is not None:
            self.riding_train = seen
            self._last_seen[number] = trains_ts
            self._maybe_handover()
            if seen.late and int(seen.late) > 60 and self.active_expected() == number:
                return self.clear_expected("delay")
        else:
            last = self._last_seen.get(number)
            if last is not None and now - last > 300:
                return self._exit(now, "train_gone")
        hinted = self.active_expected()
        if hinted:
            seen_hint = self._last_seen.get(hinted)
            if seen_hint is not None and now - seen_hint > 3600:
                return self.clear_expected("stale")
        self._expire_expected(now)
        if self.last_good_fix_ts is None or now - self.last_good_fix_ts > 20 * 60:
            if self.last_good_fix_ts is not None and now - self.last_good_fix_ts > 20 * 60:
                return self._exit(now, "no_fix")
        if self.last_good_fix_ts is not None and now - self.last_good_fix_ts >= 60:
            self.gps_gap = True
            self.confidence = "gps_gap"
        return None

    def set_tracker_state(self, state: str, ts: float | None = None) -> RideEvent | None:
        self.events = []
        self.tracker_status = state or "unknown"
        if str(state).lower() == "home" and self.riding:
            return self._exit(ts if ts is not None else (self.last_fix.ts if self.last_fix else 0), "home")
        return None


_LINE_NAMES = {
    "airport": "AIR",
    "chestnut hill east": "CHE",
    "chestnut hill west": "CHW",
    "cynwyd": "CYN",
    "fox chase": "FOX",
    "lansdale": "LAN",
    "doylestown": "LAN",
    "media": "MED",
    "wawa": "MED",
    "manayunk": "NOR",
    "norristown": "NOR",
    "paoli": "PAO",
    "thorndale": "PAO",
    "trenton": "TRE",
    "warminster": "WAR",
    "west trenton": "WTR",
    "wilmington": "WIL",
    "newark": "WIL",
}


def _line_code(line: str | None) -> str | None:
    if not line:
        return None
    text = line.strip().lower()
    if len(text) <= 3 and text.upper() in set(_LINE_NAMES.values()):
        return text.upper()
    for name, code in sorted(_LINE_NAMES.items(), key=lambda item: -len(item[0])):
        if name in text:
            return code
    return None


def rider_object_id(entity_id: str) -> str:
    text = str(entity_id or "").strip()
    return text.split(".", 1)[1] if "." in text else text


def configured_riders(options: dict | None, data: dict | None = None) -> list[str]:
    """Riders from options. A missing list falls back to the old single tracker."""
    options = options or {}
    data = data or {}
    if "ride_riders" in options:
        raw = options.get("ride_riders")
    elif "ride_riders" in data:
        raw = data.get("ride_riders")
    else:
        raw = None
    if raw is None:
        tracker = str(options.get("ride_tracker") or data.get("ride_tracker") or "").strip()
        return [tracker] if tracker else []
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",") if part.strip()]
    return [str(item).strip() for item in (raw or []) if str(item).strip()]


def dedupe_riders(entity_ids: list[str], person_to_tracker: dict[str, str] | None = None) -> list[dict]:
    """One record per person. A person and that person's phone tracker count once."""
    links = person_to_tracker or {}
    tracker_to_person: dict[str, str] = {}
    for person, tracker in links.items():
        if person and tracker:
            tracker_to_person.setdefault(str(tracker), str(person))
    seen: set[str] = set()
    out: list[dict] = []
    for entity in entity_ids:
        entity = str(entity or "").strip()
        if not entity:
            continue
        if entity.startswith("person."):
            person = entity
            tracker = str(links.get(person) or "")
            key = person
        else:
            tracker = entity
            person = tracker_to_person.get(entity, "")
            key = person or tracker
        if key in seen:
            continue
        seen.add(key)
        slug_source = person or tracker or entity
        out.append(
            {
                "key": key,
                "slug": rider_object_id(slug_source),
                "configured": person or entity,
                "person": person or None,
                "tracker": tracker or None,
                "primary": not out,
            }
        )
    return out


def riders_summary(rows: list[dict]) -> dict:
    riding = []
    trains: dict[str, list] = {}
    for row in rows:
        slug = row.get("rider")
        if row.get("riding"):
            riding.append(
                {
                    "rider": slug,
                    "person": row.get("person"),
                    "friendly_name": row.get("friendly_name_rider"),
                    "entity_picture": row.get("entity_picture"),
                    "train": row.get("train"),
                    "line": row.get("line"),
                    "next_stop": row.get("next_stop"),
                }
            )
            train = row.get("train")
            if train:
                trains.setdefault(str(train), []).append(slug)
        else:
            pass
    return {
        "count": len(riding),
        "riding": riding,
        "riders": [row.get("rider") for row in rows],
        "trains": trains,
    }


class TrainCache:
    """One TrainView fetch shared by every rider."""

    def __init__(self, ttl: float = 15) -> None:
        self.ttl = ttl
        self.rows: list = []
        self.ts = 0.0
        self.fetches = 0
        self._lock = None

    async def get(self, now: float, fetch):
        import asyncio

        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self.ts and now - self.ts < self.ttl:
                return self.rows, self.ts
            self.rows = await fetch()
            self.fetches += 1
            self.ts = now
            return self.rows, self.ts
