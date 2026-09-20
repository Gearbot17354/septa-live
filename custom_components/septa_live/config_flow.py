"""Config flow for SEPTA Live."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    CONF_DESTINATION,
    CONF_SCAN,
    CONF_STATION,
    CONF_WALK,
    DEFAULT_DESTINATION,
    DEFAULT_SCAN,
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
                vol.Optional(CONF_WALK, default=DEFAULT_WALK): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=60)
                ),
                vol.Optional(CONF_SCAN, default=DEFAULT_SCAN): vol.All(
                    vol.Coerce(int), vol.Range(min=30, max=300)
                ),
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
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
