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
    CONF_RIDE_ACTIVITY,
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
from .coordinator import NY, _LINE_NAMES, cached_schedule
from .ride import (
    Fix,
    RideMatcher,
    TrainCache,
    approaching_connection,
    configured_riders,
    dedupe_riders,
    haversine_m,
    parse_trainview,
    remaining_from_timetable,
    remaining_stops,
    riders_summary,
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


class RiderController:
    """One person, one matcher. Inert until that rider is configured."""

    def __init__(self, hass: HomeAssistant, coordinator, manager, spec: dict) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.manager = manager
        self.entry = coordinator.entry
        self.matcher = RideMatcher()
        self.key = spec["key"]
        self.slug = spec["slug"]
        self.person = spec.get("person")
        self.is_primary = bool(spec.get("primary"))
        self._tracker_hint = spec.get("tracker") or ""
        self._unsubs: list = []
        self._watched: set[str] = set()
        self._fast_unsub = None
        self._subscribed = ""
        self._configured = spec["configured"]
        self._resolved = self._tracker_hint if str(self._tracker_hint).startswith("device_tracker.") else ""
        self._zone_state = ""
        self._request_updates = False
        self._warned = False
        self._last_extra = 0.0
        self._last_ping = 0.0
        self._remaining: list[dict] = []
        self._remaining_source = ""
        self._rr_train = ""
        self._rr_ts = 0.0
        self._rr_raw: list[dict] | None = None
        self.apply_tuning()

    def signal(self) -> str:
        return f"{DOMAIN}_ride_{self.entry.entry_id}_{self.slug}"

    def legacy_signal(self) -> str:
        return f"{DOMAIN}_ride_{self.entry.entry_id}"

    def _activity_automotive(self) -> bool:
        entity = str(self._pick(CONF_RIDE_ACTIVITY, "") or "").strip()
        if not entity:
            return False
        state = self.hass.states.get(entity)
        return bool(state and str(state.state).lower() == "automotive")

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

    def apply_tuning(self) -> None:
        self._request_updates = bool(self._pick(CONF_RIDE_REQUEST, False))
        self.matcher.radius_m = float(self._pick(CONF_RIDE_RADIUS, DEFAULT_RIDE_RADIUS) or DEFAULT_RIDE_RADIUS)
        mph = float(self._pick(CONF_RIDE_MIN_SPEED, DEFAULT_RIDE_MIN_SPEED) or DEFAULT_RIDE_MIN_SPEED)
        self.matcher.min_speed_mps = mph * _MPH
        self.matcher.need_matches = max(1, int(self._pick(CONF_RIDE_MATCHES, DEFAULT_RIDE_MATCHES) or 1))
        self.matcher.max_accuracy_m = float(
            self._pick(CONF_RIDE_MAX_ACCURACY, DEFAULT_RIDE_MAX_ACCURACY) or DEFAULT_RIDE_MAX_ACCURACY
        )
        self.matcher.preferred_line = self._preferred_line()
        self._apply_entity_hint()

    def _expected_entity(self) -> str:
        raw = self._pick("ride_expected", "")
        if isinstance(raw, dict):
            return str(raw.get(self.slug) or (raw.get("") if self.is_primary else "") or "").strip()
        text = str(raw or "").strip()
        return text if self.is_primary else ""

    def _apply_entity_hint(self) -> None:
        if self.matcher._service_hint:
            return
        entity = self._expected_entity()
        if not entity:
            return
        state = self.hass.states.get(entity)
        from .trips import parse_expected_state

        self.matcher.set_expected(parse_expected_state(None if state is None else state.state))

    def apply_service_hint(self, hint: dict | None, now: float | None = None) -> None:
        train = "" if not hint else str(hint.get("train") or "").strip()
        self.matcher._service_hint = bool(train)
        cleaned = dict(hint or {})
        valid = cleaned.get("valid_until")
        if isinstance(valid, str) and valid.strip():
            try:
                from datetime import datetime

                parsed = datetime.fromisoformat(valid.strip())
                cleaned["valid_until"] = parsed.timestamp()
            except ValueError:
                cleaned["valid_until"] = None
        self.matcher.set_expected(cleaned if train else None, now=now)

    def _read_options(self) -> None:
        self.apply_tuning()

    def attributes(self) -> dict:
        payload = self.matcher.payload()
        remaining = list(self._remaining) if self.matcher.riding else []
        payload["remaining_stops"] = remaining
        if self.matcher.riding and remaining:
            payload["next_stop"] = remaining[0].get("station") or payload.get("next_stop")
        station = None if not self.matcher.expected else self.matcher.expected.get("connection_station")
        payload["transfer_next"] = approaching_connection(remaining, station)
        payload["remaining_source"] = self._remaining_source if self.matcher.riding else None
        payload["tracker"] = self._resolved or self._tracker_hint or self._configured or None
        payload["last_fix"] = _iso(self.matcher.last_fix.ts) if self.matcher.last_fix else None
        payload["boarded_time"] = _iso(self.matcher.boarded_ts) if self.matcher.boarded_ts else None
        payload["rider"] = self.slug
        payload["person"] = self.person
        person_state = self.hass.states.get(self.person) if self.person else None
        payload["friendly_name_rider"] = getattr(person_state, "name", None) or self.slug
        payload["entity_picture"] = None
        if person_state is not None:
            payload["entity_picture"] = person_state.attributes.get("entity_picture")
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
        """Retune this rider without dropping a ride that is already in progress."""
        self.apply_tuning()
        self._push()
        self._sync_fast()

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
            self.matcher.activity_moving = self._activity_automotive()
            self.matcher.set_tracker_state(str(tracked.state), _state_ts(tracked))
            self.matcher.tracker_status = "ok"
            if fix is None:
                return
            self.matcher.update(fix, trains, trains_ts, now=time.time())
            _LOGGER.debug(
                "SEPTA ride %s mph=%s source=%s gap=%s tv_age=%s candidates=%s",
                self.matcher.last_reason,
                self.matcher.phone_speed_mph,
                self.matcher.speed_source,
                self.matcher.fix_gap_s,
                self.matcher.trainview_age_s,
                self.matcher.candidates,
            )
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
        accepted = _fix_accepted(fix, self.matcher)

        async def _fetch():
            try:
                raw = await self.coordinator._get(TRAINVIEW_URL, {})
            except Exception:  # noqa: BLE001
                _LOGGER.debug("SEPTA ride TrainView fetch failed")
                return self.manager.train_cache.rows
            return raw if isinstance(raw, list) else []

        if accepted:
            rows, ts = await self.manager.train_cache.get(now, _fetch)
        else:
            rows, ts = self.manager.train_cache.rows, self.manager.train_cache.ts or now
        self.coordinator.trainview_rows = rows
        self.coordinator.trainview_ts = ts
        return parse_trainview(rows), ts

    async def _fetch_trainview(self) -> bool:
        rows, ts = await self.manager.train_cache.get(time.time(), self._pull_trainview)
        self.coordinator.trainview_rows = rows
        self.coordinator.trainview_ts = ts
        return True

    async def _pull_trainview(self):
        try:
            raw = await self.coordinator._get(TRAINVIEW_URL, {})
        except Exception:  # noqa: BLE001
            _LOGGER.debug("SEPTA ride TrainView fetch failed")
            return self.manager.train_cache.rows
        return raw if isinstance(raw, list) else []

    async def _refresh_remaining(self, force: bool = False) -> None:
        train = self.matcher.riding_train
        if train is None:
            self._remaining = []
            self._remaining_source = ""
            self._rr_train = ""
            self._rr_raw = None
            return
        now = time.time()
        fetch = (
            force
            or self._rr_train != train.trainno
            or self._rr_raw is None
            or now - self._rr_ts >= 60
        )
        if fetch:
            raw_rows: list[dict] | None = None
            try:
                raw = await self.coordinator._get(RRSCHEDULES_URL, {"req1": train.trainno})
                if isinstance(raw, dict):
                    for value in raw.values():
                        if isinstance(value, list):
                            raw = value
                            break
                if isinstance(raw, list):
                    raw_rows = [row for row in raw if isinstance(row, dict)]
            except Exception:  # noqa: BLE001
                _LOGGER.debug("RRSchedules failed for train %s", train.trainno)
                raw_rows = None
            if raw_rows:
                self._rr_raw = raw_rows
                self._rr_train = train.trainno
                self._rr_ts = now
            elif self._rr_train != train.trainno:
                self._rr_raw = None
                self._rr_train = train.trainno
                self._rr_ts = 0.0
        if self._rr_raw:
            until = None
            expected = self.matcher.expected
            if self.matcher.leg == 1 and expected and expected.get("connection_station"):
                until = expected.get("connection_station")
            self._remaining = remaining_stops(self._rr_raw, train.currentstop, train.nextstop, until)
            self._remaining_source = "rrschedules"
            return
        now_ny = datetime.now(NY)
        minutes = now_ny.hour * 60 + now_ny.minute
        self._remaining = remaining_from_timetable(
            cached_schedule(),
            train.trainno,
            now_ny.weekday(),
            minutes,
            train.currentstop,
            train.nextstop,
        )
        self._remaining_source = "timetable"

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
            for event in list(self.matcher.events):
                if event.kind == "expected_cleared":
                    self.hass.bus.async_fire(
                        "septa_live_expected_train_cleared",
                        {
                            "train": event.payload.get("train"),
                            "reason": event.payload.get("reason"),
                            "rider": self.slug,
                            "entry_id": self.entry.entry_id,
                        },
                    )
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
            if self._remaining:
                data["next_stop"] = self._remaining[0].get("station") or data.get("next_stop")
            data["remaining_source"] = self._remaining_source or None
            data["tracker"] = self._resolved or self._tracker_hint or self._configured or None
            data["rider"] = self.slug
            data["person"] = self.person
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
        attrs = self.attributes()
        async_dispatcher_send(self.hass, self.signal(), attrs)
        if self.is_primary:
            async_dispatcher_send(self.hass, self.legacy_signal(), attrs)
        self.manager.push_summary()

    def _sync_fast(self) -> None:
        self.manager.sync_fast()

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


class RideController:
    """One matcher per rider. TrainView is fetched once for all of them."""

    def __init__(self, hass: HomeAssistant, coordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.entry = coordinator.entry
        self.riders: dict[str, RiderController] = {}
        self.train_cache = TrainCache(15)
        self._fast_unsub = None

    @property
    def primary(self) -> RiderController | None:
        for rider in self.riders.values():
            if rider.is_primary:
                return rider
        return next(iter(self.riders.values()), None)

    @property
    def matcher(self) -> RideMatcher:
        primary = self.primary
        return primary.matcher if primary is not None else RideMatcher()

    def signal(self) -> str:
        return f"{DOMAIN}_ride_{self.entry.entry_id}"

    def summary_signal(self) -> str:
        return f"{DOMAIN}_riders_{self.entry.entry_id}"

    def attributes(self) -> dict:
        primary = self.primary
        return primary.attributes() if primary is not None else {}

    def summary(self) -> dict:
        return riders_summary([rider.attributes() for rider in self.riders.values()])

    def push_summary(self) -> None:
        async_dispatcher_send(self.hass, self.summary_signal(), self.summary())

    def specs(self) -> list[dict]:
        raw = configured_riders(self.entry.options, self.entry.data)
        links: dict[str, str] = {}
        try:
            people = self.hass.states.async_all("person")
        except Exception:  # noqa: BLE001
            people = []
        for state in people or []:
            source = state.attributes.get("source")
            if isinstance(source, str) and source.startswith("device_tracker."):
                links[state.entity_id] = source
        return dedupe_riders(raw, links)

    def rider_for(self, name: str | None) -> RiderController | None:
        want = str(name or "").strip()
        if not want:
            return self.primary
        for rider in self.riders.values():
            if want in (rider.slug, rider.person, rider._configured, rider._resolved, rider.key):
                return rider
        return self.primary

    async def async_start(self) -> None:
        await self.async_reconfigure()

    def async_stop(self) -> None:
        if self._fast_unsub is not None:
            try:
                self._fast_unsub()
            except Exception:  # noqa: BLE001
                pass
            self._fast_unsub = None
        for rider in list(self.riders.values()):
            rider.async_stop()
        self.riders.clear()

    async def async_reconfigure(self) -> None:
        specs = self.specs()
        wanted = {spec["key"] for spec in specs}
        for key, rider in list(self.riders.items()):
            if key not in wanted:
                rider.async_stop()
                self.riders.pop(key, None)
        for spec in specs:
            rider = self.riders.get(spec["key"])
            if rider is None:
                rider = RiderController(self.hass, self.coordinator, self, spec)
                self.riders[spec["key"]] = rider
                await rider.async_start()
            else:
                rider.is_primary = bool(spec.get("primary"))
                if spec.get("person"):
                    rider.person = spec["person"]
                await rider.async_reconfigure()
        self.push_summary()
        self.sync_fast()

    def sync_fast(self) -> None:
        armed = any(rider._subscribed and rider._armed() for rider in self.riders.values())
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

    async def _on_fast(self, now) -> None:
        for rider in list(self.riders.values()):
            await rider._on_fast(now)


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
