"""Sensors for SEPTA Transit."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NY, SeptaCoordinator, slug


def _overnight(now: datetime | None = None) -> bool:
    hour = (now or datetime.now(NY)).hour
    return hour >= 21 or hour < 5


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SeptaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    if coordinator.show_rail:
        entities.extend(
            [
                SeptaMinutesSensor(coordinator, "south", "Next Inbound", "mdi:train"),
                SeptaMinutesSensor(coordinator, "north", "Next Outbound", "mdi:train"),
                SeptaRailBoardSensor(coordinator, "south", "Inbound Board"),
                SeptaRailBoardSensor(coordinator, "north", "Outbound Board"),
                SeptaLeaveSensor(coordinator),
                SeptaStatusSensor(coordinator),
            ]
        )
    if coordinator.show_bus:
        entities.append(SeptaNextBusSensor(coordinator))
    if coordinator.show_metro:
        entities.append(SeptaServiceCountSensor(coordinator, "metro", "Metro", "mdi:subway-variant"))
    if coordinator.show_trolley:
        entities.append(SeptaServiceCountSensor(coordinator, "trolley", "Trolley", "mdi:tram"))
    entities.append(SeptaMapSensor(coordinator))
    async_add_entities(entities)


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
        return None

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
            "destination": row.get("destination"),
            "track": row.get("track"),
            "platform": row.get("track"),
            "clock": row.get("clock"),
            "service_type": row.get("service_type"),
            "status": row.get("status"),
        }
        return attrs


class SeptaRailBoardSensor(_Base):
    """Next five Regional Rail trains in one direction, with platform when posted."""

    def __init__(self, coordinator: SeptaCoordinator, direction: str, name: str) -> None:
        super().__init__(coordinator, f"{direction}_board")
        self._direction = direction
        self._attr_name = name
        self._attr_icon = "mdi:bulletin-board"

    def _trains(self) -> list[dict[str, Any]]:
        data = self.coordinator.data or {}
        key = "southbound_board" if self._direction == "south" else "northbound_board"
        rows = data.get(key) or []
        return rows if isinstance(rows, list) else []

    @property
    def native_value(self) -> str:
        trains = self._trains()
        if not trains:
            return "No more trains" if _overnight() else "No trains"
        first = trains[0]
        clock = str(first.get("clock") or "").strip()
        track = str(first.get("track") or "").strip()
        if clock and track:
            return f"{clock} · Trk {track}"
        if clock:
            return clock
        dest = str(first.get("destination") or "").strip()
        return dest or "Scheduled"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        trains = self._trains()
        first = trains[0] if trains else {}
        ended = not trains
        return {
            "trains": trains,
            "count": len(trains),
            "direction": "inbound" if self._direction == "south" else "outbound",
            "next_train": first.get("train_id"),
            "next_destination": first.get("destination"),
            "next_track": first.get("track"),
            "platform": first.get("track"),
            "clock": first.get("clock"),
            "service_type": first.get("service_type"),
            "station": (self.coordinator.data or {}).get("station") or self.coordinator.station,
            "service_ended": ended,
        }


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
        data = self.coordinator.data or {}
        row = data.get("next_commute") or {}
        return {
            "walk_minutes": self.coordinator.walk,
            "destination": self.coordinator.destination,
            "train_id": row.get("train_id"),
            "depart": row.get("depart"),
            "arrive": row.get("arrive"),
            "line": row.get("line"),
        }


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
            "home": pack.get("home"),
            "destination": pack.get("destination"),
        }


class SeptaMapSensor(_Base):
    _attr_name = "Map"
    _attr_icon = "mdi:map-marker-path"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SeptaCoordinator) -> None:
        super().__init__(coordinator, "map")
        self.entity_id = f"sensor.septa_{slug(coordinator.station)}_map"

    def _pack(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("map") or {}

    @property
    def native_value(self) -> int:
        vehicles = self._pack().get("vehicles") or []
        return len(vehicles) if isinstance(vehicles, list) else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pack = self._pack()
        home = pack.get("home") or {}
        vehicles = pack.get("vehicles") or []
        return {
            "station": self.coordinator.station,
            "home_lat": home.get("lat") if isinstance(home, dict) else None,
            "home_lon": home.get("lon") if isinstance(home, dict) else None,
            "latitude": home.get("lat") if isinstance(home, dict) else None,
            "longitude": home.get("lon") if isinstance(home, dict) else None,
            "vehicles": vehicles if isinstance(vehicles, list) else [],
        }
