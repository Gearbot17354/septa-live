"""Config flow for SEPTA Transit."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    CONF_BUS_DEST,
    CONF_DESTINATION,
    CONF_METRO_DEST,
    CONF_METRO_STATION,
    CONF_SCAN,
    CONF_SHOW_BUS,
    CONF_SHOW_METRO,
    CONF_SHOW_RAIL,
    CONF_SHOW_TROLLEY,
    CONF_STATION,
    CONF_TROLLEY_DEST,
    CONF_TROLLEY_STATION,
    CONF_WALK,
    DEFAULT_DESTINATION,
    DEFAULT_SCAN,
    DEFAULT_SHOW_BUS,
    DEFAULT_SHOW_METRO,
    DEFAULT_SHOW_RAIL,
    DEFAULT_SHOW_TROLLEY,
    DEFAULT_STATION,
    DEFAULT_WALK,
    DOMAIN,
    STATIONS,
)
from .coordinator import slug

STATION_SELECTOR = selector(
    {
        "select": {
            "options": STATIONS,
            "custom_value": True,
            "mode": "dropdown",
        }
    }
)
TEXT_SELECTOR = selector({"text": {}})
BOOL_SELECTOR = selector({"boolean": {}})


def _flag(entry, key: str, default: bool) -> bool:
    if key in entry.options:
        return bool(entry.options[key])
    return bool(entry.data.get(key, default))


def _service_schema(defaults: dict | None = None) -> dict:
    d = defaults or {}
    return {
        vol.Required(CONF_SHOW_RAIL, default=d.get(CONF_SHOW_RAIL, DEFAULT_SHOW_RAIL)): BOOL_SELECTOR,
        vol.Required(CONF_SHOW_BUS, default=d.get(CONF_SHOW_BUS, DEFAULT_SHOW_BUS)): BOOL_SELECTOR,
        vol.Required(CONF_SHOW_METRO, default=d.get(CONF_SHOW_METRO, DEFAULT_SHOW_METRO)): BOOL_SELECTOR,
        vol.Required(
            CONF_SHOW_TROLLEY, default=d.get(CONF_SHOW_TROLLEY, DEFAULT_SHOW_TROLLEY)
        ): BOOL_SELECTOR,
    }


class SeptaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up a station tracker."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            station = user_input[CONF_STATION]
            dest = user_input.get(CONF_DESTINATION) or DEFAULT_DESTINATION
            await self.async_set_unique_id(f"{DOMAIN}_{slug(station)}_{slug(dest)}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"SEPTA {station}",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION, default=DEFAULT_STATION): STATION_SELECTOR,
                vol.Optional(CONF_DESTINATION, default=DEFAULT_DESTINATION): STATION_SELECTOR,
                vol.Optional(CONF_BUS_DEST, default=""): TEXT_SELECTOR,
                vol.Optional(CONF_METRO_STATION, default=""): TEXT_SELECTOR,
                vol.Optional(CONF_METRO_DEST, default=""): TEXT_SELECTOR,
                vol.Optional(CONF_TROLLEY_STATION, default=""): TEXT_SELECTOR,
                vol.Optional(CONF_TROLLEY_DEST, default=""): TEXT_SELECTOR,
                vol.Optional(CONF_WALK, default=DEFAULT_WALK): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=60)
                ),
                vol.Optional(CONF_SCAN, default=DEFAULT_SCAN): vol.All(
                    vol.Coerce(int), vol.Range(min=30, max=300)
                ),
                **_service_schema(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SeptaOptionsFlow()


class SeptaOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        entry = self.config_entry
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DESTINATION,
                    default=entry.options.get(
                        CONF_DESTINATION, entry.data.get(CONF_DESTINATION, DEFAULT_DESTINATION)
                    ),
                ): STATION_SELECTOR,
                vol.Optional(
                    CONF_BUS_DEST,
                    default=entry.options.get(CONF_BUS_DEST, entry.data.get(CONF_BUS_DEST, "")),
                ): TEXT_SELECTOR,
                vol.Optional(
                    CONF_METRO_STATION,
                    default=entry.options.get(
                        CONF_METRO_STATION, entry.data.get(CONF_METRO_STATION, "")
                    ),
                ): TEXT_SELECTOR,
                vol.Optional(
                    CONF_METRO_DEST,
                    default=entry.options.get(CONF_METRO_DEST, entry.data.get(CONF_METRO_DEST, "")),
                ): TEXT_SELECTOR,
                vol.Optional(
                    CONF_TROLLEY_STATION,
                    default=entry.options.get(
                        CONF_TROLLEY_STATION, entry.data.get(CONF_TROLLEY_STATION, "")
                    ),
                ): TEXT_SELECTOR,
                vol.Optional(
                    CONF_TROLLEY_DEST,
                    default=entry.options.get(
                        CONF_TROLLEY_DEST, entry.data.get(CONF_TROLLEY_DEST, "")
                    ),
                ): TEXT_SELECTOR,
                vol.Optional(
                    CONF_WALK,
                    default=entry.options.get(
                        CONF_WALK, entry.data.get(CONF_WALK, DEFAULT_WALK)
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                vol.Optional(
                    CONF_SCAN,
                    default=entry.options.get(
                        CONF_SCAN, entry.data.get(CONF_SCAN, DEFAULT_SCAN)
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
                **_service_schema(
                    {
                        CONF_SHOW_RAIL: _flag(entry, CONF_SHOW_RAIL, DEFAULT_SHOW_RAIL),
                        CONF_SHOW_BUS: _flag(entry, CONF_SHOW_BUS, DEFAULT_SHOW_BUS),
                        CONF_SHOW_METRO: _flag(entry, CONF_SHOW_METRO, DEFAULT_SHOW_METRO),
                        CONF_SHOW_TROLLEY: _flag(entry, CONF_SHOW_TROLLEY, DEFAULT_SHOW_TROLLEY),
                    }
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
