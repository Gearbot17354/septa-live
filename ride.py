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
            }
        )
    return {"events": events, "steps": steps, "riding": matcher.riding, "position_source": matcher.position_source}


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


def _load_geo() -> dict:
    global _GEO
    if _GEO is None:
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
    if _TIMES is None:
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


def position_is_stale(train: Train, trace: list[tuple] | None = None) -> bool:
    """True when TrainView's lat/lon should not be trusted."""
    station = _coord_station(train.lat, train.lon)
    current = str(train.currentstop or "").strip()
    if station and current and not _same_stop(station, current):
        return True
    if not train.consist and station and current and not _same_stop(station, current) and _center_or_terminal(station):
        return True
    rows = list(trace or [])[-STALE_POLLS:]
    if len(rows) >= STALE_POLLS and len({row[0] for row in rows}) == 1:
        if len({(row[1], row[2], row[3]) for row in rows}) > 1:
            return True
    return False


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
    ) -> None:
        self.radius_m = radius_m
        self.min_speed_mps = min_speed_mps
        self.need_matches = max(1, int(need_matches))
        self.max_accuracy_m = max_accuracy_m
        self.preferred_line = preferred_line or ""
        self.max_fix_age_s = max_fix_age_s
        self.glitch_m = glitch_m
        self.glitch_s = glitch_s
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
            reject = dist > limit
            if not reject and hdiff is not None and hdiff > tol:
                reject = True
                heading_blocked = True
            scored.append(
                {
                    "train": train.trainno,
                    "line": train.line,
                    "dist_m": round(dist),
                    "limit_m": round(limit),
                    "heading_diff": None if hdiff is None else round(hdiff),
                    "stale_gps": stale,
                    "position_source": source if stale else "gps",
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
        if best is None and self._fast_count >= 2 and (speed or 0) >= FAST_MPH * 0.44704:
            for train in trains:
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
                key: row[key]
                for key in ("train", "line", "dist_m", "limit_m", "heading_diff", "stale_gps", "position_source")
            }
            for row in scored[:3]
        ]
        self._scored = scored
        if best is not None:
            chosen = views.get(best.trainno, (0, 0, None, False, "gps"))
            self.stale_gps = bool(chosen[3]) or best_via == "corridor"
            self.position_source = "estimated" if self.stale_gps else "gps"
            self._match_via = "corridor" if best_via == "corridor" else "radius"
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
            "confidence": "gps_gap" if self.gps_gap and riding else ("riding" if riding else ("candidate" if self.candidate else "")),
            "boarded_at": self.boarded_at,
            "boarded_time": self.boarded_ts,
            "gps_gap": bool(self.gps_gap and riding),
            "tracker_status": self.tracker_status,
            "last_reason": self.last_reason,
            "phone_speed_mph": self.phone_speed_mph,
            "speed_source": self.speed_source,
            "fix_gap_s": None if self.fix_gap_s is None else round(self.fix_gap_s, 1),
            "trainview_age_s": None if self.trainview_age_s is None else round(self.trainview_age_s, 1),
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
            "position_source": self.position_source if riding or self.candidate else None,
            "stale_gps": bool(self.stale_gps) if riding else False,
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
        self.confidence = "estimated" if self._match_via == "corridor" else "riding"
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
        event = self._event("exited", extra)
        self.events.append(event)
        self.riding_train = None
        self.candidate = None
        self.match_count = 0
        self.misses = 0
        self.switch_train = None
        self.switch_count = 0
        self.boarded_at = None
        self.boarded_ts = None
        self.stationary_since = None
        self.gps_gap = False
        self.confidence = ""
        self.distance_m = None
        return event

    def update(self, fix: Fix, trains: list[Train], trains_ts: float, now: float | None = None) -> RideEvent | None:
        self.events = []
        self._now = now if now is not None else fix.ts
        self._expire_expected(self._now)
        self._remember(trains, trains_ts)
        self.trainview_age_s = abs(fix.ts - trains_ts)
        self.fix_gap_s = None if self.last_fix is None else fix.ts - self.last_fix.ts
        if fix.acc_m is not None and fix.acc_m > self.max_accuracy_m:
            self._note("accuracy")
            return None
        if self.last_fix is not None and fix.ts <= self.last_fix.ts:
            self._note("duplicate_ts")
            return None
        if self._now - fix.ts > self.max_fix_age_s:
            self._note("stale_fix")
            return None
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
        creeping = speed is None or speed < 2.0
        if speed is not None and speed >= FAST_MPH * 0.44704:
            self._fast_count += 1
        else:
            self._fast_count = 0
        best, dist, reject = self._pick(fix, trains, trains_ts, speed, course)
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
            if near:
                self.misses = 0
                self.riding_train = best
                self.distance_m = dist
                self.stationary_since = None if not creeping else (self.stationary_since or fix.ts)
                self._note("riding")
                return None
            if creeping:
                if self.stationary_since is None:
                    self.stationary_since = prev_ts
                away = best is None or self.riding_train is None or best.trainno != self.riding_train.trainno or (dist or 0) > 2 * self.radius_m
                if away and fix.ts - self.stationary_since >= 180:
                    self._note("not_moving")
                    return self._exit(fix.ts, "stationary")
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
            self.confidence = "estimated" if self._match_via == "corridor" else "riding"
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
            if self._match_via == "corridor":
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
