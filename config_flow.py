"""Config flow for SEPTA Transit."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    CONF_BUS_DEST,
    CONF_DAY_WINDOW,
    CONF_DEFAULT_CITY,
    CONF_DESTINATION,
    CONF_EVENT_BUFFER,
    CONF_GEOCODE,
    CONF_GOING_HOME_COUNT,
    CONF_HOME_STATION,
    CONF_METRO_DEST,
    CONF_METRO_STATION,
    CONF_NEAR_RADIUS,
    CONF_RIDE_ACTIVITY,
    CONF_RIDE_MATCHES,
    CONF_RIDE_MAX_ACCURACY,
    CONF_RIDE_MIN_SPEED,
    CONF_RIDE_RADIUS,
    CONF_RIDE_REQUEST,
    CONF_RIDE_RIDERS,
    CONF_RIDE_TRACKER,
    CONF_RIDERS_CFG,
    CONF_SCAN,
    CONF_SHOW_BUS,
    CONF_SHOW_METRO,
    CONF_SHOW_RAIL,
    CONF_SHOW_TROLLEY,
    CONF_SIDEBAR,
    CONF_STATION,
    CONF_TRANSFER_MIN,
    CONF_TROLLEY_DEST,
    CONF_TROLLEY_STATION,
    CONF_WALK,
    DEFAULT_DAY_WINDOW,
    DEFAULT_DESTINATION,
    DEFAULT_EVENT_BUFFER,
    DEFAULT_GOING_HOME_COUNT,
    DEFAULT_NEAR_RADIUS,
    DEFAULT_RIDE_MATCHES,
    DEFAULT_RIDE_MAX_ACCURACY,
    DEFAULT_RIDE_MIN_SPEED,
    DEFAULT_RIDE_RADIUS,
    DEFAULT_SCAN,
    DEFAULT_SHOW_BUS,
    DEFAULT_SHOW_METRO,
    DEFAULT_SHOW_RAIL,
    DEFAULT_SHOW_TROLLEY,
    DEFAULT_STATION,
    DEFAULT_TRANSFER_MIN,
    DEFAULT_WALK,
    DOMAIN,
    STATIONS,
)
from .coordinator import slug
from .dynamic import migrate_options
from .ride import configured_riders, dedupe_riders

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
TRACKER_SELECTOR = selector({"entity": {"domain": ["device_tracker", "person"]}})
RIDERS_SELECTOR = selector({"entity": {"domain": ["person", "device_tracker"], "multiple": True}})
ACTIVITY_SELECTOR = selector({"entity": {"domain": "sensor"}})
WINDOW_SELECTOR = selector({"select": {"options": ["today", "rest_of_day"], "mode": "dropdown"}})
DEST_ENTITY_SELECTOR = selector({"entity": {"domain": ["input_select", "input_text"]}})
CALENDAR_SELECTOR = selector({"entity": {"domain": "calendar"}})


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
    MINOR_VERSION = 2

    async def async_migrate_entry(self, hass, config_entry) -> bool:
        """Seed home and city stations without touching saved trips."""
        if config_entry.version > 1:
            return False
        if config_entry.version == 1 and getattr(config_entry, "minor_version", 1) >= 2:
            return True
        options = migrate_options(dict(config_entry.data), dict(config_entry.options))
        try:
            hass.config_entries.async_update_entry(config_entry, options=options, minor_version=2, version=1)
        except TypeError:
            hass.config_entries.async_update_entry(config_entry, options=options)
        return True

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
                vol.Optional(CONF_SIDEBAR, default=True): BOOL_SELECTOR,
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
            merged = {**entry.options, **user_input}
            saved_dest = str(
                entry.options.get(CONF_DESTINATION) or entry.data.get(CONF_DESTINATION) or DEFAULT_DESTINATION
            )
            submitted = str(merged.get(CONF_DESTINATION) or "").strip()
            if submitted and (submitted in STATIONS or submitted == saved_dest):
                merged[CONF_DESTINATION] = submitted
            else:
                merged[CONF_DESTINATION] = saved_dest
            riders = merged.get(CONF_RIDE_RIDERS) or []
            if isinstance(riders, str):
                riders = [part.strip() for part in riders.split(",") if part.strip()]
            riders = [str(item).strip() for item in riders if str(item).strip()]
            if riders:
                merged[CONF_RIDE_RIDERS] = riders
                merged[CONF_RIDE_TRACKER] = riders[0]
            else:
                merged.pop(CONF_RIDE_RIDERS, None)
                merged.pop(CONF_RIDE_TRACKER, None)
            activity = str(merged.get(CONF_RIDE_ACTIVITY) or "").strip()
            if activity:
                merged[CONF_RIDE_ACTIVITY] = activity
            else:
                merged.pop(CONF_RIDE_ACTIVITY, None)
            configure = bool(merged.pop("configure_dynamic", False))
            if configure:
                self._pending = merged
                self._riders = []
                self._rider_index = 0
                return await self.async_step_dynamic()
            return self.async_create_entry(title="", data=merged)
        saved_dest = str(
            entry.options.get(CONF_DESTINATION) or entry.data.get(CONF_DESTINATION) or DEFAULT_DESTINATION
        )
        current_riders = configured_riders(entry.options, entry.data)
        riders_key = vol.Optional(
            CONF_RIDE_RIDERS,
            description={"suggested_value": current_riders} if current_riders else {},
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_DESTINATION, default=saved_dest): STATION_SELECTOR,
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
                vol.Optional(
                    CONF_SIDEBAR,
                    default=_flag(entry, CONF_SIDEBAR, True),
                ): BOOL_SELECTOR,
                riders_key: RIDERS_SELECTOR,
                vol.Optional(
                    CONF_RIDE_ACTIVITY,
                    description={
                        "suggested_value": str(
                            entry.options.get(CONF_RIDE_ACTIVITY, entry.data.get(CONF_RIDE_ACTIVITY, "")) or ""
                        )
                    },
                ): ACTIVITY_SELECTOR,
                vol.Optional(
                    CONF_RIDE_RADIUS,
                    default=int(entry.options.get(CONF_RIDE_RADIUS, DEFAULT_RIDE_RADIUS)),
                ): vol.All(vol.Coerce(int), vol.Range(min=100, max=1500)),
                vol.Optional(
                    CONF_RIDE_MIN_SPEED,
                    default=int(entry.options.get(CONF_RIDE_MIN_SPEED, DEFAULT_RIDE_MIN_SPEED)),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Optional(
                    CONF_RIDE_MATCHES,
                    default=int(entry.options.get(CONF_RIDE_MATCHES, DEFAULT_RIDE_MATCHES)),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
                vol.Optional(
                    CONF_RIDE_MAX_ACCURACY,
                    default=int(entry.options.get(CONF_RIDE_MAX_ACCURACY, DEFAULT_RIDE_MAX_ACCURACY)),
                ): vol.All(vol.Coerce(int), vol.Range(min=20, max=500)),
                vol.Optional(
                    CONF_RIDE_REQUEST,
                    default=bool(entry.options.get(CONF_RIDE_REQUEST, False)),
                ): BOOL_SELECTOR,
                vol.Optional("configure_dynamic", default=False): BOOL_SELECTOR,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_dynamic(self, user_input: dict[str, Any] | None = None):
        entry = self.config_entry
        if user_input is not None:
            self._pending.update(user_input)
            self._riders = dedupe_riders(configured_riders(self._pending, entry.data), {})
            self._rider_index = 0
            if not self._riders:
                return self.async_create_entry(title="", data=self._pending)
            return await self.async_step_rider()
        home = str(entry.options.get(CONF_HOME_STATION) or entry.data.get(CONF_STATION) or "")
        city = str(
            entry.options.get(CONF_DEFAULT_CITY)
            or entry.options.get(CONF_DESTINATION)
            or entry.data.get(CONF_DESTINATION)
            or ""
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOME_STATION, default=home): STATION_SELECTOR,
                vol.Required(CONF_DEFAULT_CITY, default=city): STATION_SELECTOR,
                vol.Optional(
                    CONF_NEAR_RADIUS,
                    default=int(entry.options.get(CONF_NEAR_RADIUS, DEFAULT_NEAR_RADIUS)),
                ): vol.All(vol.Coerce(int), vol.Range(min=200, max=5000)),
                vol.Optional(
                    CONF_GOING_HOME_COUNT,
                    default=int(entry.options.get(CONF_GOING_HOME_COUNT, DEFAULT_GOING_HOME_COUNT)),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
                vol.Optional(
                    CONF_TRANSFER_MIN,
                    default=int(entry.options.get(CONF_TRANSFER_MIN, DEFAULT_TRANSFER_MIN)),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=30)),
                vol.Optional(
                    CONF_EVENT_BUFFER,
                    default=int(entry.options.get(CONF_EVENT_BUFFER, DEFAULT_EVENT_BUFFER)),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=180)),
                vol.Optional(
                    CONF_DAY_WINDOW,
                    default=str(entry.options.get(CONF_DAY_WINDOW) or DEFAULT_DAY_WINDOW),
                ): WINDOW_SELECTOR,
                vol.Optional(CONF_GEOCODE, default=bool(entry.options.get(CONF_GEOCODE, False))): BOOL_SELECTOR,
            }
        )
        return self.async_show_form(step_id="dynamic", data_schema=schema)

    async def async_step_rider(self, user_input: dict[str, Any] | None = None):
        spec = self._riders[self._rider_index]
        slug = spec["slug"]
        if user_input is not None:
            cfg = dict(self._pending.get(CONF_RIDERS_CFG) or {})
            kept = {key: value for key, value in user_input.items() if value not in ("", None, False) or key.startswith("enabled_")}
            for key in ("home_station", "city_station", "default_destination", "destination_entity", "calendar_entity"):
                if not str(kept.get(key) or "").strip():
                    kept.pop(key, None)
            cfg[slug] = kept
            self._pending[CONF_RIDERS_CFG] = cfg
            self._rider_index += 1
            if self._rider_index >= len(self._riders):
                return self.async_create_entry(title="", data=self._pending)
            return await self.async_step_rider()
        saved = (self.config_entry.options.get(CONF_RIDERS_CFG) or {}).get(slug) or {}
        schema = vol.Schema(
            {
                vol.Optional(CONF_HOME_STATION, description={"suggested_value": saved.get(CONF_HOME_STATION, "")}): STATION_SELECTOR,
                vol.Optional("city_station", description={"suggested_value": saved.get("city_station", "")}): STATION_SELECTOR,
                vol.Optional(
                    "default_destination", description={"suggested_value": saved.get("default_destination", "")}
                ): STATION_SELECTOR,
                vol.Optional(
                    "destination_entity", description={"suggested_value": saved.get("destination_entity", "")}
                ): DEST_ENTITY_SELECTOR,
                vol.Optional(
                    "calendar_entity", description={"suggested_value": saved.get("calendar_entity", "")}
                ): CALENDAR_SELECTOR,
                vol.Optional("enabled_going_home", default=bool(saved.get("enabled_going_home", True))): BOOL_SELECTOR,
                vol.Optional("enabled_day_trains", default=bool(saved.get("enabled_day_trains", True))): BOOL_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="rider",
            data_schema=schema,
            description_placeholders={"rider": slug},
        )
