"""Phone-to-train matching. No Home Assistant imports."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

EARTH_M = 6_371_000.0
METERS_PER_DEG_LAT = 111_320.0


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


def remaining_stops(rows: object) -> list[dict]:
    """RRSchedules rows that have not been passed (`act_tm == na`)."""
    if not isinstance(rows, list):
        return []
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("act_tm") or "").strip().lower() != "na":
            continue
        out.append(
            {
                "station": str(row.get("station") or ""),
                "sched": str(row.get("sched_tm") or ""),
                "est": str(row.get("est_tm") or ""),
            }
        )
    return out


def weekday_bit(weekday: int) -> int:
    """Sunday is bit 0. Python weekday is Monday=0."""
    return 1 << ((weekday + 1) % 7)


def remaining_from_timetable(
    schedule: dict | None,
    trainno: str,
    weekday: int,
    after_minutes: int | None = None,
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
    if after_minutes is not None:
        found = [row for row in found if row[0] >= after_minutes]
    return [{"station": name, "sched": clock, "est": clock} for _, name, clock in found]


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


class RideMatcher:
    """Stateful matcher. All ride memory lives here so it can be unit tested."""

    def __init__(
        self,
        radius_m: float = 300,
        min_speed_mps: float = 6.7056,
        need_matches: int = 2,
        max_accuracy_m: float = 100,
        preferred_line: str = "",
        max_fix_age_s: float = 120,
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
        self.stops: list[dict] = []
        self.events: list[RideEvent] = []
        self._history: dict[str, tuple[float, float, float]] = {}
        self._speed: dict[str, float] = {}
        self._glitch: set[str] = set()
        self._last_seen: dict[str, float] = {}
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

    def _projected(self, train: Train, trains_ts: float, fix_ts: float, phone_speed: float) -> tuple[float, float] | None:
        if train.trainno in self._glitch:
            return None
        dt = fix_ts - trains_ts
        speed = self._speed.get(train.trainno)
        if speed is None:
            speed = phone_speed if phone_speed and phone_speed > 0 else 0.0
        return project_position(train.lat, train.lon, train.heading, speed, dt)

    def _phone_speed(self, fix: Fix) -> float | None:
        if fix.speed_mps is not None and fix.speed_mps >= 0:
            return fix.speed_mps
        if self.last_fix is None:
            return None
        dt = fix.ts - self.last_fix.ts
        if dt < 10 or dt > 600:
            return None
        return haversine_m(self.last_fix.lat, self.last_fix.lon, fix.lat, fix.lon) / dt

    def _course(self, fix: Fix, speed: float | None) -> float | None:
        if fix.course is not None and fix.course >= 0:
            return fix.course % 360
        if self.last_fix is None or not speed or speed < 1:
            return None
        return bearing_deg(self.last_fix.lat, self.last_fix.lon, fix.lat, fix.lon)

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

    def _pick(self, fix: Fix, trains: list[Train], trains_ts: float, speed: float | None, course: float | None) -> tuple[Train | None, float | None]:
        phone_speed = speed or 0.0
        extra = min(abs(fix.ts - trains_ts) * max(phone_speed, 0.0), 1000.0)
        limit = self.radius_m + extra
        best: Train | None = None
        best_dist: float | None = None
        best_key: tuple | None = None
        for train in trains:
            pos = self._projected(train, trains_ts, fix.ts, phone_speed)
            if pos is None:
                continue
            dist = haversine_m(fix.lat, fix.lon, pos[0], pos[1])
            if dist > limit:
                continue
            if course is not None and train.heading is not None and angle_diff(course, train.heading) > 60:
                continue
            prefer = 0
            if self.riding_train and train.trainno == self.riding_train.trainno:
                prefer = -10000
            elif self.candidate and train.trainno == self.candidate:
                prefer = -5000
            prefer += self._line_bonus(train)
            key = (prefer, dist)
            if best_key is None or key < best_key:
                best = train
                best_dist = dist
                best_key = key
        return best, best_dist

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
        self.confidence = "riding"
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
        self._remember(trains, trains_ts)
        if fix.acc_m is not None and fix.acc_m > self.max_accuracy_m:
            return None
        if self.last_fix is not None and fix.ts <= self.last_fix.ts:
            return None
        if self._now - fix.ts > self.max_fix_age_s:
            return None
        speed = self._phone_speed(fix)
        course = self._course(fix, speed)
        prev_ts = self.last_fix.ts if self.last_fix is not None else fix.ts
        self.last_fix = fix
        self.last_good_fix_ts = fix.ts
        self.gps_gap = False
        moving = speed is not None and speed >= self.min_speed_mps
        creeping = speed is None or speed < 2.0
        best, dist = self._pick(fix, trains, trains_ts, speed, course)
        if not moving:
            if not self.riding:
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
                return None
            if creeping:
                if self.stationary_since is None:
                    self.stationary_since = prev_ts
                away = best is None or self.riding_train is None or best.trainno != self.riding_train.trainno or (dist or 0) > 2 * self.radius_m
                if away and fix.ts - self.stationary_since >= 180:
                    return self._exit(fix.ts, "stationary")
            return None
        self.stationary_since = None
        if best is None:
            self.candidate = None
            self.match_count = 0
            self.switch_count = 0
            self.switch_train = None
            if self.riding:
                self.misses += 1
                if self.misses >= 3:
                    return self._exit(fix.ts, "misses")
            return None
        self.misses = 0
        self.distance_m = dist
        if self.riding and best.trainno == self.riding_train.trainno:
            self.riding_train = best
            self.switch_count = 0
            self.switch_train = None
            self.confidence = "riding"
            return None
        if self.riding and best.trainno != self.riding_train.trainno:
            if self.switch_train == best.trainno:
                self.switch_count += 1
            else:
                self.switch_train = best.trainno
                self.switch_count = 1
            if self.switch_count >= self.need_matches:
                self._exit(fix.ts, "transfer")
                return self._board(best, fix, dist)
            return None
        if self.candidate == best.trainno:
            self.match_count += 1
        else:
            self.candidate = best.trainno
            self.match_count = 1
        self.confidence = "candidate"
        if self.match_count >= self.need_matches:
            return self._board(best, fix, dist)
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
        else:
            last = self._last_seen.get(number)
            if last is not None and now - last > 300:
                return self._exit(now, "train_gone")
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
