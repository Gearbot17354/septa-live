"""Diagnostics for SEPTA Transit. Coordinates are redacted."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_HIDDEN = {"lat", "lon", "latitude", "longitude"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("redacted" if str(key).lower() in _HIDDEN else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coordinator = (hass.data.get(DOMAIN) or {}).get(entry.entry_id)
    ride = getattr(coordinator, "ride", None) if coordinator is not None else None
    if ride is None:
        trips = coordinator.configured_trips() if coordinator is not None and hasattr(coordinator, "configured_trips") else []
        dynamic = getattr(coordinator, "dynamic", None) if coordinator is not None else None
        schedule = None
        keeper = getattr(coordinator, "rail_schedule", None) if coordinator is not None else None
        if keeper is not None and hasattr(keeper, "status"):
            try:
                schedule = keeper.status()
            except Exception:  # noqa: BLE001
                schedule = None
        return {
            "ride": None,
            "trips": trips,
            "trip_response_lengths": dict(getattr(coordinator, "trip_raw_lengths", {}) or {}),
            "dynamic": dynamic.diagnostics() if dynamic is not None else None,
            "rail_schedule": schedule,
        }
    riders = []
    for rider in getattr(ride, "riders", {}).values():
        matcher = rider.matcher
        riders.append(
            {
                "slug": rider.slug,
                "person": rider.person,
                "primary": rider.is_primary,
                "ride": _redact(rider.attributes()),
                "settings": {
                    "radius_m": matcher.radius_m,
                    "min_speed_mph": round(matcher.min_speed_mps / 0.44704, 1),
                    "need_matches": matcher.need_matches,
                    "max_accuracy_m": matcher.max_accuracy_m,
                    "max_fix_age_s": matcher.max_fix_age_s,
                    "preferred_line": matcher.preferred_line,
                    "cooldown_train": matcher.cooldown_train,
                    "cooldown_until": matcher.cooldown_until,
                    "gps_quality": matcher.gps_quality,
                    "corridor_source": matcher.corridor_source,
                    "corridor_gap_m": matcher.corridor_gap_m,
                    "hold_reason": matcher.hold_reason,
                    "learned_underground": list(matcher.learned_underground),
                    "decisions": list(matcher.decisions),
                    "resumed": matcher.resumed,
                },
                "reasons": list(matcher.reason_log),
            }
        )
    primary = ride.matcher
    trips = coordinator.configured_trips() if coordinator is not None and hasattr(coordinator, "configured_trips") else []
    dynamic = getattr(coordinator, "dynamic", None) if coordinator is not None else None
    dynamic_info = dynamic.diagnostics() if dynamic is not None else None
    schedule = None
    keeper = getattr(coordinator, "rail_schedule", None) if coordinator is not None else None
    if keeper is not None and hasattr(keeper, "status"):
        try:
            schedule = keeper.status()
        except Exception:  # noqa: BLE001
            schedule = None
    return {
        "ride": _redact(ride.attributes()),
        "riders": riders,
        "trips": trips,
        "trip_response_lengths": dict(getattr(coordinator, "trip_raw_lengths", {}) or {}),
        "dynamic": dynamic_info,
        "rail_schedule": schedule,
        "settings": {
            "radius_m": primary.radius_m,
            "min_speed_mph": round(primary.min_speed_mps / 0.44704, 1),
            "need_matches": primary.need_matches,
            "max_accuracy_m": primary.max_accuracy_m,
            "max_fix_age_s": primary.max_fix_age_s,
            "preferred_line": primary.preferred_line,
            "cooldown_train": primary.cooldown_train,
            "cooldown_until": primary.cooldown_until,
            "gps_quality": primary.gps_quality,
            "corridor_source": primary.corridor_source,
            "corridor_gap_m": primary.corridor_gap_m,
            "hold_reason": primary.hold_reason,
            "learned_underground": list(primary.learned_underground),
            "decisions": list(primary.decisions),
            "resumed": primary.resumed,
        },
        "reasons": list(primary.reason_log),
    }
