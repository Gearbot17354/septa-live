"""Stable entity ids. Unique ids must not include the station or destination."""

from __future__ import annotations

import re

_OBJECT_KEY = {
    "south": "next_southbound",
    "north": "next_northbound",
    "south_board": "inbound_board",
    "north_board": "outbound_board",
}

# Older releases used these object ids. They map back to the internal key.
_TAIL_TO_KEY = (
    ("south_board", "south_board"),
    ("north_board", "north_board"),
    ("inbound_board", "south_board"),
    ("outbound_board", "north_board"),
    ("southbound_board", "south_board"),
    ("northbound_board", "north_board"),
    ("next_southbound", "south"),
    ("next_northbound", "north"),
    ("next_inbound", "south"),
    ("next_outbound", "north"),
    ("leave_in", "leave_in"),
    ("riders_count", "riders_count"),
    ("next_bus", "next_bus"),
    ("my_train", "my_train"),
    ("riding", "riding"),
    ("status", "status"),
    ("metro", "metro"),
    ("trolley", "trolley"),
    ("map", "map"),
    ("south", "south"),
    ("north", "north"),
)

_BAD_OBJECT = {
    "next_inbound": "next_southbound",
    "next_outbound": "next_northbound",
}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name or "").lower()).strip("_")


def stable_unique_id(entry_id: str, key: str) -> str:
    return f"{entry_id}_{key}"


def object_key(key: str) -> str:
    return _OBJECT_KEY.get(key, key)


def canonical_entity_id(domain: str, station: str, key: str) -> str | None:
    station_slug = slug(station) or "septa"
    if domain == "binary_sensor":
        if key == "riding":
            return f"binary_sensor.septa_{station_slug}_riding"
        if key.startswith("riding_"):
            return f"binary_sensor.septa_riding_{key[len('riding_'):]}"
        return None
    if key == "riders_count":
        return "sensor.septa_riders_count"
    if key.startswith("my_train_") and key != "my_train":
        return f"sensor.septa_my_train_{key[len('my_train_'):]}"
    if not key:
        return None
    return f"sensor.septa_{station_slug}_{object_key(key)}"


def legacy_key(unique_id: str) -> str | None:
    """Internal key from an old station_destination unique id, or from a stable one."""
    uid = str(unique_id or "")
    if not uid:
        return None
    for marker in ("_my_train_", "_riding_"):
        idx = uid.rfind(marker)
        if idx != -1:
            return uid[idx + 1 :]
    line = uid.find("_line_")
    if line != -1:
        return uid[line + 1 :]
    for tail, key in _TAIL_TO_KEY:
        if uid.endswith("_" + tail) or uid == tail:
            return key
    return None


def _collision_base(entity_id: str) -> str | None:
    head, _, last = str(entity_id or "").rpartition("_")
    if head and last.isdigit():
        return head
    return None


def _is_generated_alias(entity_id: str, canonical: str) -> bool:
    """True for a _2 collision or for next_inbound, which this integration renamed."""
    if not canonical:
        return False
    if entity_id == canonical:
        return False
    base = _collision_base(entity_id) or entity_id
    if base == canonical:
        return True
    for old, new in _BAD_OBJECT.items():
        if base.endswith("_" + old) and base[: -len(old)] + new == canonical:
            return True
    return False


def plan_registry_migration(entry_id: str, station: str, items: list[dict]) -> list[dict]:
    """Rename _2 entities back and point every old unique id at the stable one.

    A hand-renamed entity id is left alone. Only collision suffixes and the
    inbound/outbound object ids this integration introduced are moved.
    """
    groups: dict[str, list[dict]] = {}
    for item in items:
        key = legacy_key(str(item.get("unique_id") or ""))
        if not key:
            continue
        groups.setdefault(key, []).append(item)
    occupied = {str(item.get("entity_id") or "") for item in items}
    removes: list[dict] = []
    unique_updates: list[dict] = []
    renames: list[dict] = []
    for key, group in groups.items():
        domain = str(group[0].get("domain") or "sensor")
        canonical = canonical_entity_id(domain, station, key)
        desired = stable_unique_id(entry_id, key)

        def rank(item: dict) -> tuple:
            eid = str(item.get("entity_id") or "")
            if eid == canonical:
                return (0, eid)
            if _is_generated_alias(eid, canonical or ""):
                return (1, eid)
            return (2, eid)

        ordered = sorted(group, key=rank)
        keep = ordered[0]
        for extra in ordered[1:]:
            eid = str(extra.get("entity_id") or "")
            removes.append({"op": "remove", "entity_id": eid})
            occupied.discard(eid)
        keep_id = str(keep.get("entity_id") or "")
        if str(keep.get("unique_id") or "") != desired:
            unique_updates.append({"op": "unique_id", "entity_id": keep_id, "unique_id": desired})
        if canonical and _is_generated_alias(keep_id, canonical) and canonical not in occupied:
            renames.append({"op": "rename", "entity_id": keep_id, "new_entity_id": canonical})
            occupied.discard(keep_id)
            occupied.add(canonical)
    return removes + unique_updates + renames


def pick_leave(departures: list, walk: int, now) -> tuple[int | None, dict | None]:
    """Next train you can still walk to. Zero when every train has already left."""
    first = None
    for row in departures:
        if not isinstance(row, dict):
            continue
        depart = row.get("depart_dt")
        if depart is None:
            continue
        if first is None:
            first = row
        try:
            mins = int(round(((depart - now).total_seconds() / 60))) - int(walk or 0)
        except (TypeError, ValueError, AttributeError):
            continue
        if mins >= 0:
            return mins, row
    if first is not None:
        return 0, first
    return None, None
