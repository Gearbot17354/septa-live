"""SEPTA Transit integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, PLATFORMS
from .coordinator import SeptaCoordinator

_LOGGER = logging.getLogger(__name__)
_FRONTEND = f"{DOMAIN}_frontend_registered"
_CARD_JS = "septa-live-card.js"
_CARD_VERSION = "1.8.5"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    await _async_register_lovelace_cards(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await _async_register_lovelace_cards(hass)
    coordinator = SeptaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
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
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
