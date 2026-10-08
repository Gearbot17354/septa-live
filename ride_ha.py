"""Home Assistant adapter for ride matching.

`ride.py` stays import-free so the unit tests can load it without Home Assistant.
This module is the only place that talks to the tracker, the bus, and SEPTA.
"""

from __future__ import annotations

import copy
import logging
import time
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .const import (
    CONF_RIDE_MATCHES,
    CONF_RIDE_MAX_ACCURACY,
    CONF_RIDE_MIN_SPEED,
    CONF_RIDE_RADIUS,
    CONF_RIDE_REQUEST,
    CONF_RIDE_TRACKER,
    DEFAULT_RIDE_MATCHES,
    DEFAULT_RIDE_MAX_ACCURACY,
    DEFAULT_RIDE_MIN_SPEED,
    DEFAULT_RIDE_RADIUS,
    DOMAIN,
    RIDE_FAST_SCAN,
    RRSCHEDULES_URL,
    TRAINVIEW_URL,
)
from .coordinator import NY, _LINE_NAMES, _load_schedule
from .ride import (
    Fix,
    RideMatcher,
    haversine_m,
    parse_trainview,
    remaining_from_timetable,
    remaining_stops,
    _line_code,
)

_LOGGER = logging.getLogger(__name__)
_MPH = 0.44704
_STOPS_NEAR_M = 500


def _num(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm(value: object) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


class RideController:
    """Subscribe to one phone tracker and publish ride state. Inert until a tracker is set."""

    def __init__(self, hass: HomeAssistant, coordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.entry = coordinator.entry
        self.matcher = RideMatcher()
        self._unsubs: list = []
        self._watched: set[str] = set()
        self._fast_unsub = None
        self._subscribed = ""
        self._configured = ""
        self._resolved = ""
        self._zone_state = ""
        self._request_updates = False
        self._warned = False
        self._last_extra = 0.0
        self._last_ping = 0.0
        self._remaining: list[dict] = []
        self._remaining_source = ""
        self._rr_train = ""
        self._rr_ts = 0.0
        self._read_options()

    def signal(self) -> str:
        return f"{DOMAIN}_ride_{self.entry.entry_id}"

    def _preferred_line(self) -> str:
        code = (self.coordinator.rail_line or "").upper()
        if code and code in _LINE_NAMES:
            return _LINE_NAMES[code]
        return self.coordinator.station or ""

    def _pick(self, key: str, default):
        options = self.entry.options
        if key in options:
            return options[key]
        return self.entry.data.get(key, default)

    def _read_options(self) -> None:
        self._configured = str(self._pick(CONF_RIDE_TRACKER, "") or "").strip()
        self._request_updates = bool(self._pick(CONF_RIDE_REQUEST, False))
        self.matcher.radius_m = float(self._pick(CONF_RIDE_RADIUS, DEFAULT_RIDE_RADIUS) or DEFAULT_RIDE_RADIUS)
        mph = float(self._pick(CONF_RIDE_MIN_SPEED, DEFAULT_RIDE_MIN_SPEED) or DEFAULT_RIDE_MIN_SPEED)
        self.matcher.min_speed_mps = mph * _MPH
        self.matcher.need_matches = max(1, int(self._pick(CONF_RIDE_MATCHES, DEFAULT_RIDE_MATCHES) or 1))
        self.matcher.max_accuracy_m = float(
            self._pick(CONF_RIDE_MAX_ACCURACY, DEFAULT_RIDE_MAX_ACCURACY) or DEFAULT_RIDE_MAX_ACCURACY
        )
        self.matcher.preferred_line = self._preferred_line()

    def attributes(self) -> dict:
        payload = self.matcher.payload()
        payload["remaining_stops"] = list(self._remaining) if self.matcher.riding else []
        payload["remaining_source"] = self._remaining_source if self.matcher.riding else None
        payload["tracker"] = self._resolved or self._configured or None
        payload["last_fix"] = _iso(self.matcher.last_fix.ts) if self.matcher.last_fix else None
        payload["boarded_time"] = _iso(self.matcher.boarded_ts) if self.matcher.boarded_ts else None
        return payload

    async def async_start(self) -> None:
        """Listen only when a tracker is configured."""
        self._read_options()
        if not self._configured or self._subscribed == self._configured:
            return
        self._subscribed = self._configured
        self._watch(self._configured)
        try:
            state = self.hass.states.get(self._configured)
        except Exception:  # noqa: BLE001
            state = None
        if state is None:
            self._mark_unavailable()
            self._push()
            return
        await self._consume_state(state)

    def async_stop(self) -> None:
        for unsub in list(self._unsubs):
            try:
                unsub()
            except Exception:  # noqa: BLE001
                continue
        self._unsubs.clear()
        self._watched.clear()
        if self._fast_unsub is not None:
            try:
                self._fast_unsub()
            except Exception:  # noqa: BLE001
                pass
            self._fast_unsub = None
        self._subscribed = ""

    async def async_reconfigure(self) -> None:
        """Apply option changes without reloading the config entry."""
        previous = self._subscribed
        self._read_options()
        if self._configured == previous:
            self._push()
            self._sync_fast()
            return
        self.async_stop()
        self.matcher = RideMatcher()
        self._remaining = []
        self._remaining_source = ""
        self._rr_train = ""
        self._rr_ts = 0.0
        self._warned = False
        self._resolved = ""
        self._read_options()
        await self.async_start()

    def _watch(self, entity_id: str) -> None:
        if not entity_id or entity_id in self._watched:
            return
        self._watched.add(entity_id)
        self._unsubs.append(async_track_state_change_event(self.hass, [entity_id], self._on_tracker))

    @callback
    def _on_tracker(self, event) -> None:
        new_state = event.data.get("new_state")
        self.hass.async_create_task(self._consume_state(new_state))

    async def _consume_state(self, state) -> None:
        try:
            await self._match_state(state)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("SEPTA ride update failed")
            return
        try:
            self._emit()
            await self._maybe_ping()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("SEPTA ride publish failed")

    async def _match_state(self, state) -> None:
        if state is None:
            self._mark_unavailable()
            return
        tracked, _entity_id = self._resolve(state)
        if tracked is None and str(getattr(state, "state", "") or "").lower() != "home":
            self._mark_unavailable()
            return
        source = tracked or state
        self._zone_state = str(getattr(source, "state", "") or "")
        if str(getattr(source, "state", "") or "").lower() == "home":
            snap = copy.deepcopy(self.matcher)
            try:
                self.matcher.set_tracker_state("home", _state_ts(source))
            except Exception:
                self.matcher = snap
                raise
            return
        if tracked is None or tracked.state in ("unavailable", "unknown", None, ""):
            self._mark_unavailable()
            return
        lat = _num(tracked.attributes.get("latitude"))
        lon = _num(tracked.attributes.get("longitude"))
        if lat is None or lon is None:
            self._mark_unavailable()
            return
        self._warned = False
        await self._ensure_stops()
        fix = _fix_from_state(tracked)
        trains: list = []
        trains_ts = time.time()
        if fix is not None:
            trains, trains_ts = await self._trains_for(fix)
        snap = copy.deepcopy(self.matcher)
        try:
            self.matcher.set_tracker_state(str(tracked.state), _state_ts(tracked))
            self.matcher.tracker_status = "ok"
            if fix is None:
                return
            self.matcher.update(fix, trains, trains_ts)
        except Exception:
            self.matcher = snap
            raise
        if self.matcher.riding and self.matcher.riding_train is not None:
            await self._refresh_remaining(force=self._rr_train != self.matcher.riding_train.trainno)

    def _resolve(self, state):
        entity_id = state.entity_id
        if entity_id.startswith("person.") or getattr(state, "domain", "") == "person":
            source = state.attributes.get("source")
            if isinstance(source, str) and source.startswith("device_tracker."):
                self._watch(source)
                tracked = self.hass.states.get(source)
                if tracked is not None:
                    self._resolved = source
                    return tracked, source
            self._resolved = entity_id
            return None, entity_id
        self._resolved = entity_id
        return state, entity_id

    def _mark_unavailable(self) -> None:
        self.matcher.tracker_status = "unavailable"
        if not self._warned:
            _LOGGER.warning("SEPTA ride tracker %s is unavailable", self._configured or "unset")
            self._warned = True

    async def _ensure_stops(self) -> None:
        code = (self.coordinator.rail_line or _line_code(self.coordinator.station) or "LAN").upper()
        stops = await self.coordinator.async_line_stops(code)
        if stops:
            self.matcher.set_stops(stops)

    async def _trains_for(self, fix: Fix) -> tuple[list, float]:
        now = time.time()
        cached_ts = float(self.coordinator.trainview_ts or 0)
        accepted = _fix_accepted(fix, self.matcher)
        if accepted and now - cached_ts >= 15 and now - self._last_extra >= 15:
            if await self._fetch_trainview():
                self._last_extra = now
        rows = self.coordinator.trainview_rows or []
        ts = float(self.coordinator.trainview_ts or now)
        return parse_trainview(rows), ts

    async def _fetch_trainview(self) -> bool:
        try:
            raw = await self.coordinator._get(TRAINVIEW_URL, {})
        except Exception:  # noqa: BLE001
            _LOGGER.debug("SEPTA ride TrainView fetch failed")
            return False
        self.coordinator.trainview_rows = raw if isinstance(raw, list) else []
        self.coordinator.trainview_ts = time.time()
        return True

    async def _refresh_remaining(self, force: bool = False) -> None:
        train = self.matcher.riding_train
        if train is None:
            self._remaining = []
            self._remaining_source = ""
            self._rr_train = ""
            return
        now = time.time()
        if not force and self._rr_train == train.trainno and now - self._rr_ts < 60 and self._remaining:
            return
        rows: list[dict] | None = None
        try:
            raw = await self.coordinator._get(RRSCHEDULES_URL, {"req1": train.trainno})
            if isinstance(raw, dict):
                for value in raw.values():
                    if isinstance(value, list):
                        raw = value
                        break
            rows = remaining_stops(raw)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("RRSchedules failed for train %s", train.trainno)
            rows = None
        if rows:
            self._remaining = rows
            self._remaining_source = "rrschedules"
        else:
            now_ny = datetime.now(NY)
            minutes = now_ny.hour * 60 + now_ny.minute
            self._remaining = remaining_from_timetable(
                _load_schedule(), train.trainno, now_ny.weekday(), minutes
            )
            self._remaining_source = "timetable"
        self._rr_train = train.trainno
        self._rr_ts = now

    async def _on_fast(self, now) -> None:
        try:
            if time.time() - float(self.coordinator.trainview_ts or 0) >= 15:
                await self._fetch_trainview()
            await self._ensure_stops()
            trains = parse_trainview(self.coordinator.trainview_rows or [])
            ts = float(self.coordinator.trainview_ts or time.time())
        except Exception:  # noqa: BLE001
            _LOGGER.exception("SEPTA ride scan failed")
            return
        snap = copy.deepcopy(self.matcher)
        try:
            self.matcher.tick(now.timestamp(), trains, ts)
        except Exception:  # noqa: BLE001
            self.matcher = snap
            _LOGGER.exception("SEPTA ride scan failed")
            return
        try:
            if self.matcher.riding:
                await self._refresh_remaining()
            self._emit()
            await self._maybe_ping()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("SEPTA ride scan publish failed")

    def _emit(self) -> None:
        events = list(self.matcher.events)
        self.matcher.events = []
        for event in events:
            if event.kind == "boarded":
                name = "septa_live_train_boarded"
            elif event.kind == "exited":
                name = "septa_live_train_exited"
            else:
                continue
            data = dict(event.payload)
            if isinstance(data.get("boarded_time"), (int, float)):
                data["boarded_time"] = _iso(data["boarded_time"])
            data["remaining_stops"] = list(self._remaining)
            data["remaining_source"] = self._remaining_source or None
            data["tracker"] = self._resolved or self._configured or None
            data["last_fix"] = _iso(self.matcher.last_fix.ts) if self.matcher.last_fix else None
            data["entry_id"] = self.entry.entry_id
            if event.kind == "exited":
                data["riding"] = False
            for key in ("latitude", "longitude", "lat", "lon"):
                data.pop(key, None)
            self.hass.bus.async_fire(name, data)
        self._push()
        self._sync_fast()

    def _push(self) -> None:
        async_dispatcher_send(self.hass, self.signal(), self.attributes())

    def _armed(self) -> bool:
        if self.matcher.riding or self.matcher.candidate:
            return True
        if self._near_station():
            return True
        return self._in_station_zone()

    def _near_station(self) -> bool:
        fix = self.matcher.last_fix
        if fix is None:
            return False
        for stop in self.matcher.stops:
            lat = _num(stop.get("lat"))
            lon = _num(stop.get("lng") if stop.get("lng") is not None else stop.get("lon"))
            if lat is None or lon is None:
                continue
            if haversine_m(fix.lat, fix.lon, lat, lon) <= _STOPS_NEAR_M:
                return True
        return False

    def _in_station_zone(self) -> bool:
        name = _norm(self._zone_state)
        if name in ("", "home", "nothome", "unknown", "unavailable"):
            return False
        for stop in self.matcher.stops:
            stop_name = _norm(stop.get("stopname") or stop.get("name"))
            if stop_name and (stop_name == name or stop_name in name or name in stop_name):
                return True
        return False

    def _sync_fast(self) -> None:
        armed = bool(self._subscribed) and self._armed()
        if armed and self._fast_unsub is None:
            self._fast_unsub = async_track_time_interval(
                self.hass, self._on_fast, timedelta(seconds=RIDE_FAST_SCAN)
            )
        elif not armed and self._fast_unsub is not None:
            try:
                self._fast_unsub()
            except Exception:  # noqa: BLE001
                pass
            self._fast_unsub = None

    async def _maybe_ping(self) -> None:
        if not self._request_updates or self.matcher.riding:
            return
        if not (self.matcher.candidate or self._near_station() or self._in_station_zone()):
            return
        now = time.time()
        if now - self._last_ping < 120:
            return
        entity = self._resolved or self._configured
        if not entity.startswith("device_tracker."):
            return
        self._last_ping = now
        service = f"mobile_app_{entity.split('.', 1)[1]}"
        try:
            await self.hass.services.async_call(
                "notify",
                service,
                {"message": "request_location_update"},
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("SEPTA ride location request was not sent")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, NY).isoformat()


def _state_ts(state) -> float:
    updated = getattr(state, "last_updated", None)
    if updated is None:
        return time.time()
    try:
        return updated.timestamp()
    except Exception:  # noqa: BLE001
        return time.time()


def _fix_from_state(state) -> Fix | None:
    lat = _num(state.attributes.get("latitude"))
    lon = _num(state.attributes.get("longitude"))
    if lat is None or lon is None:
        return None
    speed = _num(state.attributes.get("speed"))
    if speed is not None and speed < 0:
        speed = None
    course = _num(state.attributes.get("course"))
    if course is None:
        course = _num(state.attributes.get("heading"))
    if course is not None and course < 0:
        course = None
    return Fix(
        lat=lat,
        lon=lon,
        acc_m=_num(state.attributes.get("gps_accuracy")),
        speed_mps=speed,
        course=course,
        ts=_state_ts(state),
    )


def _fix_accepted(fix: Fix, matcher: RideMatcher) -> bool:
    if fix.acc_m is not None and fix.acc_m > matcher.max_accuracy_m:
        return False
    if matcher.last_fix is not None and fix.ts <= matcher.last_fix.ts:
        return False
    if time.time() - fix.ts > matcher.max_fix_age_s:
        return False
    return True
