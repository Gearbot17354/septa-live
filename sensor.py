"""Sensors for SEPTA Transit."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_RIDE_TRACKER, DOMAIN, UNRECORDED_TRAIN_ATTRS
from .ids import dynamic_ids, dynamic_key, object_key, stable_unique_id
from .trips import trip_ids
from .coordinator import NY, SeptaCoordinator, slug
from .ride import companions, configured_riders, dedupe_riders, riders_on_train, write_state_on_loop
from .shapes import cleared_route

# Card and YAML expect these object ids, not the device-area prefix HA would add.
_OBJECT_KEY = {
    "south": "next_southbound",
    "north": "next_northbound",
    "south_board": "inbound_board",
    "north_board": "outbound_board",
}


def _object_key(key: str) -> str:
    return object_key(key)


def _entity_id(station: str, key: str) -> str:
    return f"sensor.septa_{slug(station)}_{_object_key(key)}"


def _stabilize_entity_ids(hass: HomeAssistant, entry: ConfigEntry, coordinator: SeptaCoordinator) -> None:
    """Rename prefixed ids (sensor.area_septa_lansdale_metro) to sensor.septa_lansdale_metro."""
    registry = async_get_entity_registry(hass)
    prefix = f"{slug(coordinator.station)}_{slug(coordinator.destination)}_"
    for item in list(registry.entities.values()):
        if item.config_entry_id != entry.entry_id or item.domain != "sensor":
            continue
        uid = item.unique_id or ""
        if not uid.startswith(prefix):
            continue
        key = uid[len(prefix) :]
        if key == "riders_count" or key.startswith("my_train_"):
            continue
        desired = _entity_id(coordinator.station, key)
        stable = f"sensor.septa_{slug(coordinator.station)}_"
        if item.entity_id == desired or item.entity_id.startswith(stable):
            continue
        if registry.async_get(desired) is not None:
            continue
        registry.async_update_entity(item.entity_id, new_entity_id=desired)


def _overnight(now: datetime | None = None) -> bool:
    hour = (now or datetime.now(NY)).hour
    return hour >= 21 or hour < 5


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SeptaCoordinator = hass.data[DOMAIN][entry.entry_id]
    _stabilize_entity_ids(hass, entry, coordinator)
    entities = _wanted_entities(coordinator)
    coordinator.add_sensors = async_add_entities
    coordinator.sensors = {entity.unique_id: entity for entity in entities if entity.unique_id}
    _drop_removed_entities(hass, entry, entities)
    async_add_entities(entities)


def _wanted_entities(coordinator: SeptaCoordinator) -> list[SensorEntity]:
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
    for watch in coordinator.watches():
        if watch["mode"] == "rail" and not coordinator.show_rail:
            continue
        if watch["mode"] == "bus" and not coordinator.show_bus:
            continue
        if watch["mode"] == "metro" and not coordinator.show_metro:
            continue
        if watch["mode"] == "trolley" and not coordinator.show_trolley:
            continue
        if watch["mode"] == "rail":
            entities.append(SeptaLineSensor(coordinator, watch, "south"))
            entities.append(SeptaLineSensor(coordinator, watch, "north"))
        else:
            entities.append(SeptaLineSensor(coordinator, watch))
    for trip in coordinator.configured_trips():
        entities.append(SeptaTripSensor(coordinator, trip))
    for spec in _dynamic_specs(coordinator):
        entities.append(SeptaDynamicSensor(coordinator, "going_home", spec))
        entities.append(SeptaDynamicSensor(coordinator, "day_trains", spec))
    entities.append(SeptaMapSensor(coordinator))
    entities.append(SeptaRailScheduleSensor(coordinator))
    specs = _rider_specs(coordinator)
    if specs:
        entities.append(SeptaRidersCountSensor(coordinator))
        for spec in specs:
            if spec.get("primary"):
                entities.append(SeptaMyTrainSensor(coordinator, spec))
            else:
                entities.append(SeptaRiderTrainSensor(coordinator, spec))
    return entities


async def async_sync_sensors(coordinator: SeptaCoordinator) -> None:
    """Add and remove sensors without reloading the integration."""
    if coordinator.add_sensors is None:
        return
    wanted = _wanted_entities(coordinator)
    wanted_ids = {entity.unique_id for entity in wanted if entity.unique_id}
    current: dict[str, Any] = coordinator.sensors
    for uid, entity in list(current.items()):
        if uid in wanted_ids:
            continue
        current.pop(uid, None)
        if getattr(entity, "hass", None) is not None:
            await entity.async_remove()
    fresh = []
    for entity in wanted:
        uid = entity.unique_id
        if not uid:
            continue
        existing = current.get(uid)
        if existing is not None and getattr(existing, "hass", None) is not None:
            continue
        current.pop(uid, None)
        fresh.append(entity)
    if fresh:
        coordinator.add_sensors(fresh)
        for entity in fresh:
            current[entity.unique_id] = entity
    _drop_removed_entities(coordinator.hass, coordinator.entry, list(current.values()))


def _drop_removed_entities(
    hass: HomeAssistant, entry: ConfigEntry, entities: list[SensorEntity]
) -> None:
    """Remove sensors for lines that were deleted, and modes that were turned off."""
    keep = {entity.unique_id for entity in entities if getattr(entity, "unique_id", None)}
    registry = async_get_entity_registry(hass)
    try:
        stale = [
            item
            for item in async_entries_for_config_entry(registry, entry.entry_id)
            if item.domain == "sensor" and item.unique_id and item.unique_id not in keep
        ]
    except Exception:  # noqa: BLE001
        return
    for item in stale:
        try:
            registry.async_remove(item.entity_id)
        except Exception:  # noqa: BLE001
            continue


class _Base(CoordinatorEntity[SeptaCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SeptaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        station = coordinator.station
        self._key = key
        self._attr_unique_id = stable_unique_id(coordinator.entry.entry_id, key)
        self.entity_id = _entity_id(station, key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"SEPTA {station}",
            manufacturer="SEPTA",
            model=_device_model(coordinator),
        )


    @property
    def suggested_object_id(self) -> str:
        return _entity_id(self.coordinator.station, self._key).split(".", 1)[1]


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
        data = self.coordinator.data or {}
        board_key = "southbound_board" if self._key == "south" else "northbound_board"
        trains = data.get(board_key) or []
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
            "scheduled": row.get("scheduled"),
            "trains": trains if isinstance(trains, list) else [],
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

    def _with_riders(self, trains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = _rider_rows(self.coordinator)
        out = []
        for train in trains:
            item = dict(train)
            number = str(item.get("train_id") or item.get("train") or "")
            party = riders_on_train(rows, number) if number else []
            if party:
                item["riders"] = party
                item["rider_pictures"] = [row["entity_picture"] for row in party if row.get("entity_picture")]
            out.append(item)
        return out

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        trains = self._with_riders(self._trains())
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
        value = data.get("leave_in")
        if value is None or isinstance(value, bool):
            return None
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None

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


def _device_model(coordinator: SeptaCoordinator) -> str:
    parts: list[str] = []
    if coordinator.show_rail:
        parts.append("Regional Rail")
    if coordinator.show_bus:
        parts.append("Bus")
    if coordinator.show_metro:
        parts.append("Metro")
    if coordinator.show_trolley:
        parts.append("Trolley")
    extra = len(coordinator.watches())
    if extra:
        parts.append(f"{extra} extra line" + ("s" if extra != 1 else ""))
    return " + ".join(parts) or "SEPTA"


class SeptaTripSensor(CoordinatorEntity[SeptaCoordinator], SensorEntity):
    """Next departures for one origin-to-destination trip."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:transit-connection-variant"
    _attr_has_entity_name = True
    _unrecorded_attributes = UNRECORDED_TRAIN_ATTRS

    def __init__(self, coordinator: SeptaCoordinator, trip: dict) -> None:
        super().__init__(coordinator)
        self._trip_id = trip["id"]
        unique, entity = trip_ids(coordinator.entry.entry_id, trip["id"])
        self._attr_unique_id = unique
        self.entity_id = entity
        label = trip.get("label") or f"{trip['origin']} to {trip['destination']}"
        self._attr_name = label
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"SEPTA {coordinator.station}",
            manufacturer="SEPTA",
            model=_device_model(coordinator),
        )

    @property
    def suggested_object_id(self) -> str:
        return self.entity_id.split(".", 1)[1]

    def _pack(self) -> dict[str, Any]:
        found = (getattr(self.coordinator, "trip_results", {}) or {}).get(self._trip_id) or {}
        return found if isinstance(found, dict) else {}

    @property
    def native_value(self) -> int | None:
        rows = self._pack().get("trips") or []
        if not rows or not isinstance(rows, list):
            return None
        minutes = rows[0].get("minutes")
        if minutes is None or isinstance(minutes, bool):
            return None
        try:
            return max(0, int(minutes))
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pack = self._pack()
        return {
            "origin": pack.get("origin"),
            "destination": pack.get("destination"),
            "label": pack.get("label"),
            "updated": pack.get("updated"),
            "source": pack.get("source"),
            "trips": pack.get("trips") or [],
            "day": pack.get("day"),
            "transfer_min": pack.get("transfer_min"),
            "error": pack.get("error"),
        }


class SeptaDynamicSensor(CoordinatorEntity[SeptaCoordinator], RestoreEntity, SensorEntity):
    """Going Home, or the trains into town, for one rider."""

    _attr_has_entity_name = True
    _unrecorded_attributes = UNRECORDED_TRAIN_ATTRS

    def __init__(self, coordinator: SeptaCoordinator, kind: str, spec: dict) -> None:
        super().__init__(coordinator)
        self._kind = kind
        slug = str(spec.get("slug") or "")
        self._slug = slug
        self._primary = bool(spec.get("primary")) or not slug
        unique_id, entity_id = dynamic_ids(coordinator.entry.entry_id, kind, slug, self._primary)
        self._attr_unique_id = unique_id
        self.entity_id = entity_id
        title = "Going home" if kind == "going_home" else "Day trains"
        self._attr_name = f"{title} {slug.replace('_', ' ').title()}" if slug else title
        if kind == "going_home":
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
            self._attr_icon = "mdi:home-import-outline"
        else:
            self._attr_icon = "mdi:calendar-clock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"SEPTA {coordinator.station}",
            manufacturer="SEPTA",
            model=_device_model(coordinator),
        )

    @property
    def suggested_object_id(self) -> str:
        return self.entity_id.split(".", 1)[1]

    def _pack(self) -> dict[str, Any]:
        board = getattr(self.coordinator, "dynamic", None)
        if board is None:
            return {}
        found = board.results.get(dynamic_key(self._kind, self._slug, self._primary)) or {}
        return found if isinstance(found, dict) else {}

    @property
    def native_value(self) -> int | str | None:
        pack = self._pack()
        if self._kind == "going_home":
            if pack.get("reason") in {"at_home_station", "disabled", "no_origin"}:
                return None
            minutes = pack.get("state_minutes")
            if minutes is None or isinstance(minutes, bool):
                return None
            try:
                return max(0, int(minutes))
            except (TypeError, ValueError):
                return None
        train = pack.get("suggested_train") or pack.get("state_train")
        return None if not train else str(train)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pack = self._pack()
        attrs = {
            "rider": pack.get("rider"),
            "origin": pack.get("origin"),
            "origin_lat": pack.get("origin_lat"),
            "origin_lon": pack.get("origin_lon"),
            "origin_source": pack.get("origin_source"),
            "origin_distance_m": pack.get("origin_distance_m"),
            "origin_entity": pack.get("origin_entity"),
            "origin_fix_lat": pack.get("origin_fix_lat"),
            "origin_fix_lon": pack.get("origin_fix_lon"),
            "origin_fix_accuracy": pack.get("origin_fix_accuracy"),
            "origin_fix_age_s": pack.get("origin_fix_age_s"),
            "origin_skip_reason": pack.get("origin_skip_reason"),
            "home_station": pack.get("home_station"),
            "destination": pack.get("destination"),
            "destination_source": pack.get("destination_source"),
            "updated": pack.get("updated"),
            "source": pack.get("source"),
            "reason": pack.get("reason"),
            "error": pack.get("error"),
            "trains": pack.get("trains") or [],
            "trains_total": pack.get("trains_total") if pack.get("trains_total") is not None else len(pack.get("trains") or []),
        }
        if self._kind == "day_trains":
            attrs.update(
                {
                    "event": pack.get("event"),
                    "suggested": pack.get("suggested"),
                    "suggested_train": pack.get("suggested_train"),
                    "buffer_min": pack.get("buffer_min"),
                    "egress_walk_min": pack.get("egress_walk_min"),
                    "destination_distance_m": pack.get("destination_distance_m"),
                    "arrive_deadline": pack.get("arrive_deadline"),
                    "leave_by": pack.get("leave_by"),
                    "spare_min": pack.get("spare_min"),
                    "suggest_reason": pack.get("suggest_reason"),
                    "schedule_valid_until": pack.get("schedule_valid_until"),
                    "schedule_source": pack.get("schedule_source"),
                }
            )
        return attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._kind != "going_home":
            return
        board = getattr(self.coordinator, "dynamic", None)
        last = await self.async_get_last_state()
        origin = None if last is None else (last.attributes or {}).get("origin")
        if board is not None and origin:
            board.remember_last(self._slug, str(origin))


class SeptaLineSensor(_Base):
    """Inbound and outbound sensors for an extra commute line."""

    def __init__(
        self, coordinator: SeptaCoordinator, watch: dict[str, str], direction: str | None = None
    ) -> None:
        suffix = f"_{direction}" if direction else ""
        super().__init__(coordinator, f"line_{watch['mode']}_{watch['id']}{suffix}")
        self._watch_id = watch["id"]
        self._direction = direction
        home = watch.get("home") or watch.get("line") or watch["mode"].title()
        if direction == "south":
            self._attr_name = f"{home} inbound"
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
            self._attr_icon = "mdi:train"
        elif direction == "north":
            self._attr_name = f"{home} outbound"
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
            self._attr_icon = "mdi:train"
        else:
            label = watch.get("line") or watch.get("home") or watch["mode"].title()
            self._attr_name = f"{watch['mode'].title()} {label}"
            self._attr_icon = {
                "bus": "mdi:bus",
                "metro": "mdi:subway-variant",
                "trolley": "mdi:tram",
            }.get(watch["mode"], "mdi:transit-connection-variant")

    def _pack(self) -> dict[str, Any]:
        lines = (self.coordinator.data or {}).get("lines") or {}
        pack = lines.get(self._watch_id) if isinstance(lines, dict) else None
        return pack if isinstance(pack, dict) else {}

    def _row(self) -> dict[str, Any] | None:
        pack = self._pack()
        key = "southbound" if self._direction == "south" else "northbound"
        rows = pack.get(key) or []
        if rows and isinstance(rows[0], dict):
            return rows[0]
        return None

    @property
    def native_value(self) -> int | str | None:
        if self._direction:
            row = self._row()
            if not row:
                return None
            return row.get("minutes")
        pack = self._pack()
        if "state" not in pack:
            return None
        return pack.get("state")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pack = self._pack()
        if not self._direction:
            return pack
        row = self._row() or {}
        trains = pack.get("southbound" if self._direction == "south" else "northbound") or []
        return {
            "home": pack.get("home"),
            "line": row.get("line") or pack.get("line"),
            "destination": row.get("destination"),
            "clock": row.get("clock"),
            "train_id": row.get("train_id"),
            "track": row.get("track"),
            "status": row.get("status"),
            "delay_min": row.get("delay_min"),
            "service_type": row.get("service_type"),
            "trains": trains,
            "southbound": pack.get("southbound") or [],
            "northbound": pack.get("northbound") or [],
        }


class SeptaRailScheduleSensor(_Base):
    """Valid-through date of the Regional Rail timetable."""

    _attr_name = "Rail schedule"
    _attr_icon = "mdi:calendar"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SeptaCoordinator) -> None:
        super().__init__(coordinator, "rail_schedule")
        self.entity_id = "sensor.septa_rail_schedule"

    def _status(self) -> dict[str, Any]:
        keeper = getattr(self.coordinator, "rail_schedule", None)
        if keeper is None or not hasattr(keeper, "status"):
            return {}
        try:
            data = keeper.status()
        except Exception:  # noqa: BLE001
            return {}
        return data if isinstance(data, dict) else {}

    @property
    def native_value(self) -> date | None:
        raw = self._status().get("state")
        if not raw:
            return None
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._status()
        return {
            "feed": data.get("feed"),
            "source": data.get("source"),
            "last_check": data.get("last_check"),
            "last_success": data.get("last_success"),
            "last_error": data.get("last_error"),
            "days_remaining": data.get("days_remaining"),
        }


class SeptaMapSensor(_Base):
    _attr_name = "Map"
    _attr_icon = "mdi:map-marker-path"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SeptaCoordinator) -> None:
        super().__init__(coordinator, "map")

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


def _dynamic_specs(coordinator: SeptaCoordinator) -> list[dict]:
    ride = getattr(coordinator, "ride", None)
    if ride is not None and getattr(ride, "riders", None):
        specs = [
            {
                "key": rider.key,
                "slug": rider.slug,
                "person": rider.person,
                "configured": rider._configured,
                "tracker": rider._tracker_hint,
                "primary": rider.is_primary,
            }
            for rider in ride.riders.values()
        ]
        if specs:
            return specs
    specs = dedupe_riders(configured_riders(coordinator.entry.options, coordinator.entry.data), {})
    if specs:
        return specs
    return [{"slug": "", "primary": True, "configured": "", "tracker": "", "person": None}]


def _rider_rows(coordinator: SeptaCoordinator) -> list[dict]:
    ride = getattr(coordinator, "ride", None)
    if ride is None or not getattr(ride, "riders", None):
        return []
    rows = []
    for rider in ride.riders.values():
        try:
            rows.append(rider.attributes())
        except Exception:  # noqa: BLE001
            continue
    return rows


def _rider_specs(coordinator: SeptaCoordinator) -> list[dict]:
    ride = getattr(coordinator, "ride", None)
    if ride is not None and getattr(ride, "riders", None):
        return [
            {
                "key": rider.key,
                "slug": rider.slug,
                "person": rider.person,
                "configured": rider._configured,
                "primary": rider.is_primary,
            }
            for rider in ride.riders.values()
        ]
    return dedupe_riders(configured_riders(coordinator.entry.options, coordinator.entry.data), {})


def _ride_tracker_set(coordinator: SeptaCoordinator) -> bool:
    return bool(_rider_specs(coordinator))


class SeptaMyTrainSensor(_Base):
    """Train the phone is currently riding. State is the train number, or nothing."""

    _attr_name = "My train"
    _attr_icon = "mdi:train"
    _unrecorded_attributes = UNRECORDED_TRAIN_ATTRS

    def __init__(self, coordinator: SeptaCoordinator, spec: dict | None = None) -> None:
        spec = spec or {}
        slug_name = str(spec.get("slug") or "").strip()
        primary = bool(spec.get("primary", True))
        key = "my_train" if primary or not slug_name else f"my_train_{slug_name}"
        super().__init__(coordinator, key)
        self._spec = spec
        if slug_name:
            self.entity_id = f"sensor.septa_my_train_{slug_name}"
            self._attr_name = f"My train {slug_name.replace('_', ' ').title()}"

    def _ride(self) -> dict[str, Any]:
        ride = getattr(self.coordinator, "ride", None)
        if ride is None:
            return {}
        return ride.attributes()

    @property
    def native_value(self) -> str | None:
        data = self._ride()
        if not data.get("riding"):
            return None
        train = data.get("train")
        return str(train) if train else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = dict(self._ride())
        slug_name = str(self._spec.get("slug") or "")
        party = companions(_rider_rows(self.coordinator), slug_name, data.get("train"))
        data["riders"] = party
        data["rider_pictures"] = [row["entity_picture"] for row in party if row.get("entity_picture")]
        keeper = getattr(self.coordinator, "rail_schedule", None)
        if keeper is not None and hasattr(keeper, "route_for"):
            data.update(keeper.route_for(data))
        else:
            data.update(cleared_route())
        return data

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        ride = getattr(self.coordinator, "ride", None)
        if ride is None:
            return
        self.async_on_remove(async_dispatcher_connect(self.hass, ride.signal(), self._on_ride))

    @callback
    def _on_ride(self, _payload=None) -> None:
        write_state_on_loop(self.hass, self.async_write_ha_state)


class SeptaRiderTrainSensor(SeptaMyTrainSensor):
    """My Train for a rider who is not the primary."""

    def __init__(self, coordinator: SeptaCoordinator, spec: dict) -> None:
        spec = dict(spec)
        spec["primary"] = False
        super().__init__(coordinator, spec)

    @property
    def suggested_object_id(self) -> str:
        return f"septa_my_train_{self._spec['slug']}"

    def _rider(self):
        ride = getattr(self.coordinator, "ride", None)
        if ride is None:
            return None
        for rider in ride.riders.values():
            if rider.slug == self._spec["slug"] and not rider.is_primary:
                return rider
        return None

    def _ride(self) -> dict[str, Any]:
        rider = self._rider()
        return rider.attributes() if rider is not None else {}

    async def async_added_to_hass(self) -> None:
        await SensorEntity.async_added_to_hass(self)
        rider = self._rider()
        if rider is None:
            return
        self.async_on_remove(async_dispatcher_connect(self.hass, rider.signal(), self._on_ride))


class SeptaRidersCountSensor(_Base):
    """How many configured people are on a train right now."""

    _attr_name = "Riders on a train"
    _attr_icon = "mdi:account-group"
    _attr_should_poll = False

    def __init__(self, coordinator: SeptaCoordinator) -> None:
        super().__init__(coordinator, "riders_count")
        self.entity_id = "sensor.septa_riders_count"
        self._listener_unsubs: list = []
        self._listener_key: tuple[str, ...] | None = None

    @property
    def suggested_object_id(self) -> str:
        return "septa_riders_count"

    @property
    def available(self) -> bool:
        return True

    def _summary(self) -> dict[str, Any]:
        ride = getattr(self.coordinator, "ride", None)
        if ride is None:
            return {"count": 0, "riding": [], "riders": [], "trains": {}}
        try:
            data = ride.summary()
        except Exception:  # noqa: BLE001
            return {"count": 0, "riding": [], "riders": [], "trains": {}}
        if not isinstance(data, dict):
            return {"count": 0, "riding": [], "riders": [], "trains": {}}
        return data

    @property
    def native_value(self) -> int:
        try:
            return int(self._summary().get("count") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._summary()
        return {
            "riding": data.get("riding") or [],
            "riders": data.get("riders") or [],
            "trains": data.get("trains") or {},
            "parties": data.get("parties") or [],
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._listen()
        self.async_on_remove(self._close_listeners)
        write_state_on_loop(self.hass, self.async_write_ha_state)

    @callback
    def _on_ride(self, _payload=None) -> None:
        self._listen()
        write_state_on_loop(self.hass, self.async_write_ha_state)

    @callback
    def _listen(self) -> None:
        ride = getattr(self.coordinator, "ride", None)
        if ride is None or self.hass is None:
            return
        signals = tuple(sorted(rider.signal() for rider in ride.riders.values()))
        if signals == self._listener_key and self._listener_unsubs:
            return
        self._close_listeners()
        self._listener_key = signals
        watched = (ride.summary_signal(), *signals)
        for signal in watched:
            self._listener_unsubs.append(async_dispatcher_connect(self.hass, signal, self._on_ride))

    def _close_listeners(self) -> None:
        for unsub in self._listener_unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001
                continue
        self._listener_unsubs = []
        self._listener_key = None
