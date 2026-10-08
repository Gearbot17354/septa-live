"""Riding binary sensor for SEPTA Transit."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import CONF_RIDE_TRACKER, DOMAIN
from .coordinator import SeptaCoordinator, slug
from .sensor import _device_model


def _tracker_set(coordinator: SeptaCoordinator) -> bool:
    raw = coordinator.entry.options.get(CONF_RIDE_TRACKER, coordinator.entry.data.get(CONF_RIDE_TRACKER, ""))
    return bool(str(raw or "").strip())


def _wanted(coordinator: SeptaCoordinator) -> list[BinarySensorEntity]:
    if not _tracker_set(coordinator):
        return []
    return [SeptaRidingBinarySensor(coordinator)]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SeptaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = _wanted(coordinator)
    coordinator.add_binary = async_add_entities
    coordinator.binary_sensors = {entity.unique_id: entity for entity in entities if entity.unique_id}
    _drop_removed(hass, entry, entities)
    async_add_entities(entities)


async def async_sync_binary_sensors(coordinator: SeptaCoordinator) -> None:
    """Add or remove the riding sensor without reloading the integration."""
    if coordinator.add_binary is None:
        return
    wanted = _wanted(coordinator)
    wanted_ids = {entity.unique_id for entity in wanted if entity.unique_id}
    current: dict[str, Any] = coordinator.binary_sensors
    for uid, entity in list(current.items()):
        if uid in wanted_ids:
            continue
        current.pop(uid, None)
        if getattr(entity, "hass", None) is not None:
            await entity.async_remove()
    fresh = [entity for entity in wanted if entity.unique_id and entity.unique_id not in current]
    if fresh:
        coordinator.add_binary(fresh)
        for entity in fresh:
            current[entity.unique_id] = entity
    _drop_removed(coordinator.hass, coordinator.entry, list(current.values()))


def _drop_removed(hass: HomeAssistant, entry: ConfigEntry, entities: list) -> None:
    keep = {entity.unique_id for entity in entities if getattr(entity, "unique_id", None)}
    registry = async_get_entity_registry(hass)
    try:
        stale = [
            item
            for item in async_entries_for_config_entry(registry, entry.entry_id)
            if item.domain == "binary_sensor" and item.unique_id and item.unique_id not in keep
        ]
    except Exception:  # noqa: BLE001
        return
    for item in stale:
        try:
            registry.async_remove(item.entity_id)
        except Exception:  # noqa: BLE001
            continue


class SeptaRidingBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Riding"
    _attr_icon = "mdi:train"
    _attr_device_class = BinarySensorDeviceClass.MOVING
    _attr_should_poll = False

    def __init__(self, coordinator: SeptaCoordinator) -> None:
        self.coordinator = coordinator
        station = coordinator.station
        dest = coordinator.destination
        self._attr_unique_id = f"{slug(station)}_{slug(dest)}_riding"
        self.entity_id = f"binary_sensor.septa_{slug(station)}_riding"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{slug(station)}_{slug(dest)}")},
            name=f"SEPTA {station}",
            manufacturer="SEPTA",
            model=_device_model(coordinator),
        )

    @property
    def suggested_object_id(self) -> str:
        return self.entity_id.split(".", 1)[1]

    def _ride(self) -> dict[str, Any]:
        ride = getattr(self.coordinator, "ride", None)
        if ride is None:
            return {}
        return ride.attributes()

    @property
    def is_on(self) -> bool:
        return bool(self._ride().get("riding"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._ride()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        ride = getattr(self.coordinator, "ride", None)
        if ride is None:
            return
        self.async_on_remove(async_dispatcher_connect(self.hass, ride.signal(), self._on_ride))

    @callback
    def _on_ride(self, _payload=None) -> None:
        self.async_write_ha_state()
