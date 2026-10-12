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
        return {"ride": None}
    matcher = ride.matcher
    return {
        "ride": _redact(ride.attributes()),
        "settings": {
            "radius_m": matcher.radius_m,
            "min_speed_mph": round(matcher.min_speed_mps / 0.44704, 1),
            "need_matches": matcher.need_matches,
            "max_accuracy_m": matcher.max_accuracy_m,
            "max_fix_age_s": matcher.max_fix_age_s,
            "preferred_line": matcher.preferred_line,
        },
        "reasons": list(matcher.reason_log),
    }
