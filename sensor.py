"""Sensors for SEPTA Live."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SeptaCoordinator, slug


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SeptaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SeptaMinutesSensor(coordinator, "south", "Next Southbound", "mdi:train"),
            SeptaMinutesSensor(coordinator, "north", "Next Northbound", "mdi:train"),
            SeptaMinutesSensor(coordinator, "commute", "Commute", "mdi:city-variant-outline"),
            SeptaLeaveSensor(coordinator),
            SeptaStatusSensor(coordinator),
            SeptaNextBusSensor(coordinator),
            SeptaServiceCountSensor(coordinator, "metro", "Metro", "mdi:subway-variant"),
            SeptaServiceCountSensor(coordinator, "trolley", "Trolley", "mdi:tram"),
        ]
    )


class _Base(CoordinatorEntity[SeptaCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SeptaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        station = coordinator.station
        dest = coordinator.destination
        self._key = key
        self._attr_unique_id = f"{slug(station)}_{slug(dest)}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{slug(station)}_{slug(dest)}")},
            name=f"SEPTA {station}",
            manufacturer="SEPTA",
            model="Regional Rail + Bus + Metro",
        )


class SeptaMinutesSensor(_Base):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: SeptaCoordinator, key: str, name: str, icon: str
    ) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._attr_icon = icon

    def _row(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        if self._key == "south":
            return data.get("next_south")
        if self._key == "north":
            return data.get("next_north")
        return data.get("next_commute")

    @property
    def native_value(self) -> int | None:
        row = self._row()
        if not row:
            return None
        return row.get("minutes")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        row = self._row() or {}
        attrs = {
            "train_id": row.get("train_id"),
            "line": row.get("line"),
            "delay": row.get("status") or row.get("delay"),
            "delay_min": row.get("delay_min"),
            "cancelled": row.get("cancelled"),
        }
        if self._key == "commute":
            attrs.update({"depart": row.get("depart"), "arrive": row.get("arrive")})
        else:
            attrs.update(
                {
                    "destination": row.get("destination"),
                    "track": row.get("track"),
                }
            )
        return attrs


class SeptaLeaveSensor(_Base):
    _attr_name = "Leave in"
    _attr_icon = "mdi:walk"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, coordinator: SeptaCoordinator) -> None:
        super().__init__(coordinator, "leave_in")

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("leave_in")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"walk_minutes": self.coordinator.walk}


class SeptaStatusSensor(_Base):
    _attr_name = "Status"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator: SeptaCoordinator) -> None:
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data or {}
        return data.get("status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        alerts = data.get("alerts") or []
        return {
            "alerts": [a.get("alert") for a in alerts],
            "updated": data.get("updated"),
        }


class SeptaNextBusSensor(_Base):
    _attr_name = "Next Bus"
    _attr_icon = "mdi:bus"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, coordinator: SeptaCoordinator) -> None:
        super().__init__(coordinator, "next_bus")

    @property
    def native_value(self) -> int | None:
        row = (self.coordinator.data or {}).get("next_bus") or {}
        return row.get("minutes")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        row = (self.coordinator.data or {}).get("next_bus") or {}
        return {
            "route": row.get("route"),
            "destination": row.get("destination"),
            "stop_name": row.get("stop_name"),
            "clock": row.get("clock"),
            "delay_min": row.get("delay_min"),
            "live": row.get("live"),
        }


class SeptaServiceCountSensor(_Base):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: SeptaCoordinator, key: str, name: str, icon: str
    ) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._attr_icon = icon

    def _pack(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self._key) or {}

    @property
    def native_value(self) -> int:
        pack = self._pack()
        try:
            return int(pack.get("count") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pack = self._pack()
        return {
            "summary": pack.get("summary"),
            "routes": pack.get("routes"),
            "l": pack.get("l"),
            "b": pack.get("b"),
            "m": pack.get("m"),
            "gps": pack.get("gps"),
        }
