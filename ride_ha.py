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
    CONF_CORRIDOR_CHORD,
    CONF_GOOD_ACCURACY,
    CONF_GOOD_FIX_AGE,
    CONF_HOME_STATION,
    CONF_RECOVER_S,
    CONF_RIDE_ACTIVITY,
    CONF_RIDE_MATCHES,
    CONF_RIDE_MAX_ACCURACY,
    CONF_RIDE_MIN_SPEED,
    CONF_RIDE_RADIUS,
    CONF_RIDE_REQUEST,
    CONF_RIDE_TRACKER,
    CONF_UNDERGROUND_STOPS,
    CORRIDOR_CHORD_M,
    DEFAULT_RIDE_MATCHES,
    DEFAULT_RIDE_MAX_ACCURACY,
    DEFAULT_RIDE_MIN_SPEED,
    DEFAULT_RIDE_RADIUS,
    DOMAIN,
    GOOD_ACCURACY_M,
    GOOD_FIX_AGE_S,
    RECOVER_S,
    RIDE_FAST_SCAN,
    RRSCHEDULES_URL,
    TRAINVIEW_URL,
)
from .coordinator import NY, _LINE_NAMES, cached_schedule
from .shapes import line_title, lookup_train
from .ride import (
    Fix,
    RideMatcher,
    TrainCache,
    apply_delay,
    approaching_connection,
    through_change,
    alight_plan,
    annotate_coords,
    destination_is_auto,
    rider_cfg_row,
    rider_home,
    finish_remaining,
    dest_parts,
    should_republish_destination,
    _loose_name,
    classify_fix,
    configured_riders,
    dedupe_riders,
    haversine_m,
    parse_trainview,
    position_is_stale,
    remaining_from_timetable,
    remaining_stops,
    riders_summary,
    trim_passed,
    _line_code,
    _stop_key,
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
        self.matcher = RideMatcher(switch_fixes=3, switch_min_s=120)
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
        self._dest_entity = ""
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
        self.matcher.good_accuracy_m = float(self._pick(CONF_GOOD_ACCURACY, GOOD_ACCURACY_M) or GOOD_ACCURACY_M)
        self.matcher.good_fix_age_s = float(self._pick(CONF_GOOD_FIX_AGE, GOOD_FIX_AGE_S) or GOOD_FIX_AGE_S)
        self.matcher.corridor_chord_m = float(self._pick(CONF_CORRIDOR_CHORD, CORRIDOR_CHORD_M) or CORRIDOR_CHORD_M)
        self.matcher.recover_s = float(self._pick(CONF_RECOVER_S, RECOVER_S) or RECOVER_S)
        raw_stops = self._pick(CONF_UNDERGROUND_STOPS, []) or []
        if isinstance(raw_stops, str):
            raw_stops = [part.strip() for part in raw_stops.split(",") if part.strip()]
        self.matcher.set_underground(list(raw_stops), self.matcher.learned_underground)
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
        train = self.matcher.riding_train
        if train is not None:
            payload["latitude"] = train.lat
            payload["longitude"] = train.lon
        remaining = list(self._remaining) if self.matcher.riding else []
        marked = finish_remaining(remaining, self.matcher.alight_station)
        payload["remaining_stops"] = marked["rows"]
        payload["alight_index"] = marked["alight_index"]
        payload["stops_to_alight"] = marked["stops_to_alight"]
        if marked["alight_est"] is not None:
            payload["alight_est"] = marked["alight_est"]
        if self.matcher.riding and marked["rows"]:
            payload["next_stop"] = marked["rows"][0].get("station") or payload.get("next_stop")
        station = None if not self.matcher.expected else self.matcher.expected.get("connection_station")
        payload["transfer_next"] = approaching_connection(marked["rows"], station)
        payload["through_line"] = self.matcher.through_line
        payload["through_line_code"] = self.matcher.through_line_code
        payload["through_at"] = self.matcher.through_at
        payload["remaining_source"] = self._remaining_source if self.matcher.riding else None
        payload["delay_min"] = self.matcher.delay_min
        payload["alight_station"] = self.matcher.alight_station
        payload["alight_source"] = self.matcher.alight_source
        payload["alight_est"] = self.matcher.alight_est
        payload["stop_source"] = self.matcher.stop_source
        if self.matcher.published_current:
            payload["current_stop"] = self.matcher.published_current
        payload["tracker"] = self._resolved or self._tracker_hint or self._configured or None
        payload["last_fix"] = _iso(self.matcher.last_fix.ts) if self.matcher.last_fix else None
        payload["boarded_time"] = _iso(self.matcher.boarded_ts) if self.matcher.boarded_ts else None
        payload["rider"] = self.slug
        payload["person"] = self.person
        payload["origin"] = None if not self.matcher.expected else self.matcher.expected.get("origin")
        payload["friendly_name_rider"] = self._friendly_name()
        payload["entity_picture"] = self._entity_picture()
        return payload

    def _friendly_name(self) -> str:
        for entity in (self.person, self._resolved, self._tracker_hint, self._configured):
            if not entity:
                continue
            state = self.hass.states.get(entity)
            if state is None:
                continue
            name = getattr(state, "name", None) or state.attributes.get("friendly_name")
            if name:
                return str(name)
        return self.slug

    def _entity_picture(self) -> str | None:
        """Person picture, then the tracker. Read every update so a new avatar shows up."""
        for entity in (self.person, self._resolved, self._tracker_hint, self._configured):
            if not entity:
                continue
            state = self.hass.states.get(entity)
            if state is None:
                continue
            picture = state.attributes.get("entity_picture")
            if picture:
                return str(picture)
        return None

    async def async_start(self) -> None:
        """Listen only when a tracker is configured."""
        self._read_options()
        if not self._configured or self._subscribed == self._configured:
            return
        self._subscribed = self._configured
        self._watch(self._configured)
        self._watch_destination()
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
        self._watch_destination()
        self._push()
        self._sync_fast()

    def _destination_entity(self) -> str:
        mine = rider_cfg_row(self.entry.options, self.slug, self.person, self._tracker_hint or self._resolved, self.key)
        entity = str(mine.get("destination_entity") or "").strip()
        if entity:
            return entity
        from collections.abc import Mapping

        opt = self.entry.options if isinstance(self.entry.options, Mapping) else {}
        return str(opt.get("destination_entity") or "").strip()

    def _watch_destination(self) -> None:
        entity = self._destination_entity()
        if not entity or entity == self._dest_entity or entity in self._watched:
            self._dest_entity = entity or self._dest_entity
            return
        self._dest_entity = entity
        self._watched.add(entity)
        self._unsubs.append(async_track_state_change_event(self.hass, [entity], self._on_destination))

    @callback
    def _on_destination(self, event) -> None:
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        previous = "" if old is None else getattr(old, "state", "")
        current = "" if new is None else getattr(new, "state", "")
        if not should_republish_destination(bool(self.matcher.riding), previous, current):
            return
        self.hass.async_create_task(self.async_refresh_alight())

    async def async_refresh_alight(self) -> None:
        """Recompute the stop the rider gets off and publish it."""
        try:
            if self.matcher.riding:
                await self._refresh_remaining(force=True)
            self._emit()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("SEPTA alight refresh failed")

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

    def _home_station(self) -> str:
        return rider_home(self.entry.options, self.entry.data, self.slug, self.person, self._tracker_hint or self._resolved, self.key)

    def _alight_choice(self, order: list[str], current: str | None) -> tuple[str | None, str, list[dict]]:
        options = self.entry.options
        data = self.entry.data
        mine = rider_cfg_row(options, self.slug, self.person, self._tracker_hint or self._resolved, self.key)
        board = getattr(self.coordinator, "dynamic", None)
        manual = getattr(board, "_manual_dest", None) if board is not None else None
        service = ""
        if isinstance(manual, dict):
            service = str(manual.get(self.slug) or manual.get(self.key) or "").strip()
        entity = str(mine.get("destination_entity") or "").strip()
        if not entity:
            from collections.abc import Mapping

            opt = options if isinstance(options, Mapping) else {}
            entity = str(opt.get("destination_entity") or "").strip()
        select = ""
        if entity:
            state = self.hass.states.get(entity)
            select = "" if state is None else str(state.state or "").strip()
        calendar = ""
        if board is not None:
            pack = getattr(board, "_current", None)
            row = pack.get(self.slug) if isinstance(pack, dict) else None
            if isinstance(row, dict) and str(row.get("destination_source") or "") == "calendar":
                calendar = str(row.get("destination") or "")
        default = str(mine.get("default_destination") or "").strip()
        if not default:
            from collections.abc import Mapping

            opt = options if isinstance(options, Mapping) else {}
            raw = data if isinstance(data, Mapping) else {}
            default = str(opt.get("destination") or raw.get("destination") or "").strip()
        service_at = None
        if isinstance(manual, dict):
            service, service_at = dest_parts(manual.get(self.slug) or manual.get(self.key))
        select_at = None
        if entity:
            state = self.hass.states.get(entity)
            select = "" if state is None else str(state.state or "").strip()
            changed = None if state is None else getattr(state, "last_changed", None)
            if changed is not None:
                try:
                    select_at = changed.timestamp()
                except (AttributeError, OSError, ValueError):
                    select_at = None
        return alight_plan(
            order,
            current,
            expected=self.matcher.expected,
            leg=self.matcher.leg,
            home=self._home_station(),
            service=service or None,
            select=select or None,
            calendar=calendar or None,
            default=default or None,
            service_at=service_at,
            select_at=select_at,
            boarded_ts=self.matcher.boarded_ts,
        )

    def _route_tables(self) -> tuple[dict, dict]:
        keeper = getattr(self.coordinator, "rail_schedule", None)
        shapes = getattr(keeper, "shapes", None) if keeper is not None else None
        routes = shapes.get("routes") if isinstance(shapes, dict) else {}
        return routes if isinstance(routes, dict) else {}, _LINE_NAMES

    def _name_line(self, code: object) -> tuple[str | None, str | None]:
        text = str(code or "").strip()
        if not text:
            return None, None
        routes, names = self._route_tables()
        title = line_title(text, routes, names)
        if title and title != text:
            return title, text
        return title, None

    def _remember_through(self, train: Train, current: object, nxt: object) -> None:
        full = remaining_from_timetable(cached_schedule(), train.trainno, datetime.now(NY).weekday(), None, None, None, None)
        code, where = through_change(full, current, nxt)
        title, short = self._name_line(code)
        self.matcher.through_line = title
        self.matcher.through_line_code = short
        self.matcher.through_at = where

    def _publish_stops(self, rows: list[dict], train: Train, source: str, order: list[str]) -> None:
        late = int(train.late or 0)
        home = self._home_station()
        self.matcher.home_station = home
        self.matcher.delay_min = late
        alight, alight_source, checked = self._alight_choice(order, train.currentstop)
        if alight_source != getattr(self, "_last_alight_source", None):
            self._last_alight_source = alight_source
            _LOGGER.debug("SEPTA alight %s %s", alight_source, checked)
        self.matcher.alight_checked = checked
        delayed = apply_delay(list(rows), late)
        keeper = getattr(self.coordinator, "rail_schedule", None)
        cache = getattr(keeper, "shapes", None) if keeper is not None else None
        train_stops = []
        points = []
        try:
            info = lookup_train(cache, train.trainno)
            train_stops = list((info or {}).get("stops") or [])
            points = list((info or {}).get("points") or [])
        except Exception:  # noqa: BLE001
            train_stops = []
            points = []
        if points:
            self.matcher.set_route_shape(points, train.trainno)
        try:
            from .ride import _load_geo

            geo = _load_geo()
        except Exception:  # noqa: BLE001
            geo = {}
        delayed = annotate_coords(delayed, train_stops, geo)
        marked = finish_remaining(delayed, alight)
        delayed = marked["rows"]
        self.matcher.alight_station = alight
        self.matcher.alight_source = alight_source
        self.matcher.alight_est = marked["alight_est"]
        self.matcher._stop_rows = delayed
        now_ny = datetime.now(NY)
        fresh = not position_is_stale(train, self.matcher._trace.get(train.trainno))
        trimmed = trim_passed(
            delayed,
            now_ny.hour * 60 + now_ny.minute,
            train.currentstop,
            train.nextstop,
            train.lat if fresh else None,
            train.lon if fresh else None,
            line_points=self.matcher._line_points,
        )
        self._remaining = trimmed["remaining"]
        self.matcher.remaining_stops = self._remaining
        self.matcher.stop_source = trimmed["stop_source"]
        self.matcher.published_current = trimmed["current_stop"]
        self.matcher.published_next = trimmed["next_stop"]
        published = finish_remaining(trimmed["remaining"], alight)
        self._remaining = published["rows"]
        self.matcher.remaining_stops = self._remaining
        self.matcher.alight_est = published["alight_est"] if published["alight_est"] is not None else self.matcher.alight_est
        self._remaining_source = source
        self._remaining_late = late

    async def _refresh_remaining(self, force: bool = False) -> None:
        train = self.matcher.riding_train
        if train is None:
            self._remaining = []
            self.matcher.remaining_stops = []
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
            order = [str(row.get("station") or "") for row in self._rr_raw]
            rows = remaining_stops(self._rr_raw, train.currentstop, train.nextstop, None)
            self._remember_through(train, train.currentstop, train.nextstop)
            self._publish_stops(rows, train, "rrschedules", order)
            return
        now_ny = datetime.now(NY)
        minutes = now_ny.hour * 60 + now_ny.minute
        full = remaining_from_timetable(cached_schedule(), train.trainno, now_ny.weekday(), None, None, None, None)
        code, where = through_change(full, train.currentstop, train.nextstop)
        title, short = self._name_line(code)
        self.matcher.through_line = title
        self.matcher.through_line_code = short
        self.matcher.through_at = where
        rows = remaining_from_timetable(
            cached_schedule(),
            train.trainno,
            now_ny.weekday(),
            minutes,
            train.currentstop,
            train.nextstop,
            None,
        )
        self._publish_stops(rows, train, "timetable", [row.get("station") or "" for row in full])

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
            marked = finish_remaining(self._remaining, self.matcher.alight_station)
            data["remaining_stops"] = marked["rows"]
            data["alight_index"] = marked["alight_index"]
            data["stops_to_alight"] = marked["stops_to_alight"]
            if marked["alight_est"] is not None:
                data["alight_est"] = marked["alight_est"]
            if marked["rows"]:
                data["next_stop"] = marked["rows"][0].get("station") or data.get("next_stop")
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
            if event.kind == "exited":
                self.hass.bus.async_fire(
                    "septa_live_ride_ended",
                    {
                        "reason": data.get("reason") or data.get("ended_reason"),
                        "train": data.get("train"),
                        "line": data.get("line"),
                        "boarded_at": data.get("boarded_at"),
                        "exited_at": data.get("exited_at"),
                        "duration": data.get("duration"),
                        "position_source": data.get("position_source"),
                        "stale_gps": data.get("stale_gps"),
                        "final_destination": data.get("final_destination"),
                        "ended_at": data.get("ended_at"),
                        "rider": data.get("rider"),
                        "entry_id": data.get("entry_id"),
                    },
                )
                dynamic = getattr(self.coordinator, "dynamic", None)
                if dynamic is not None:
                    self.hass.async_create_task(dynamic.async_refresh(force=False, only_slug=self.slug or None))
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


def _gps_ts(state) -> float | None:
    """Tracker GPS time when the companion app provides one. Otherwise None."""
    attrs = getattr(state, "attributes", None) or {}
    for key in ("gps_timestamp", "timestamp", "last_seen", "last_seen_at"):
        raw = attrs.get(key)
        if raw in (None, ""):
            continue
        if hasattr(raw, "timestamp"):
            try:
                return float(raw.timestamp())
            except Exception:  # noqa: BLE001
                continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            text = str(raw).strip()
            if not text:
                continue
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
    return None


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
        ts=_gps_ts(state) or _state_ts(state),
    )


def _fix_accepted(fix: Fix, matcher: RideMatcher) -> bool:
    if fix.acc_m is not None and fix.acc_m > matcher.max_accuracy_m:
        return False
    kind, prepared = classify_fix(fix, matcher.last_fix, time.time())
    if kind != "ok":
        return False
    if time.time() - prepared.ts > matcher.max_fix_age_s:
        return False
    return True
