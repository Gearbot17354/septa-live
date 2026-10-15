"""One map marker per rider, at that rider's current train.

A device tracker keeps a stable entity id. While the rider is not on a train the
entity has no location, so the map does not draw it. Two people on the same train
each get a marker at the same TrainView point.
"""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import DOMAIN
from .coordinator import SeptaCoordinator
from .ride import position_is_stale, riders_on_train, write_state_on_loop
from .sensor import _device_model, _rider_specs
from .tracker import leftover_trackers, project_tracker, tracker_attributes, tracker_entities, tracker_icon


def _wanted(coordinator: SeptaCoordinator) -> list[TrackerEntity]:
    return [SeptaTrainTracker(coordinator, spec) for spec in _rider_specs(coordinator) if spec.get("slug")]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SeptaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = _wanted(coordinator)
    coordinator.add_trackers = async_add_entities
    coordinator.trackers = {entity.unique_id: entity for entity in entities if entity.unique_id}
    _drop_removed(hass, entry, entities)
    async_add_entities(entities)


async def async_sync_train_trackers(coordinator: SeptaCoordinator) -> None:
    if getattr(coordinator, "add_trackers", None) is None:
        return
    wanted = _wanted(coordinator)
    wanted_ids = {entity.unique_id for entity in wanted if entity.unique_id}
    current: dict[str, Any] = coordinator.trackers
    for uid, entity in list(current.items()):
        if uid in wanted_ids:
            continue
        current.pop(uid, None)
        if getattr(entity, "hass", None) is not None:
            await entity.async_remove()
    fresh = [entity for entity in wanted if entity.unique_id and entity.unique_id not in current]
    if fresh:
        coordinator.add_trackers(fresh)
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
            if item.domain == "device_tracker" and item.unique_id and item.unique_id not in keep
        ]
    except Exception:  # noqa: BLE001
        return
    for item in stale:
        try:
            registry.async_remove(item.entity_id)
        except Exception:  # noqa: BLE001
            continue


class SeptaTrainTracker(TrackerEntity):
    """The train a rider is on, shown with that rider's picture."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_icon = "mdi:train"

    def __init__(self, coordinator: SeptaCoordinator, spec: dict) -> None:
        self.coordinator = coordinator
        self._spec = spec
        slug = str(spec.get("slug") or "")
        planned = tracker_entities(coordinator.entry.entry_id, [slug])[0]
        self._attr_unique_id = planned["unique_id"]
        self.entity_id = planned["entity_id"]
        self._attr_name = f"Train {slug.replace('_', ' ').title()}"
        self._previous = None
        self._state = project_tracker(riding=False, latitude=None, longitude=None, now=0, previous=None)
        self._attrs: dict = {}
        self._picture = None
        station = coordinator.station
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"SEPTA {station}",
            manufacturer="SEPTA",
            model=_device_model(coordinator),
        )

    def _rider(self):
        ride = getattr(self.coordinator, "ride", None)
        if ride is None:
            return None
        for rider in ride.riders.values():
            if rider.slug == self._spec.get("slug"):
                return rider
        return None

    def _pull(self) -> None:
        rider = self._rider()
        now = time.time()
        train = None if rider is None else rider.matcher.riding_train
        riding = bool(rider is not None and rider.matcher.riding and train is not None)
        lat = lon = None
        if riding and train is not None:
            fresh = not position_is_stale(train, rider.matcher._trace.get(train.trainno))
            if fresh:
                lat, lon = train.lat, train.lon
        self._state = project_tracker(
            riding=riding,
            latitude=lat,
            longitude=lon,
            now=now,
            previous=self._previous,
        )
        self._previous = self._state.get("previous")
        self._picture = None
        own = {}
        if rider is not None:
            try:
                own = rider.attributes()
            except Exception:  # noqa: BLE001
                own = {}
            self._picture = own.get("entity_picture")
        rows = []
        ride = getattr(self.coordinator, "ride", None)
        if riding and ride is not None:
            for other in ride.riders.values():
                try:
                    rows.append(other.attributes())
                except Exception:  # noqa: BLE001
                    continue
        party = riders_on_train(rows, own.get("train")) if riding else []
        self._attrs = tracker_attributes(
            train=own.get("train"),
            line=own.get("line"),
            next_stop=own.get("next_stop"),
            destination=own.get("destination"),
            delay_min=own.get("delay_min") if own.get("delay_min") is not None else own.get("late_min"),
            consist=own.get("consist"),
            last_update=own.get("boarded_time") or own.get("last_fix"),
            riders=party,
            stale=bool(self._state.get("stale")),
        )
        self._attr_icon = tracker_icon(self._picture)

    @property
    def available(self) -> bool:
        return bool(self._state.get("available"))

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self._state.get("latitude")

    @property
    def longitude(self) -> float | None:
        return self._state.get("longitude")

    @property
    def location_accuracy(self) -> int:
        return int(self._state.get("location_accuracy") or 100)

    @property
    def entity_picture(self) -> str | None:
        return self._picture or None

    @property
    def extra_state_attributes(self) -> dict:
        return dict(self._attrs)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._pull()
        rider = self._rider()
        if rider is not None:
            self.async_on_remove(async_dispatcher_connect(self.hass, rider.signal(), self._on_ride))
        ride = getattr(self.coordinator, "ride", None)
        if ride is not None:
            self.async_on_remove(async_dispatcher_connect(self.hass, ride.summary_signal(), self._on_ride))
        write_state_on_loop(self.hass, self.async_write_ha_state)

    @callback
    def _on_ride(self, _payload=None) -> None:
        self._pull()
        write_state_on_loop(self.hass, self.async_write_ha_state)


def planned_tracker_ids(entry_id: str, slugs: list[str]) -> list[str]:
    return [item["unique_id"] for item in tracker_entities(entry_id, slugs)]


def unexpected_trackers(entry_id: str, slugs: list[str], registry_ids: list[str]) -> list[str]:
    return leftover_trackers(entry_id, slugs, registry_ids)
