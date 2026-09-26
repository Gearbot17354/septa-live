"""SEPTA Transit integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .bus_routes import BUS_ROUTES
from .const import (
    CONF_BUS_LINE,
    CONF_BUS_STOP,
    CONF_DESTINATION,
    CONF_METRO_DEST,
    CONF_METRO_LINE,
    CONF_METRO_STATION,
    CONF_RAIL_LINE,
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
    DOMAIN,
    METRO_STATIONS,
    PLATFORMS,
    SERVICE_LINES,
    STATIONS,
    TROLLEY_STATIONS,
)
from .coordinator import SeptaCoordinator, _LINE_NAMES, slug

_LOGGER = logging.getLogger(__name__)
_FRONTEND = f"{DOMAIN}_frontend_registered"
_CARD_JS = "septa-live-card.js"
_PANEL_JS = "septa-live-panel.js"
_PANEL_PATH = "septa-live"
_CARD_VERSION = "1.9.11"
_PANEL_SIG: tuple | None = None
_RELOADING: set[str] = set()
_SKIP_RELOAD: set[str] = set()


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    await _async_register_lovelace_cards(hass)
    websocket_api.async_register_command(hass, websocket_board)
    websocket_api.async_register_command(hass, websocket_panel)
    websocket_api.async_register_command(hass, websocket_options)
    websocket_api.async_register_command(hass, websocket_bus_picker)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await _async_register_lovelace_cards(hass)
    coordinator = SeptaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "septa_live/board",
        vol.Required("station"): str,
    }
)
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


@websocket_api.websocket_command({vol.Required("type"): "septa_live/panel"})
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
                "entities": _entity_map(hass, entry_id, coordinator.station, coordinator.destination),
                "live": _live_board(coordinator),
            }
        )
    connection.send_result(
        msg["id"],
        {
            "entries": entries,
            "stations": list(STATIONS),
            "lines": [{"id": code, "name": name} for code, name in _LINE_NAMES.items()],
            "bus_routes": [{"id": rid, "name": name} for rid, name in BUS_ROUTES],
            "metro_lines": [{"id": rid, "name": name} for rid, name in SERVICE_LINES["metro"]],
            "trolley_lines": [{"id": rid, "name": name} for rid, name in SERVICE_LINES["trolley"]],
            "metro_stations": list(METRO_STATIONS),
            "trolley_stations": list(TROLLEY_STATIONS),
        },
    )


def _structure_changed(entry: ConfigEntry, data: dict, options: dict) -> bool:
    """True when Save has to add or remove sensors."""
    if data.get(CONF_STATION) != entry.data.get(CONF_STATION):
        return True
    keys = (CONF_SHOW_RAIL, CONF_SHOW_BUS, CONF_SHOW_METRO, CONF_SHOW_TROLLEY, CONF_WATCHES)
    for key in keys:
        new = options.get(key)
        old = entry.options.get(key, entry.data.get(key))
        if key == CONF_WATCHES:
            if json.dumps(new or [], sort_keys=True) != json.dumps(old or [], sort_keys=True):
                return True
        elif bool(new) != bool(old):
            return True
    return False


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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "septa_live/bus_picker",
        vol.Required("entry_id"): str,
        vol.Optional("route"): str,
        vol.Optional("stop_id"): str,
    }
)
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "septa_live/options",
        vol.Required("entry_id"): str,
        vol.Optional("destination"): str,
        vol.Optional("walk_minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
        vol.Optional("show_sidebar"): bool,
        vol.Optional("show_rail"): bool,
        vol.Optional("show_bus"): bool,
        vol.Optional("show_metro"): bool,
        vol.Optional("show_trolley"): bool,
        vol.Optional("station"): str,
        vol.Optional("rail_line"): str,
        vol.Optional("bus_line"): str,
        vol.Optional("bus_stop"): str,
        vol.Optional("bus_destination"): str,
        vol.Optional("metro_line"): str,
        vol.Optional("trolley_line"): str,
        vol.Optional("metro_home"): str,
        vol.Optional("metro_dest"): str,
        vol.Optional("trolley_home"): str,
        vol.Optional("trolley_dest"): str,
        vol.Optional("watches"): list,
    }
)
@websocket_api.async_response
async def websocket_options(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Update commute setup from the sidebar app."""
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
        if src in msg:
            options[dest] = msg[src]
    if "watches" in msg:
        options[CONF_WATCHES] = _clean_watches(msg.get("watches"))
    if msg.get("station"):
        data[CONF_STATION] = msg["station"]
    structural = _structure_changed(entry, data, options)
    if not structural:
        # The update listener refreshes in place. A reload here deadlocks Save.
        _SKIP_RELOAD.add(entry.entry_id)
    try:
        hass.config_entries.async_update_entry(entry, data=data, options=options)
    except Exception as err:  # noqa: BLE001
        _SKIP_RELOAD.discard(entry.entry_id)
        _LOGGER.exception("SEPTA options update failed")
        connection.send_error(msg["id"], "save_failed", str(err) or "Could not save")
        return
    connection.send_result(msg["id"], {"ok": True, "reloaded": structural})


def _entity_map(hass: HomeAssistant, entry_id: str, station: str, dest: str) -> dict:
    """Map sensor keys to the entity ids HA actually registered."""
    try:
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(hass)
        prefix = f"{slug(station)}_{slug(dest)}_"
        found: dict[str, str] = {}
        for item in er.async_entries_for_config_entry(registry, entry_id):
            uid = item.unique_id or ""
            key = uid[len(prefix) :] if uid.startswith(prefix) else uid
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


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload sensors without tearing down the sidebar page."""
    if entry.entry_id in _SKIP_RELOAD:
        _SKIP_RELOAD.discard(entry.entry_id)
        coordinator = (hass.data.get(DOMAIN) or {}).get(entry.entry_id)
        if coordinator is not None:
            hass.async_create_task(coordinator.async_request_refresh())
        return
    _RELOADING.add(entry.entry_id)
    try:
        await hass.config_entries.async_reload(entry.entry_id)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SEPTA reload failed")
    finally:
        _RELOADING.discard(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry.entry_id not in _RELOADING:
            await _async_sync_panel(hass)
    return unload_ok
