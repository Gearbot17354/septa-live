"""SEPTA Transit integration."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers.event import async_call_later

from .bus_routes import BUS_ROUTES
from .ids import legacy_key, plan_registry_migration
from .const import (
    CONF_BUS_DEST,
    CONF_BUS_LINE,
    CONF_BUS_STOP,
    CONF_DESTINATION,
    CONF_EVENT_LOOKAHEAD,
    CONF_EVENT_WALK_SPEED,
    CONF_METRO_DEST,
    CONF_METRO_LINE,
    CONF_METRO_STATION,
    CONF_RAIL_LINE,
    CONF_RIDE_MATCHES,
    CONF_RIDE_MAX_ACCURACY,
    CONF_RIDE_MIN_SPEED,
    CONF_RIDE_RADIUS,
    CONF_RIDE_REQUEST,
    CONF_RIDE_TRACKER,
    CONF_SHOW_BUS,
    CONF_SHOW_METRO,
    CONF_SHOW_RAIL,
    CONF_SHOW_TROLLEY,
    CONF_SIDEBAR,
    CONF_STATION,
    CONF_TROLLEY_DEST,
    CONF_TROLLEY_LINE,
    CONF_TROLLEY_STATION,
    CONF_WALK,
    CONF_WATCHES,
    CONF_TRIPS,
    DOMAIN,
    METRO_STATIONS,
    PLATFORMS,
    SERVICE_LINES,
    STATIONS,
    TROLLEY_STATIONS,
)
from .coordinator import SeptaCoordinator, _LINE_NAMES, _ha_home, _load_schedule, slug
from .schema import (
    REFRESH_SCHEDULE,
    REFRESH_TRIPS,
    SET_EXPECTED,
    SIMULATE_RIDE,
    STATION_SERVICE,
    PLAN_TRIPS,
    WEBSOCKET_BOARD,
    WEBSOCKET_BUS,
    WEBSOCKET_OPTIONS,
    WEBSOCKET_PANEL,
    WEBSOCKET_PLAN,
    WEBSOCKET_DAY,
    WEBSOCKET_ROUTE,
)

_LOGGER = logging.getLogger(__name__)
_FRONTEND = f"{DOMAIN}_frontend_registered"
_CARD_JS = "septa-live-card.js"
_PANEL_JS = "septa-live-panel.js"
_PANEL_PATH = "septa-live"
_CARD_VERSION = "1.13.9"
_PANEL_SIG: tuple | None = None
_RELOADING: set[str] = set()


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    await _async_register_lovelace_cards(hass)
    websocket_api.async_register_command(hass, websocket_board)
    websocket_api.async_register_command(hass, websocket_panel)
    websocket_api.async_register_command(hass, websocket_options)
    websocket_api.async_register_command(hass, websocket_bus_picker)
    websocket_api.async_register_command(hass, websocket_route)
    websocket_api.async_register_command(hass, websocket_plan)
    websocket_api.async_register_command(hass, websocket_day_trains)
    _register_simulate(hass)
    return True


def _register_simulate(hass: HomeAssistant) -> None:
    """Replay fixes on a fresh matcher. The live riding sensor is not touched."""
    try:
        from homeassistant.core import SupportsResponse

        support = SupportsResponse.ONLY
    except ImportError:
        support = None

    async def _simulate(call):
        from .ride import Fix, Train, replay_fixes

        coordinator = (hass.data.get(DOMAIN) or {}).get(call.data.get("entry_id"))
        kwargs = {"radius_m": 300, "min_speed_mps": 15 * 0.44704, "need_matches": 2, "max_accuracy_m": 100}
        before = None
        matcher = None
        if coordinator is not None and getattr(coordinator, "ride", None) is not None:
            rider = coordinator.ride.rider_for(call.data.get("rider"))
            matcher = rider.matcher if rider is not None else coordinator.ride.matcher
            kwargs = {
                "radius_m": matcher.radius_m,
                "min_speed_mps": matcher.min_speed_mps,
                "need_matches": matcher.need_matches,
                "max_accuracy_m": matcher.max_accuracy_m,
                "preferred_line": matcher.preferred_line,
            }
            if call.data.get("expected_train"):
                kwargs["expected_train"] = call.data.get("expected_train")
            before = (matcher.riding, matcher.match_count, matcher.last_reason, id(matcher))
        trains = []
        for item in call.data.get("trainview") or []:
            if not isinstance(item, dict):
                continue
            try:
                trains.append(
                    Train(
                        trainno=str(item.get("trainno") or item.get("train") or ""),
                        lat=float(item["lat"]),
                        lon=float(item["lon"]),
                        heading=float(item["heading"]) if item.get("heading") is not None else None,
                        dest=str(item.get("dest") or ""),
                        line=str(item.get("line") or ""),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        samples = []
        for item in call.data.get("fixes") or []:
            if not isinstance(item, dict):
                continue
            try:
                sample_fix = Fix(
                    lat=float(item["lat"]),
                    lon=float(item["lon"]),
                    acc_m=float(item["acc"]) if item.get("acc") is not None else None,
                    speed_mps=float(item["speed"]) if item.get("speed") is not None else None,
                    course=float(item["course"]) if item.get("course") is not None else None,
                    ts=float(item["ts"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            samples.append(
                {
                    "fix": sample_fix,
                    "trains": trains,
                    "trains_ts": float(item.get("trains_ts", item["ts"])),
                }
            )
        result = replay_fixes(samples, **kwargs)
        if before is not None and matcher is not None:
            if (matcher.riding, matcher.match_count, matcher.last_reason, id(matcher)) != before:
                _LOGGER.error("SEPTA simulate_ride changed the live matcher")
        return result

    register_kwargs = {"schema": SIMULATE_RIDE}
    if support is not None:
        register_kwargs["supports_response"] = support
    hass.services.async_register(DOMAIN, "simulate_ride", _simulate, **register_kwargs)

    async def _refresh_trips(call):
        data = hass.data.get(DOMAIN) or {}
        wanted = str(call.data.get("entry_id") or "").strip()
        trip_id = str(call.data.get("trip_id") or "").strip() or None
        for entry_id, coordinator in data.items():
            if wanted and entry_id != wanted:
                continue
            if not hasattr(coordinator, "async_refresh_trips"):
                continue
            await coordinator.async_refresh_trips(force=True, trip_id=trip_id)

    hass.services.async_register(
        DOMAIN,
        "refresh_trips",
        _refresh_trips,
        schema=REFRESH_TRIPS,
    )

    async def _set_expected(call):
        data = hass.data.get(DOMAIN) or {}
        wanted = str(call.data.get("entry_id") or "").strip()
        hint = {
            "train": call.data.get("train"),
            "origin": call.data.get("origin"),
            "destination": call.data.get("destination"),
            "connection_train": call.data.get("connection_train"),
            "connection_station": call.data.get("connection_station"),
            "valid_until": call.data.get("valid_until"),
        }
        for entry_id, coordinator in data.items():
            if wanted and entry_id != wanted:
                continue
            ride = getattr(coordinator, "ride", None)
            if ride is None or not hasattr(ride, "rider_for"):
                continue
            rider = ride.rider_for(call.data.get("rider"))
            if rider is None:
                continue
            rider.apply_service_hint(hint)
            rider._push()

    hass.services.async_register(
        DOMAIN,
        "set_expected_train",
        _set_expected,
        schema=SET_EXPECTED,
    )

    async def _set_dynamic_station(call, which: str):
        from homeassistant.exceptions import ServiceValidationError

        from .dynamic import match_station

        data = hass.data.get(DOMAIN) or {}
        wanted = str(call.data.get("entry_id") or "").strip()
        raw = str(call.data.get("station") or "").strip()
        for entry_id, coordinator in data.items():
            if wanted and entry_id != wanted:
                continue
            board = getattr(coordinator, "dynamic", None)
            if board is None:
                continue
            station = None
            if raw:
                station = board.known_station(raw) or match_station(raw, list(STATIONS))
                if not station:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="unknown_station",
                        translation_placeholders={"station": raw},
                    )
            slug = board.slug_for(call.data.get("rider"))
            if which == "origin":
                await board.set_origin(slug, station)
            else:
                await board.set_destination(slug, station)

    async def _set_origin(call):
        await _set_dynamic_station(call, "origin")

    async def _set_destination_service(call):
        await _set_dynamic_station(call, "destination")

    hass.services.async_register(DOMAIN, "set_origin_station", _set_origin, schema=STATION_SERVICE)
    hass.services.async_register(DOMAIN, "set_destination", _set_destination_service, schema=STATION_SERVICE)

    async def _plan_trips(call):
        from datetime import datetime

        from .coordinator import NY
        from .dynamic import match_station, plan_query

        data = hass.data.get(DOMAIN) or {}
        wanted = str(call.data.get("entry_id") or "").strip()
        chosen = None
        for entry_id, coordinator in data.items():
            if wanted and entry_id != wanted:
                continue
            if getattr(coordinator, "dynamic", None) is not None:
                chosen = coordinator
                break
        if chosen is None:
            return {"error": "not_found"}
        board = chosen.dynamic
        opt = board.options()
        slug = board.slug_for(call.data.get("rider"))
        cfg = board._cfg(slug, opt)
        home = str(cfg.get("home_station") or opt.get("home_station") or "").strip()
        names = list(board._names or STATIONS)
        origin = match_station(call.data.get("origin"), names)
        if not origin:
            return {"error": "not_found"}
        destination = call.data.get("destination")
        if destination and not match_station(destination, names):
            return {"error": "not_found"}
        now = datetime.now(NY)
        live: list = []
        dest_name = match_station(destination, names) if destination else (match_station(home, names) or home)
        try:
            if dest_name:
                fetched, _error = await chosen.async_cached_nta(
                    origin, dest_name, int(call.data.get("count") or 8), opt["transfer_min"], force=False
                )
                live = fetched or []
        except Exception:  # noqa: BLE001
            live = []
        from functools import partial

        return await hass.async_add_executor_job(
            partial(
                plan_query,
                board._schedule,
                names,
                origin=origin,
                destination=destination,
                home=home,
                after=call.data.get("after"),
                arrive_by=call.data.get("arrive_by"),
                count=call.data.get("count") or 8,
                transfer_min=opt["transfer_min"],
                now=now,
                live_rows=live,
            )
        )

    hass.services.async_register(
        DOMAIN,
        "plan_trips",
        _plan_trips,
        schema=PLAN_TRIPS,
        supports_response=SupportsResponse.ONLY,
    )

    async def _refresh_schedule(call):
        from .schedule_ha import _KEEPER

        wanted = str(call.data.get("entry_id") or "").strip()
        force = bool(call.data.get("force"))
        data = hass.data.get(DOMAIN) or {}
        seen: set[int] = set()
        for entry_id, coordinator in list(data.items()):
            if wanted and entry_id != wanted:
                continue
            keeper = getattr(coordinator, "rail_schedule", None)
            if keeper is None or id(keeper) in seen:
                continue
            seen.add(id(keeper))
            await keeper.async_refresh(force=force)
        if not seen:
            keeper = hass.data.get(_KEEPER)
            if keeper is not None:
                await keeper.async_refresh(force=force)

    hass.services.async_register(DOMAIN, "refresh_schedule", _refresh_schedule, schema=REFRESH_SCHEDULE)


async def _async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Point old unique ids at the config entry and put _2 names back."""
    try:
        from homeassistant.helpers import entity_registry as er
    except ImportError:
        return
    registry = er.async_get(hass)
    station = str(entry.data.get(CONF_STATION) or "")
    primary_slug = None
    try:
        from .ride import configured_riders, dedupe_riders

        riders = dedupe_riders(configured_riders(entry.options, entry.data), {})
        primary = next((item for item in riders if item.get("primary")), None)
        primary_slug = None if primary is None else primary.get("slug")
    except Exception:  # noqa: BLE001
        primary_slug = None
    try:
        current = er.async_entries_for_config_entry(registry, entry.entry_id)
    except Exception:  # noqa: BLE001
        return
    items = [
        {"unique_id": item.unique_id, "entity_id": item.entity_id, "domain": item.domain}
        for item in current
    ]
    for action in plan_registry_migration(entry.entry_id, station, items, primary_slug):
        try:
            if action["op"] == "remove":
                registry.async_remove(action["entity_id"])
            elif action["op"] == "unique_id":
                registry.async_update_entity(action["entity_id"], new_unique_id=action["unique_id"])
            elif action["op"] == "rename" and registry.async_get(action["new_entity_id"]) is None:
                registry.async_update_entity(action["entity_id"], new_entity_id=action["new_entity_id"])
            elif action["op"] == "skip":
                _LOGGER.warning(
                    "SEPTA left %s unchanged because %s is already in use",
                    action.get("entity_id"),
                    action.get("new_entity_id"),
                )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("SEPTA entity id migration skipped for %s", action.get("entity_id"))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await _async_migrate_entity_ids(hass, entry)
    from .ride import async_preload

    await async_preload(hass)
    await hass.async_add_executor_job(_load_schedule)
    await _async_register_lovelace_cards(hass)
    coordinator = SeptaCoordinator(hass, entry)
    from .schedule_ha import async_attach_schedule, audit_saved_stations

    try:
        await async_attach_schedule(hass, coordinator)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SEPTA timetable did not start")
    from .ride_ha import RideController
    from .dynamic_ha import DynamicBoard

    coordinator.ride = RideController(hass, coordinator)
    coordinator.dynamic = DynamicBoard(hass, coordinator)
    await coordinator.dynamic.async_prepare()
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    coordinator.sidebar_on = _sidebar_enabled(entry)
    entry.async_on_unload(coordinator.start_trip_poller())
    entry.async_on_unload(coordinator.dynamic.async_stop)
    try:
        await coordinator.ride.async_start()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SEPTA ride tracker did not start")
    entry.async_on_unload(coordinator.ride.async_stop)

    def _push() -> None:
        hass.bus.async_fire("septa_live_updated", {"entry_id": entry.entry_id})

    coordinator.async_add_listener(_push)
    entry.async_on_unload(lambda: coordinator.async_remove_listener(_push))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    try:
        audit_saved_stations(hass, entry)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("SEPTA station audit skipped", exc_info=True)
    await _async_sync_panel(hass)
    return True


def _card_source() -> Path:
    return Path(__file__).parent / "www" / _CARD_JS


async def _async_register_lovelace_cards(hass: HomeAssistant) -> None:
    source = _card_source()
    if not source.exists():
        _LOGGER.warning("SEPTA Transit card file missing at %s", source)
        return

    await hass.async_add_executor_job(_install_local_card, hass, source)

    url_local = f"/local/{_CARD_JS}?v={_CARD_VERSION}"
    url_int = f"/{DOMAIN}/{_CARD_JS}?v={_CARD_VERSION}"

    www = source.parent
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"/{DOMAIN}", str(www), False)]
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("SEPTA Transit static path already set or unavailable: %s", err)

    already = bool(hass.data.get(_FRONTEND))
    if not already:
        try:
            from homeassistant.components.frontend import add_extra_js_url

            add_extra_js_url(hass, url_local)
            add_extra_js_url(hass, url_int)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("SEPTA Transit extra JS url failed: %s", err)

    registered = await _async_ensure_lovelace_resource(hass, url_local)
    hass.data[_FRONTEND] = True
    if registered:
        _LOGGER.info("SEPTA Transit Lovelace cards registered (%s)", url_local)
    else:
        _LOGGER.info(
            "SEPTA Transit card served at %s — add a Lovelace resource if it does not appear",
            url_local,
        )

        async def _retry(_now) -> None:
            await _async_ensure_lovelace_resource(hass, url_local)

        async_call_later(hass, 15, _retry)


@websocket_api.websocket_command(WEBSOCKET_BOARD)
@websocket_api.async_response
async def websocket_board(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return inbound/outbound trains for any Regional Rail station."""
    data = hass.data.get(DOMAIN) or {}
    coordinator = next(iter(data.values()), None)
    if coordinator is None:
        connection.send_error(msg["id"], "not_setup", "SEPTA Transit is not set up")
        return
    try:
        board = await coordinator.async_board_for_station(str(msg.get("station") or ""))
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "septa_error", str(err))
        return
    connection.send_result(msg["id"], board)


def _public_bus(row: dict | None) -> dict | None:
    if not isinstance(row, dict):
        return None
    return {key: value for key, value in row.items() if key != "sched_dt"}


def _live_board(coordinator: SeptaCoordinator) -> dict:
    data = coordinator.data or {}
    bus = data.get("next_bus") if isinstance(data.get("next_bus"), dict) else None
    lines = data.get("lines") if isinstance(data.get("lines"), dict) else {}
    return {
        "updated": data.get("updated"),
        "status": data.get("status"),
        "southbound": (data.get("southbound_board") or [])[:8],
        "northbound": (data.get("northbound_board") or [])[:8],
        "bus": _public_bus(bus),
        "lines": lines,
    }


@websocket_api.websocket_command(WEBSOCKET_PANEL)
@websocket_api.async_response
async def websocket_panel(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Sidebar app: entries, commute settings, and the station list."""
    data = hass.data.get(DOMAIN) or {}
    entries = []
    for entry_id, coordinator in data.items():
        if not hasattr(coordinator, "station"):
            continue
        entries.append(
            {
                "entry_id": entry_id,
                "station": coordinator.station,
                "destination": coordinator.destination,
                "walk_minutes": coordinator.walk,
                "show_rail": coordinator.show_rail,
                "show_bus": coordinator.show_bus,
                "show_metro": coordinator.show_metro,
                "show_trolley": coordinator.show_trolley,
                "show_sidebar": _sidebar_enabled(coordinator.entry),
                "rail_line": coordinator.rail_line,
                "bus_line": coordinator.bus_line,
                "bus_stop": coordinator.bus_stop,
                "bus_destination": coordinator.bus_dest,
                "metro_line": coordinator.metro_line,
                "trolley_line": coordinator.trolley_line,
                "metro_home": coordinator.metro_home,
                "metro_dest": coordinator.metro_dest,
                "trolley_home": coordinator.trolley_home,
                "trolley_dest": coordinator.trolley_dest,
                "watches": coordinator.watches(),
                "trips": coordinator.configured_trips(),
                "entities": _entity_map(hass, entry_id, coordinator.station, coordinator.destination),
                "live": _live_board(coordinator),
            }
        )
    connection.send_result(
        msg["id"],
        {
            "entries": entries,
            "stations": _rail_stations(hass, data),
            "nearest_stations": await _nearest_stations(data),
            "lines": [{"id": code, "name": name} for code, name in _LINE_NAMES.items()],
            "bus_routes": [{"id": rid, "name": name} for rid, name in BUS_ROUTES],
            "metro_lines": [{"id": rid, "name": name} for rid, name in SERVICE_LINES["metro"]],
            "trolley_lines": [{"id": rid, "name": name} for rid, name in SERVICE_LINES["trolley"]],
            "metro_stations": list(METRO_STATIONS),
            "trolley_stations": list(TROLLEY_STATIONS),
        },
    )


def _rail_stations(hass: HomeAssistant, data: dict) -> list:
    """Regional Rail stations from the active timetable. Metro and trolley stay separate."""
    from .schedule_ha import rail_names

    line = ""
    for coordinator in data.values():
        line = str(getattr(coordinator, "rail_line", "") or "")
        if line:
            break
    try:
        return rail_names(hass, line or None, list(STATIONS))
    except Exception:  # noqa: BLE001
        return list(STATIONS)


async def _nearest_stations(data: dict) -> list[dict]:
    """Names and distances only. Home coordinates stay on the HA box."""
    coordinator = next((item for item in data.values() if hasattr(item, "async_nearest_stations")), None)
    if coordinator is None:
        return []
    try:
        return await coordinator.async_nearest_stations(list(STATIONS), _ha_home(coordinator.hass))
    except Exception:  # noqa: BLE001
        _LOGGER.debug("SEPTA nearest stations skipped")
        return []


def _clean_watches(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    counts: dict[str, int] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode") or "")
        if mode not in ("rail", "bus", "metro", "trolley"):
            continue
        counts[mode] = counts.get(mode, 0) + 1
        if counts[mode] > 3:
            continue
        wid = "".join(ch for ch in str(item.get("id") or "").lower() if ch.isalnum())[:12]
        if not wid:
            continue
        out.append(
            {
                "id": wid,
                "mode": mode,
                "line": str(item.get("line") or "")[:24],
                "home": str(item.get("home") or "")[:80],
                "dest": str(item.get("dest") or "")[:80],
            }
        )
    return out


def _clean_trips(raw: object) -> list[dict]:
    from .trips import clean_trips

    return clean_trips(raw)


@websocket_api.websocket_command(WEBSOCKET_BUS)
@websocket_api.async_response
async def websocket_bus_picker(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Stops and destinations for the selected bus route."""
    coordinator = (hass.data.get(DOMAIN) or {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "SEPTA Transit entry not found")
        return
    choices = await coordinator.async_bus_choices(
        str(msg.get("route") or ""),
        str(msg.get("stop_id") or ""),
    )
    connection.send_result(msg["id"], choices)


@websocket_api.websocket_command(WEBSOCKET_ROUTE)
@websocket_api.async_response
async def websocket_route(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Full route line for a rider or a train number. Read from the GTFS cache."""
    from .shapes import resolve_route

    data = hass.data.get(DOMAIN) or {}
    entry_id = msg.get("entry_id")
    if entry_id:
        coords = [data.get(entry_id)]
        if coords[0] is None:
            connection.send_result(msg["id"], {"error": "not_found"})
            return
    else:
        coords = [item for item in data.values() if hasattr(item, "rail_schedule") or hasattr(item, "ride")]
    pairs = []
    for coordinator in coords:
        keeper = getattr(coordinator, "rail_schedule", None)
        cache = getattr(keeper, "shapes", None) or {}
        ride = getattr(coordinator, "ride", None)
        rows = []
        for rider in getattr(ride, "riders", {}).values() if ride is not None else []:
            try:
                rows.append(rider.attributes())
            except Exception:  # noqa: BLE001
                continue
        pairs.append((cache, rows))
    connection.send_result(msg["id"], resolve_route(pairs, msg.get("train"), msg.get("rider")))


@websocket_api.websocket_command(WEBSOCKET_PLAN)
@websocket_api.async_response
async def websocket_plan(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Read-only trip plan. Does not change a rider's Going Home origin."""
    from datetime import datetime

    from .coordinator import NY
    from .dynamic import match_station, plan_query

    data = hass.data.get(DOMAIN) or {}
    entry_id = msg.get("entry_id")
    if entry_id:
        coordinator = data.get(entry_id)
        if coordinator is None or getattr(coordinator, "dynamic", None) is None:
            connection.send_result(msg["id"], {"error": "not_found"})
            return
    else:
        coordinator = next((item for item in data.values() if getattr(item, "dynamic", None) is not None), None)
        if coordinator is None:
            connection.send_result(msg["id"], {"error": "not_found"})
            return
    board = coordinator.dynamic
    opt = board.options()
    slug = board.slug_for(msg.get("rider"))
    cfg = board._cfg(slug, opt)
    home = str(cfg.get("home_station") or opt.get("home_station") or "").strip()
    names = list(board._names or STATIONS)
    origin = match_station(msg.get("origin"), names)
    if not origin:
        connection.send_result(msg["id"], {"error": "not_found"})
        return
    destination = msg.get("destination")
    if destination and not match_station(destination, names):
        connection.send_result(msg["id"], {"error": "not_found"})
        return
    now = datetime.now(NY)
    dest_name = match_station(destination, names) if destination else (match_station(home, names) or home)
    live: list = []
    try:
        if dest_name:
            fetched, _error = await coordinator.async_cached_nta(
                origin, dest_name, int(msg.get("count") or 8), opt["transfer_min"], force=False
            )
            live = fetched or []
    except Exception:  # noqa: BLE001
        live = []
    from functools import partial

    connection.send_result(
        msg["id"],
        await hass.async_add_executor_job(
            partial(
                plan_query,
                board._schedule,
                names,
                origin=origin,
                destination=destination,
                home=home,
                after=msg.get("after"),
                arrive_by=msg.get("arrive_by"),
                count=msg.get("count") or 8,
                transfer_min=opt["transfer_min"],
                now=now,
                live_rows=live,
            )
        ),
    )


@websocket_api.websocket_command(WEBSOCKET_DAY)
@websocket_api.async_response
async def websocket_day_trains(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Full day-train list. State attributes keep a shorter copy."""
    data = hass.data.get(DOMAIN) or {}
    entry_id = msg.get("entry_id")
    if entry_id:
        coordinator = data.get(entry_id)
    else:
        coordinator = next((item for item in data.values() if getattr(item, "dynamic", None) is not None), None)
    board = getattr(coordinator, "dynamic", None)
    if board is None:
        connection.send_result(msg["id"], {"error": "not_found"})
        return
    slug = board.slug_for(msg.get("rider"))
    primary = not slug
    from .ids import dynamic_key

    day = board.results.get(dynamic_key("day_trains", slug, primary or not slug)) or {}
    rows = day.get("trains_full") or day.get("trains") or []
    connection.send_result(
        msg["id"],
        {
            "rider": slug,
            "origin": day.get("origin"),
            "destination": day.get("destination"),
            "suggested_train": day.get("suggested_train"),
            "trains": rows,
        },
    )


@websocket_api.websocket_command(WEBSOCKET_OPTIONS)
@websocket_api.async_response
async def websocket_options(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Update commute setup from the sidebar app."""
    try:
        entry = hass.config_entries.async_get_entry(msg["entry_id"])
        if entry is None or entry.domain != DOMAIN:
            connection.send_error(msg["id"], "not_found", "SEPTA Transit entry not found")
            return
        options = dict(entry.options)
        data = dict(entry.data)
        mapping = {
            "destination": CONF_DESTINATION,
            "walk_minutes": CONF_WALK,
            "show_sidebar": CONF_SIDEBAR,
            "show_rail": CONF_SHOW_RAIL,
            "show_bus": CONF_SHOW_BUS,
            "show_metro": CONF_SHOW_METRO,
            "show_trolley": CONF_SHOW_TROLLEY,
            "rail_line": CONF_RAIL_LINE,
            "bus_line": CONF_BUS_LINE,
            "bus_stop": CONF_BUS_STOP,
            "bus_destination": CONF_BUS_DEST,
            "metro_line": CONF_METRO_LINE,
            "trolley_line": CONF_TROLLEY_LINE,
            "metro_home": CONF_METRO_STATION,
            "metro_dest": CONF_METRO_DEST,
            "trolley_home": CONF_TROLLEY_STATION,
            "trolley_dest": CONF_TROLLEY_DEST,
        }
        for src, dest in mapping.items():
            if src not in msg or msg.get(src) is None:
                continue
            if dest == CONF_DESTINATION and not str(msg.get(src) or "").strip():
                continue
            options[dest] = msg[src]
        if "watches" in msg:
            options[CONF_WATCHES] = _clean_watches(msg.get("watches"))
        if "trips" in msg:
            options[CONF_TRIPS] = _clean_trips(msg.get("trips"))
        if "ride_tracker" in msg:
            tracker = str(msg.get("ride_tracker") or "").strip()
            if tracker:
                options[CONF_RIDE_TRACKER] = tracker
            else:
                options.pop(CONF_RIDE_TRACKER, None)
        ride_map = {
            "ride_radius_m": CONF_RIDE_RADIUS,
            "ride_min_speed_mph": CONF_RIDE_MIN_SPEED,
            "ride_matches": CONF_RIDE_MATCHES,
            "ride_max_accuracy_m": CONF_RIDE_MAX_ACCURACY,
            "ride_request_updates": CONF_RIDE_REQUEST,
            "event_lookahead_h": CONF_EVENT_LOOKAHEAD,
            "event_walk_speed": CONF_EVENT_WALK_SPEED,
        }
        for src, dest in ride_map.items():
            if src in msg:
                options[dest] = msg[src]
        if msg.get("station"):
            data[CONF_STATION] = msg["station"]
        hass.config_entries.async_update_entry(entry, data=data, options=options)
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("SEPTA options update failed")
        connection.send_error(msg["id"], "save_failed", str(err) or err.__class__.__name__)
        return
    connection.send_result(msg["id"], {"ok": True})


def _entity_map(hass: HomeAssistant, entry_id: str, station: str, dest: str) -> dict:
    """Map sensor keys to the entity ids HA actually registered."""
    try:
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(hass)
        prefix = f"{slug(station)}_{slug(dest)}_"
        found: dict[str, str] = {}
        for item in er.async_entries_for_config_entry(registry, entry_id):
            uid = item.unique_id or ""
            key = legacy_key(uid) or (uid[len(prefix) :] if uid.startswith(prefix) else "")
            if key:
                found[key] = item.entity_id
        return found
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("SEPTA Transit entity map skipped: %s", err)
        return {}


def _sidebar_enabled(entry: ConfigEntry) -> bool:
    if CONF_SIDEBAR in entry.options:
        return bool(entry.options[CONF_SIDEBAR])
    return bool(entry.data.get(CONF_SIDEBAR, True))


async def _async_sync_panel(hass: HomeAssistant) -> None:
    """Register the SEPTA app and show or hide the sidebar item."""
    global _PANEL_SIG
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id in (hass.data.get(DOMAIN) or {})
    ]
    show = any(_sidebar_enabled(entry) for entry in entries)
    sig = (bool(entries), show, _CARD_VERSION)
    if entries and sig == _PANEL_SIG:
        return
    try:
        from homeassistant.components.frontend import async_remove_panel

        panels = hass.data.get("frontend_panels") or {}
        if _PANEL_PATH in panels:
            async_remove_panel(hass, _PANEL_PATH)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("SEPTA Transit panel remove skipped: %s", err)
    if not entries:
        _PANEL_SIG = sig
        return
    try:
        from homeassistant.components import panel_custom

        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=_PANEL_PATH,
            webcomponent_name="septa-live-panel",
            sidebar_title="SEPTA" if show else None,
            sidebar_icon="mdi:train" if show else None,
            js_url=f"/{DOMAIN}/{_PANEL_JS}?v={_CARD_VERSION}",
            config={"show_sidebar": show},
            require_admin=False,
            embed_iframe=False,
        )
        _PANEL_SIG = sig
        _LOGGER.info("SEPTA Transit sidebar app registered (visible=%s)", show)
    except Exception as err:  # noqa: BLE001
        _PANEL_SIG = None
        _LOGGER.warning("SEPTA Transit could not register the sidebar app: %s", err)


def _install_local_card(hass: HomeAssistant, source: Path) -> None:
    dest_dir = Path(hass.config.path("www"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _CARD_JS
    dest.write_bytes(source.read_bytes())


async def _async_ensure_lovelace_resource(hass: HomeAssistant, url: str) -> bool:
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None and isinstance(lovelace, dict):
        resources = lovelace.get("resources")
    if resources is None:
        return False
    try:
        if hasattr(resources, "async_load") and not getattr(resources, "loaded", True):
            await resources.async_load()
        items = list(resources.async_items()) if hasattr(resources, "async_items") else []
        needle = f"/local/{_CARD_JS}"
        for item in items:
            if needle in str(item.get("url") or ""):
                item_id = item.get("id")
                if item_id is not None and item.get("url") != url and hasattr(resources, "async_update_item"):
                    await resources.async_update_item(item_id, {"res_type": "module", "url": url})
                return True
        if hasattr(resources, "async_create_item"):
            await resources.async_create_item({"res_type": "module", "url": url})
            return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("SEPTA Transit could not write Lovelace resource: %s", err)
    return False


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply a Save without unloading the sidebar app.

    Home Assistant's config entry reload tears the panel down. Sensors can be
    added and removed in place, and the coordinator refresh pushes a new board.
    A full reload is only needed when the station itself changes, because that
    changes the device identity.
    """
    coordinator = (hass.data.get(DOMAIN) or {}).get(entry.entry_id)
    if coordinator is None:
        return
    # Don't do this inside the Save websocket call. Home Assistant runs update
    # listeners immediately, and a sensor update there fails the button.
    async_call_later(hass, 0, _apply_saved_options_later(hass, entry))


def _apply_saved_options_later(hass: HomeAssistant, entry: ConfigEntry):
    async def _run(_now) -> None:
        await _apply_saved_options(hass, entry)

    return _run


async def _apply_saved_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator = (hass.data.get(DOMAIN) or {}).get(entry.entry_id)
    if coordinator is None:
        return
    if entry.data.get(CONF_STATION) != coordinator.device_station:
        _RELOADING.add(entry.entry_id)
        try:
            await hass.config_entries.async_reload(entry.entry_id)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("SEPTA reload failed")
        finally:
            _RELOADING.discard(entry.entry_id)
        return
    ride = getattr(coordinator, "ride", None)
    if ride is not None:
        try:
            await ride.async_reconfigure()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("SEPTA ride reconfigure failed")
    from .sensor import async_sync_sensors

    try:
        await async_sync_sensors(coordinator)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SEPTA sensor sync failed")
    try:
        from .binary_sensor import async_sync_binary_sensors

        await async_sync_binary_sensors(coordinator)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SEPTA riding sensor sync failed")
    try:
        from .device_tracker import async_sync_train_trackers

        await async_sync_train_trackers(coordinator)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SEPTA train tracker sync failed")
    show = _sidebar_enabled(entry)
    if show != bool(coordinator.sidebar_on):
        coordinator.sidebar_on = show
        await _async_sync_panel(hass)
    try:
        await coordinator.async_refresh_trips(force=True)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SEPTA trip refresh after save failed")
    try:
        await coordinator.async_request_refresh()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SEPTA refresh after save failed")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        from .schedule_ha import async_detach_schedule

        async_detach_schedule(hass)
        if entry.entry_id not in _RELOADING:
            await _async_sync_panel(hass)
    return unload_ok
