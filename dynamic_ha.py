"""Home Assistant glue for Going Home and day trains.

The decisions live in dynamic.py. This module only talks to trackers,
calendars, the coordinator's HTTP session, and the config directory.
"""

from __future__ import annotations

import json
import logging
import time
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .const import (
    CONF_DAY_WINDOW,
    CONF_DEFAULT_CITY,
    CONF_DESTINATION,
    CONF_EVENT_BUFFER,
    CONF_GEOCODE,
    CONF_GOING_HOME_COUNT,
    CONF_HOME_STATION,
    CONF_MAX_TRAINS,
    CONF_NEAR_RADIUS,
    CONF_RIDE_MAX_ACCURACY,
    CONF_RIDERS_CFG,
    CONF_STATION,
    CONF_TRANSFER_MIN,
    DEFAULT_DAY_WINDOW,
    DEFAULT_EVENT_BUFFER,
    DEFAULT_GOING_HOME_COUNT,
    DEFAULT_MAX_TRAINS,
    DEFAULT_NEAR_RADIUS,
    DEFAULT_RIDE_MAX_ACCURACY,
    DEFAULT_TRANSFER_MIN,
    DOMAIN,
    GTFS_RAIL_API,
    LIVE_WINDOW_MIN,
    NTA_URL,
)
from .coordinator import NY, cached_schedule, nta_station
from .dynamic import (
    build_itineraries,
    builtin_place,
    cap_trains,
    indexed_stops,
    match_station,
    merge_nta,
    overlay_live,
    parse_valid_until,
    pick_fix,
    present_row,
    resolve_destination,
    resolve_origin,
    round_coord,
    select_schedule,
    station_names,
    suggest_itinerary,
    timetable_allowed,
    watch_entities,
    zone_station,
    ORIGIN_MAX_AGE_S,
    gtfs_tables_to_schedule,
)
from .ids import dynamic_key
from .ride import configured_riders, dedupe_riders
from .trips import parse_next_to_arrive, station_key

_LOGGER = logging.getLogger(__name__)
_USER_AGENT = "septa_live/1.13.1 (Home Assistant)"
_GEOCODE_GAP = 0.0


def _blank_payload(rider: str, home: str) -> dict:
    return {
        "rider": rider or None,
        "origin": None,
        "origin_lat": None,
        "origin_lon": None,
        "origin_source": None,
        "origin_distance_m": None,
        "origin_skip_reason": None,
        "origin_entity": None,
        "origin_fix_lat": None,
        "origin_fix_lon": None,
        "origin_fix_accuracy": None,
        "origin_fix_age_s": None,
        "home_station": home or None,
        "destination": None,
        "destination_source": None,
        "updated": None,
        "source": None,
        "reason": None,
        "error": None,
        "trains": [],
        "trains_total": 0,
        "state_minutes": None,
        "state_train": None,
        "event": None,
        "suggested": None,
        "suggested_train": None,
        "buffer_min": None,
        "schedule_valid_until": None,
        "schedule_source": None,
    }


def _download_gtfs(cache_file: Path) -> dict | None:
    """Download SEPTA's public rail GTFS at most once a day. Runs off the loop."""
    now = time.time()
    if cache_file.exists() and now - cache_file.stat().st_mtime < 86400:
        try:
            saved = json.loads(cache_file.read_text())
            schedule = saved.get("schedule") if isinstance(saved, dict) else None
            if isinstance(schedule, dict) and schedule.get("stations"):
                return schedule
        except (OSError, json.JSONDecodeError):
            pass
    try:
        request = Request(GTFS_RAIL_API, headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=30) as response:
            release = json.loads(response.read().decode())
        asset = ""
        for item in release.get("assets") or []:
            url = str(item.get("browser_download_url") or "")
            if url.endswith(".zip"):
                asset = url
                break
        if not asset:
            return None
        packed = Request(asset, headers={"User-Agent": _USER_AGENT})
        with urlopen(packed, timeout=60) as response:
            blob = response.read()
        files = _rail_texts(blob)
        if "stops" not in files or "stop_times" not in files:
            return None
        schedule = gtfs_tables_to_schedule(files)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"fetched_at": now, "schedule": schedule}))
        return schedule
    except Exception:  # noqa: BLE001
        _LOGGER.debug("SEPTA GTFS refresh failed", exc_info=True)
        return None


def _rail_texts(blob: bytes) -> dict[str, str]:
    wanted = {"stops.txt": "stops", "trips.txt": "trips", "stop_times.txt": "stop_times", "calendar.txt": "calendar", "feed_info.txt": "feed_info"}
    found: dict[str, str] = {}
    with zipfile.ZipFile(BytesIO(blob)) as outer:
        names = outer.namelist()
        inner = next((name for name in names if name.endswith("google_rail.zip")), "")
        if inner:
            blob = outer.read(inner)
            with zipfile.ZipFile(BytesIO(blob)) as rail:
                names = rail.namelist()
                source = rail
                _read_zip(source, names, wanted, found)
        else:
            _read_zip(outer, names, wanted, found)
    return found


def _read_zip(archive, names, wanted, found) -> None:
    for name in names:
        base = name.rsplit("/", 1)[-1]
        key = wanted.get(base)
        if key and key not in found:
            found[key] = archive.read(name).decode("utf-8", "replace")


class DynamicBoard:
    """Resolved Going Home and day-train payloads for every rider."""

    def __init__(self, hass: HomeAssistant, coordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.results: dict[str, dict] = {}
        self._current: dict[str, str] = {}
        self._manual_origin: dict[str, str] = {}
        self._manual_dest: dict[str, str] = {}
        self._last_origin: dict[str, str] = {}
        self._last_seen_at: dict[str, float] = {}
        self._geo_cache: dict[str, tuple[float, float] | None] = {}
        self._schedule: dict = {"stations": {}}
        self._schedule_source = "bundled"
        self._stops: list[dict] = []
        self._names: list[str] = []
        self._warned = False
        self._unsubs: list = []
        self._store = Store(hass, 1, f"{DOMAIN}_dynamic_{coordinator.entry.entry_id}")
        self._cache_file = Path(hass.config.path(".storage", f"{DOMAIN}_schedule.json"))

    def async_stop(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001
                pass
        self._unsubs.clear()

    async def async_prepare(self) -> None:
        await self.hass.async_add_executor_job(self._load_local)
        await self._load_store()
        self._listen()

    def reload_schedule(self) -> None:
        self._load_local()

    def _load_local(self) -> None:
        from .ride import _load_geo

        geo = _load_geo()
        bundled = cached_schedule()
        keeper = getattr(self.coordinator, "rail_schedule", None)
        book = getattr(keeper, "book", None)
        if book is not None and isinstance(book.schedule, dict) and book.schedule.get("stations"):
            self._schedule = book.schedule
            self._schedule_source = book.timetable_source()
        else:
            cached = None
            if self._cache_file.exists():
                try:
                    saved = json.loads(self._cache_file.read_text())
                    cached = saved.get("schedule") if isinstance(saved, dict) else None
                except (OSError, json.JSONDecodeError):
                    cached = None
            chosen, source = select_schedule(bundled, cached, datetime.now(NY).date())
            self._schedule = chosen if isinstance(chosen, dict) else {"stations": {}}
            self._schedule_source = source
        base = self._schedule if isinstance(self._schedule, dict) and self._schedule.get("stations") else bundled
        self._stops = indexed_stops(base if isinstance(base, dict) else {}, geo if isinstance(geo, dict) else {})
        self._names = station_names(self._schedule, geo if isinstance(geo, dict) else {})
        if self._schedule_source in {"expired", "missing"} and not self._warned:
            self._warned = True
            _LOGGER.warning(
                "SEPTA timetable is %s. Day trains are using live NextToArrive only until a schedule refresh succeeds",
                self._schedule_source,
            )

    async def _load_store(self) -> None:
        try:
            saved = await self._store.async_load()
        except Exception:  # noqa: BLE001
            saved = None
        if not isinstance(saved, dict):
            return
        self._manual_origin = {str(k): str(v) for k, v in (saved.get("origin") or {}).items() if v}
        self._manual_dest = {str(k): str(v) for k, v in (saved.get("destination") or {}).items() if v}
        self._last_origin = {str(k): str(v) for k, v in (saved.get("last") or {}).items() if v}

    async def _save_store(self) -> None:
        try:
            await self._store.async_save(
                {"origin": self._manual_origin, "destination": self._manual_dest, "last": self._last_origin}
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("SEPTA dynamic store was not saved")

    def remember_last(self, slug: str, origin: str) -> None:
        if slug and origin and slug not in self._last_origin:
            self._last_origin[slug] = origin

    def options(self) -> dict:
        entry = self.coordinator.entry
        opt = entry.options
        data = entry.data

        def integer(key: str, default: int, low: int, high: int) -> int:
            try:
                value = int(opt.get(key, default))
            except (TypeError, ValueError):
                value = default
            return min(high, max(low, value))

        return {
            "home_station": str(opt.get(CONF_HOME_STATION) or data.get(CONF_STATION) or "").strip(),
            "default_city_station": str(
                opt.get(CONF_DEFAULT_CITY) or opt.get(CONF_DESTINATION) or data.get(CONF_DESTINATION) or ""
            ).strip(),
            "near_radius_m": integer(CONF_NEAR_RADIUS, DEFAULT_NEAR_RADIUS, 200, 5000),
            "going_home_count": integer(CONF_GOING_HOME_COUNT, DEFAULT_GOING_HOME_COUNT, 1, 20),
            "transfer_min": integer(CONF_TRANSFER_MIN, DEFAULT_TRANSFER_MIN, 0, 30),
            "event_buffer_min": integer(CONF_EVENT_BUFFER, DEFAULT_EVENT_BUFFER, 0, 180),
            "day_window": str(opt.get(CONF_DAY_WINDOW) or DEFAULT_DAY_WINDOW),
            "geocode": bool(opt.get(CONF_GEOCODE)),
            "calendar_entity": str(opt.get("calendar_entity") or "").strip(),
            "max_trains": integer(CONF_MAX_TRAINS, DEFAULT_MAX_TRAINS, 1, 120),
            "riders_cfg": opt.get(CONF_RIDERS_CFG) if isinstance(opt.get(CONF_RIDERS_CFG), dict) else {},
            "max_accuracy": float(
                opt.get(CONF_RIDE_MAX_ACCURACY, data.get(CONF_RIDE_MAX_ACCURACY, DEFAULT_RIDE_MAX_ACCURACY))
                or DEFAULT_RIDE_MAX_ACCURACY
            ),
        }

    def specs(self) -> list[dict]:
        entry = self.coordinator.entry
        raw = configured_riders(entry.options, entry.data)
        links: dict[str, str] = {}
        try:
            people = self.hass.states.async_all("person")
        except Exception:  # noqa: BLE001
            people = []
        for state in people or []:
            source = state.attributes.get("source")
            if isinstance(source, str) and source.startswith("device_tracker."):
                links[state.entity_id] = source
        found = dedupe_riders(raw, links)
        if not found:
            return [{"slug": "", "primary": True, "configured": "", "tracker": "", "person": None}]
        return found

    def _cfg(self, slug: str, opt: dict) -> dict:
        raw = (opt["riders_cfg"] or {}).get(slug) or {}
        if not isinstance(raw, dict):
            raw = {}

        def pick(key: str, fallback: str) -> str:
            value = str(raw.get(key) or "").strip()
            return value or fallback

        def flag(key: str) -> bool:
            if key not in raw:
                return True
            return bool(raw.get(key))

        return {
            "home_station": pick("home_station", opt["home_station"]),
            "city_station": pick("city_station", opt["default_city_station"]),
            "default_destination": pick("default_destination", opt["default_city_station"]),
            "destination_entity": str(raw.get("destination_entity") or "").strip(),
            "calendar_entity": pick("calendar_entity", opt.get("calendar_entity") or ""),
            "enabled_going_home": flag("enabled_going_home"),
            "enabled_day_trains": flag("enabled_day_trains"),
        }

    def _listen(self) -> None:
        entities = watch_entities(self.specs())
        for spec in self.specs():
            cfg = self._cfg(spec.get("slug") or "", self.options())
            for key in ("destination_entity", "calendar_entity"):
                entity = str(cfg.get(key) or "")
                if "." in entity:
                    entities.append(entity)
        entities = list(dict.fromkeys(entities))
        signature = tuple(entities)
        if signature == getattr(self, "_listened", None):
            return
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001
                pass
        self._unsubs.clear()
        self._listened = signature
        if not entities:
            return

        @callback
        def _changed(event) -> None:
            self.hass.async_create_task(self._on_tracker(event))

        self._unsubs.append(async_track_state_change_event(self.hass, entities, _changed))

    async def _on_tracker(self, event) -> None:
        self._listen()
        entity = event.data.get("entity_id")
        for spec in self.specs():
            watched = {spec.get("configured"), spec.get("tracker"), spec.get("person")}
            if entity not in watched:
                continue
            slug = spec.get("slug") or ""
            before = self._current.get(slug)
            opt = self.options()
            cfg = self._cfg(slug, opt)
            if self._tracker(spec).get("at_home"):
                self._manual_origin.pop(slug, None)
            resolved = self._origin(spec, cfg, opt)
            if resolved.get("origin") != before:
                self._current[slug] = resolved.get("origin") or ""
                await self.async_refresh(force=False, only_slug=slug)
                return

    def _state_fix(self, entity: str) -> dict | None:
        state = self.hass.states.get(entity) if entity else None
        if state is None:
            return None
        attrs = getattr(state, "attributes", None) or {}

        def num(key: str) -> float | None:
            value = attrs.get(key)
            if value in (None, ""):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        updated = getattr(state, "last_updated", None)
        stamp = None
        try:
            if updated is not None:
                stamp = float(updated.timestamp())
        except (AttributeError, TypeError, ValueError, OSError):
            stamp = None
        text = str(getattr(state, "state", "") or "")
        return {
            "entity": entity,
            "state": text,
            "at_home": text.lower() == "home",
            "lat": num("latitude"),
            "lon": num("longitude"),
            "accuracy": num("gps_accuracy"),
            "updated": stamp,
        }

    def _tracker(self, spec: dict) -> dict:
        rows = []
        seen: set[str] = set()
        for key in ("tracker", "person", "configured"):
            entity = str(spec.get(key) or "")
            if not entity or entity in seen:
                continue
            seen.add(entity)
            row = self._state_fix(entity)
            if row:
                rows.append(row)
        empty = {
            "at_home": False,
            "lat": None,
            "lon": None,
            "accuracy": None,
            "zone": None,
            "origin_entity": None,
            "age_s": None,
        }
        if not rows:
            return empty
        chosen = pick_fix(rows)
        zone = None
        for row in rows:
            hit = zone_station(row.get("state"), self._names)
            if hit:
                zone = hit
                if chosen.get("lat") is None:
                    chosen = row
                break
        if zone is None:
            for row in rows:
                text = str(row.get("state") or "")
                if text.lower() in {"home", "not_home", "unknown", "unavailable"}:
                    continue
                for zone_row in self._zones():
                    zname = str(zone_row.get("name") or "")
                    if zname and station_key(zname) == station_key(text):
                        zone = match_station(zname, self._names) or match_station(text, self._names)
                        if zone and chosen.get("lat") is None:
                            chosen = row
                        break
                if zone:
                    break
        age = None
        if isinstance(chosen.get("updated"), (int, float)):
            age = max(0.0, time.time() - float(chosen["updated"]))
        return {
            "at_home": bool(chosen.get("at_home")) and not zone,
            "lat": chosen.get("lat"),
            "lon": chosen.get("lon"),
            "accuracy": chosen.get("accuracy"),
            "zone": zone,
            "origin_entity": chosen.get("entity"),
            "age_s": age,
        }

    def _origin(self, spec: dict, cfg: dict, opt: dict) -> dict:
        slug = spec.get("slug") or ""
        fix = self._tracker(spec)
        age = fix.get("age_s")
        stale = age is not None and age > ORIGIN_MAX_AGE_S
        try:
            ride_limit = float(opt["max_accuracy"])
        except (TypeError, ValueError):
            ride_limit = 100.0
        return resolve_origin(
            manual=self._manual_origin.get(slug),
            at_home=bool(fix["at_home"]),
            lat=fix["lat"],
            lon=fix["lon"],
            accuracy=fix["accuracy"],
            max_accuracy=max(ride_limit, 500.0),
            stops=self._stops,
            radius_m=opt["near_radius_m"],
            current=self._current.get(slug),
            city_station=cfg["city_station"],
            home_station=cfg["home_station"],
            last=self._last_origin.get(slug),
            zone=fix.get("zone"),
            stale=stale,
            origin_entity=fix.get("origin_entity"),
            fix_age_s=None if age is None else round(float(age), 1),
            ride_origin=self._ride_origin(slug),
            last_recent=self._last_is_recent(slug),
        )

    def _last_is_recent(self, slug: str) -> bool:
        stamp = self._last_seen_at.get(slug)
        if stamp is None:
            return False
        return time.time() - float(stamp) <= 30 * 60

    def _ride_origin(self, slug: str) -> str | None:
        ride = getattr(self.coordinator, "ride", None)
        riders = getattr(ride, "riders", None) if ride is not None else None
        if not riders:
            return None
        for rider in riders.values():
            same = (slug and getattr(rider, "slug", None) == slug) or (not slug and getattr(rider, "is_primary", False))
            if not same:
                continue
            matcher = getattr(rider, "matcher", None)
            if matcher is None or not getattr(matcher, "riding", False):
                return None
            if getattr(matcher, "alight_station", None):
                return str(matcher.alight_station)
            if getattr(matcher, "published_next", None):
                return str(matcher.published_next)
            train = getattr(matcher, "riding_train", None)
            if train is not None and getattr(train, "nextstop", None):
                return str(train.nextstop)
        return None

    def _event(self, entity: str, now: datetime) -> dict | None:
        if not entity:
            return None
        state = self.hass.states.get(entity)
        if state is None:
            return None
        from .trips import _parse_iso

        start = _parse_iso(state.attributes.get("start_time") or state.attributes.get("start"))
        if start is None:
            return None
        base = now.astimezone(start.tzinfo) if now.tzinfo else now
        if start < base - timedelta(minutes=30):
            return None
        summary = state.attributes.get("message") or state.attributes.get("summary") or ""
        return {
            "summary": str(summary),
            "start": start.isoformat(),
            "location": state.attributes.get("location"),
            "latitude": state.attributes.get("latitude"),
            "longitude": state.attributes.get("longitude"),
        }

    def _zones(self) -> list[dict]:
        try:
            states = self.hass.states.async_all("zone")
        except Exception:  # noqa: BLE001
            states = []
        zones = []
        for state in states or []:
            zones.append(
                {
                    "name": state.attributes.get("friendly_name") or state.name,
                    "latitude": state.attributes.get("latitude"),
                    "longitude": state.attributes.get("longitude"),
                }
            )
        return zones

    async def _maybe_geocode(self, enabled: bool, event: dict | None) -> tuple[float, float] | None:
        if not enabled or not isinstance(event, dict):
            return None
        if event.get("latitude") not in (None, "") or not event.get("location"):
            return None
        if match_station(event.get("location"), self._names):
            return None
        place = builtin_place(event.get("location"))
        if place and (place.get("station") or place.get("lat") is not None):
            return None
        query = str(event.get("location"))
        if query in self._geo_cache:
            return self._geo_cache[query]
        global _GEOCODE_GAP
        wait = 1.0 - (time.time() - _GEOCODE_GAP)
        if wait > 0:
            import asyncio

            await asyncio.sleep(wait)
        _GEOCODE_GAP = time.time()
        try:
            async with self.coordinator.session.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": _USER_AGENT},
                timeout=15,
            ) as resp:
                payload = await resp.json()
            if payload:
                point = (float(payload[0]["lat"]), float(payload[0]["lon"]))
            else:
                point = None
        except Exception:  # noqa: BLE001
            point = None
        self._geo_cache[query] = point
        return point

    async def async_refresh(self, force: bool = False, only_slug: str | None = None) -> None:
        self._listen()
        opt = self.options()
        now = datetime.now(NY)
        until = parse_valid_until(self._schedule)
        for spec in self.specs():
            slug = spec.get("slug") or ""
            if only_slug is not None and slug != only_slug:
                continue
            cfg = self._cfg(slug, opt)
            origin = self._origin(spec, cfg, opt)
            if origin.get("origin") and origin.get("reason") != "at_home_station":
                self._current[slug] = origin["origin"]
            if origin.get("origin_source") in {"nearest", "zone"} and origin.get("origin"):
                self._last_origin[slug] = origin["origin"]
                self._last_seen_at[slug] = time.time()
            await self._fill(spec, cfg, opt, origin, now, until)
        await self._save_store()
        try:
            self.coordinator.async_update_listeners()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("SEPTA dynamic listener update skipped")

    async def _fill(self, spec, cfg, opt, origin, now, until) -> None:
        slug = spec.get("slug") or ""
        primary = bool(spec.get("primary")) or not slug
        rider = slug or None
        home = cfg["home_station"]
        going_key = dynamic_key("going_home", slug, primary)
        day_key = dynamic_key("day_trains", slug, primary)
        going = _blank_payload(rider, home)
        going.update(
            {
                "origin": origin.get("origin"),
                "origin_lat": origin.get("origin_lat"),
                "origin_lon": origin.get("origin_lon"),
                "origin_source": origin.get("origin_source"),
                "origin_distance_m": origin.get("origin_distance_m"),
                "origin_entity": origin.get("origin_entity"),
                "origin_fix_lat": origin.get("origin_fix_lat"),
                "origin_fix_lon": origin.get("origin_fix_lon"),
                "origin_fix_accuracy": origin.get("origin_fix_accuracy"),
                "origin_fix_age_s": origin.get("origin_fix_age_s"),
                "origin_skip_reason": origin.get("origin_skip_reason"),
                "reason": origin.get("reason"),
                "updated": now.isoformat(),
                "destination": home or None,
                "destination_source": "home",
            }
        )
        if not cfg["enabled_going_home"]:
            going["reason"] = "disabled"
        elif (
            not home
            or not origin.get("origin")
            or origin.get("reason") == "at_home_station"
            or station_key(origin.get("origin")) == station_key(home)
        ):
            going["reason"] = "at_home_station" if home and origin.get("origin") else (origin.get("reason") or "no_origin")
            going["trains"] = []
        else:
            live, error = await self.coordinator.async_cached_nta(
                origin["origin"], home, opt["going_home_count"], opt["transfer_min"], force=False
            )
            schedule_rows = []
            if timetable_allowed(self._schedule_source):
                schedule_rows = build_itineraries(
                    self._schedule,
                    origin["origin"],
                    home,
                    now.date(),
                    transfer_min=opt["transfer_min"],
                    now=now,
                    window="rest_of_day",
                )
            going["trains"] = merge_nta(live, schedule_rows, opt["going_home_count"], now)
            shown, total = cap_trains(going["trains"], opt["max_trains"])
            going["trains"] = shown
            going["trains_total"] = total
            going["source"] = "nta" if live else ("timetable" if schedule_rows else "nta")
            going["error"] = error
            if going["trains"]:
                minutes = going["trains"][0].get("minutes")
                going["state_minutes"] = None if minutes is None else max(0, int(minutes))
        self.results[going_key] = going

        event = self._event(cfg["calendar_entity"], now)
        geocoded = await self._maybe_geocode(opt["geocode"], event)
        entity_state = ""
        if cfg["destination_entity"]:
            state = self.hass.states.get(cfg["destination_entity"])
            entity_state = "" if state is None else str(state.state)
        dest = resolve_destination(
            manual=self._manual_dest.get(slug),
            entity_state=entity_state,
            event=event,
            default_station=cfg["default_destination"],
            names=self._names,
            stops=self._stops,
            zones=self._zones(),
            near_radius_m=opt["near_radius_m"],
            geocoded=geocoded,
        )
        day = _blank_payload(rider, home)
        day.update(
            {
                "origin": home or None,
                "origin_source": "home",
                "destination": dest.get("destination"),
                "destination_source": dest.get("destination_source"),
                "updated": now.isoformat(),
                "event": self._public_event(dest.get("event")),
                "buffer_min": opt["event_buffer_min"],
                "schedule_source": self._schedule_source,
                "schedule_valid_until": until.isoformat() if until else None,
            }
        )
        home_lat = next((stop["lat"] for stop in self._stops if station_key(stop["name"]) == station_key(home)), None)
        home_lon = next((stop["lon"] for stop in self._stops if station_key(stop["name"]) == station_key(home)), None)
        day["origin_lat"] = home_lat
        day["origin_lon"] = home_lon
        if not cfg["enabled_day_trains"]:
            day["reason"] = "disabled"
        elif not home or not dest.get("destination") or station_key(home) == station_key(dest.get("destination")):
            day["reason"] = "no_destination"
        else:
            live, error = await self.coordinator.async_cached_nta(
                home, dest["destination"], 10, opt["transfer_min"], force=False
            )
            if timetable_allowed(self._schedule_source):
                skeleton = build_itineraries(
                    self._schedule,
                    home,
                    dest["destination"],
                    now.date(),
                    transfer_min=opt["transfer_min"],
                    now=now,
                    window=opt["day_window"] if opt["day_window"] in {"today", "rest_of_day"} else "rest_of_day",
                )
                full = overlay_live(skeleton, live, now, LIVE_WINDOW_MIN)
                day["source"] = "timetable"
            else:
                full = [present_row(dict(row, live=True), now) for row in live]
                day["source"] = "nta"
            day["error"] = error
            start = None
            if isinstance(day["event"], dict):
                from .trips import _parse_iso

                start = _parse_iso(day["event"].get("start"))
            suggested = suggest_itinerary(full, start, opt["event_buffer_min"])
            day["suggested"] = suggested
            day["suggested_train"] = None if not suggested else suggested.get("train")
            shown, total = cap_trains(full, opt["max_trains"])
            day["trains"] = shown
            day["trains_total"] = total
            first = shown[0]["train"] if shown else None
            day["state_train"] = day["suggested_train"] or first
        self.results[day_key] = day

    def _public_event(self, event: dict | None) -> dict | None:
        if not isinstance(event, dict):
            return None
        return {
            "summary": event.get("summary") or "",
            "start": event.get("start"),
            "location": event.get("location"),
        }

    def known_station(self, name: str) -> str | None:
        return match_station(name, self._names) or match_station(name, list(self._names))

    async def set_origin(self, slug: str, station: str | None) -> None:
        if station:
            self._manual_origin[slug] = station
        else:
            self._manual_origin.pop(slug, None)
        await self.async_refresh(force=True, only_slug=slug)

    async def set_destination(self, slug: str, station: str | None) -> None:
        if station:
            self._manual_dest[slug] = station
        else:
            self._manual_dest.pop(slug, None)
        await self.async_refresh(force=True, only_slug=slug)

    def slug_for(self, name: str | None) -> str:
        ride = getattr(self.coordinator, "ride", None)
        if ride is not None and hasattr(ride, "rider_for"):
            rider = ride.rider_for(name)
            if rider is not None:
                return rider.slug if not rider.is_primary else rider.slug
        want = str(name or "").strip()
        if want in {"sensor.septa_going_home", "sensor.septa_day_trains"}:
            want = ""
        else:
            for prefix in (
                "sensor.septa_going_home_",
                "sensor.septa_day_trains_",
                "sensor.septa_my_train_",
                "binary_sensor.septa_riding_",
            ):
                if want.startswith(prefix):
                    want = want[len(prefix) :]
                    break
        specs = self.specs()
        if not want:
            primary = next((spec for spec in specs if spec.get("primary")), specs[0] if specs else {})
            return primary.get("slug") or ""
        for spec in specs:
            if want in {spec.get("slug"), spec.get("configured"), spec.get("person"), spec.get("tracker")}:
                return spec.get("slug") or ""
        return want

    def diagnostics(self) -> dict:
        until = parse_valid_until(self._schedule)
        riders = []
        for spec in self.specs():
            slug = spec.get("slug") or ""
            primary = bool(spec.get("primary")) or not slug
            going = self.results.get(dynamic_key("going_home", slug, primary)) or {}
            day = self.results.get(dynamic_key("day_trains", slug, primary)) or {}
            event = day.get("event") or {}
            riders.append(
                {
                    "slug": slug or "primary",
                    "home_station": going.get("home_station"),
                    "origin": going.get("origin"),
                    "origin_source": going.get("origin_source"),
                    "origin_lat": round_coord(going.get("origin_lat")),
                    "origin_lon": round_coord(going.get("origin_lon")),
                    "destination": day.get("destination"),
                    "destination_source": day.get("destination_source"),
                    "event_summary_length": len(str(event.get("summary") or "")),
                }
            )
        now = time.time()
        cache = []
        for key, item in (getattr(self.coordinator, "_nta_cache", {}) or {}).items():
            cache.append({"key": list(key), "age_s": int(now - item[0])})
        holds = [list(key) for key, until_ts in (getattr(self.coordinator, "_nta_hold", {}) or {}).items() if until_ts > now]
        return {
            "schedule_source": self._schedule_source,
            "schedule_valid_until": until.isoformat() if until else None,
            "riders": riders,
            "cache": cache,
            "nta_hold": holds,
        }
