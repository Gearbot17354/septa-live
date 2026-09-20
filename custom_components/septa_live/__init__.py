"""SEPTA Live integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import SeptaCoordinator

_LOGGER = logging.getLogger(__name__)
_FRONTEND = f"{DOMAIN}_frontend_registered"


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


async def _async_register_lovelace_cards(hass: HomeAssistant) -> None:
    if hass.data.get(_FRONTEND):
        return
    www = Path(__file__).parent / "www"
    card = www / "septa-live-card.js"
    if not card.exists():
        return
    try:
        from homeassistant.components.frontend import add_extra_js_url
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"/{DOMAIN}", str(www), False)]
        )
        add_extra_js_url(hass, f"/{DOMAIN}/septa-live-card.js")
        hass.data[_FRONTEND] = True
    except Exception:  # noqa: BLE001 — keep sensors working if frontend APIs shift
        _LOGGER.warning("Could not auto-register SEPTA Live Lovelace cards")


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
