"""Where a rider's train is drawn on the map. No Home Assistant."""

from __future__ import annotations

STALE_S = 300
ACCURACY_M = 100


def project_tracker(*, riding: bool, latitude, longitude, now: float, previous: dict | None, stale_s: float = STALE_S) -> dict:
    """Fresh TrainView position, then the last one for a few minutes, then nothing.

    A ride that has ended drops the point immediately so the map marker goes away.
    """
    if not riding:
        return {
            "latitude": None,
            "longitude": None,
            "stale": False,
            "available": False,
            "previous": None,
            "location_accuracy": ACCURACY_M,
            "source": "trainview",
        }
    if latitude is not None and longitude is not None:
        seen = {"latitude": float(latitude), "longitude": float(longitude), "ts": float(now)}
        return {
            "latitude": seen["latitude"],
            "longitude": seen["longitude"],
            "stale": False,
            "available": True,
            "previous": seen,
            "location_accuracy": ACCURACY_M,
            "source": "trainview",
        }
    if previous and float(now) - float(previous.get("ts") or 0) <= float(stale_s):
        return {
            "latitude": previous.get("latitude"),
            "longitude": previous.get("longitude"),
            "stale": True,
            "available": True,
            "previous": previous,
            "location_accuracy": ACCURACY_M,
            "source": "trainview",
        }
    return {
        "latitude": None,
        "longitude": None,
        "stale": False,
        "available": False,
        "previous": previous,
        "location_accuracy": ACCURACY_M,
        "source": "trainview",
    }


def tracker_icon(picture: object) -> str:
    """No profile picture uses the train icon. A picture is the entity image instead."""
    return "mdi:train"


def tracker_attributes(
    *,
    train,
    line,
    next_stop,
    destination,
    delay_min,
    consist,
    last_update,
    riders,
    stale: bool,
) -> dict:
    pictures = [str(item.get("entity_picture")) for item in (riders or []) if isinstance(item, dict) and item.get("entity_picture")]
    return {
        "train": train,
        "line": line,
        "next_stop": next_stop,
        "destination": destination,
        "delay_min": delay_min,
        "consist": list(consist or []),
        "last_update": last_update,
        "riders": list(riders or []),
        "rider_pictures": pictures,
        "source": "trainview",
        "stale": bool(stale),
    }


def tracker_entities(entry_id: str, slugs: list[str]) -> list[dict]:
    """One stable tracker per rider. Shared trains are two markers at the same point."""
    return [
        {
            "unique_id": f"{entry_id}_{slug}_train",
            "entity_id": f"device_tracker.septa_{slug}_train",
        }
        for slug in slugs
        if slug
    ]


def leftover_trackers(entry_id: str, slugs: list[str], registry_ids: list[str]) -> list[str]:
    wanted = {item["unique_id"] for item in tracker_entities(entry_id, slugs)}
    prefix = f"{entry_id}_"
    return [
        uid
        for uid in registry_ids
        if str(uid).startswith(prefix) and str(uid).endswith("_train") and uid not in wanted
    ]
