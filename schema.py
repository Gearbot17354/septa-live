"""Service and websocket schemas. Numbers from templates become strings. No Home Assistant."""

from __future__ import annotations

import voluptuous as vol

# The same ranges the options UI uses.
_RANGES = {
    "walk_minutes": (0, 60),
    "ride_radius_m": (100, 1500),
    "ride_min_speed_mph": (5, 60),
    "ride_matches": (1, 5),
    "ride_max_accuracy_m": (20, 500),
}


def as_text(value):
    """String coerce. Whole floats drop the trailing .0. None is rejected."""
    if value is None:
        raise vol.Invalid("string value is None")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, (list, dict)):
        raise vol.Invalid("expected a string")
    return str(value).strip()


def opt_str(value):
    """Optional text. None and a blank string are 'not set' and do not raise."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    text = as_text(value).strip()
    return text or None


def train_id(value):
    """Train number. Digits are canonical. Blank means no train. Alphanumeric ids stay."""
    text = opt_str(value)
    if text is None:
        return None
    compact = text.replace(" ", "")
    if compact.isdigit():
        return str(int(compact))
    return text


def opt_bool(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in (0, 1, 0.0, 1.0):
            return bool(int(value))
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise vol.Invalid("expected a boolean")


def ranged_int(low: int, high: int):
    def _check(value):
        if isinstance(value, bool) or value is None or value == "":
            raise vol.Invalid("expected an integer")
        if isinstance(value, str):
            text = value.strip()
            if text.endswith(".0"):
                text = text[:-2]
            try:
                number = int(text)
            except ValueError as err:
                raise vol.Invalid("expected an integer") from err
        elif isinstance(value, float):
            if not value.is_integer():
                raise vol.Invalid("expected an integer")
            number = int(value)
        elif isinstance(value, int):
            number = value
        else:
            raise vol.Invalid("expected an integer")
        if number < low or number > high:
            raise vol.Invalid(f"value must be {low}-{high}")
        return number

    return _check


def _loose_row(value):
    if not isinstance(value, dict):
        raise vol.Invalid("expected a mapping")
    out = dict(value)
    for key in ("train", "trainno"):
        if key in out:
            out[key] = train_id(out[key])
    for key in ("id", "stop_id"):
        if key in out:
            out[key] = opt_str(out[key])
    return out


def mapping_list(value):
    if value is None:
        return None
    if not isinstance(value, list):
        raise vol.Invalid("expected a list")
    return [_loose_row(item) for item in value]


def _int(name: str):
    low, high = _RANGES[name]
    return ranged_int(low, high)


SIMULATE_RIDE = vol.Schema(
    {
        vol.Required("entry_id"): as_text,
        vol.Required("fixes"): mapping_list,
        vol.Optional("trainview"): mapping_list,
        vol.Optional("rider"): opt_str,
        vol.Optional("expected_train"): train_id,
    }
)

REFRESH_TRIPS = vol.Schema(
    {
        vol.Optional("entry_id"): opt_str,
        vol.Optional("trip_id"): opt_str,
    }
)

SET_EXPECTED = vol.Schema(
    {
        vol.Optional("entry_id"): opt_str,
        vol.Optional("rider"): opt_str,
        vol.Optional("train"): train_id,
        vol.Optional("origin"): opt_str,
        vol.Optional("destination"): opt_str,
        vol.Optional("connection_train"): train_id,
        vol.Optional("connection_station"): opt_str,
        vol.Optional("valid_until"): opt_str,
    }
)

STATION_SERVICE = vol.Schema(
    {
        vol.Optional("entry_id"): opt_str,
        vol.Optional("rider"): opt_str,
        vol.Optional("station"): opt_str,
    }
)

REFRESH_SCHEDULE = vol.Schema(
    {
        vol.Optional("entry_id"): opt_str,
        vol.Optional("force"): opt_bool,
    }
)

WEBSOCKET_BOARD = {
    vol.Required("type"): "septa_live/board",
    vol.Required("station"): as_text,
}

WEBSOCKET_PANEL = {vol.Required("type"): "septa_live/panel"}

WEBSOCKET_BUS = {
    vol.Required("type"): "septa_live/bus_picker",
    vol.Required("entry_id"): as_text,
    vol.Optional("route"): opt_str,
    vol.Optional("stop_id"): opt_str,
}

WEBSOCKET_OPTIONS = {
    vol.Required("type"): "septa_live/options",
    vol.Required("entry_id"): as_text,
    vol.Optional("destination"): opt_str,
    vol.Optional("walk_minutes"): _int("walk_minutes"),
    vol.Optional("show_sidebar"): opt_bool,
    vol.Optional("show_rail"): opt_bool,
    vol.Optional("show_bus"): opt_bool,
    vol.Optional("show_metro"): opt_bool,
    vol.Optional("show_trolley"): opt_bool,
    vol.Optional("station"): opt_str,
    vol.Optional("rail_line"): opt_str,
    vol.Optional("bus_line"): opt_str,
    vol.Optional("bus_stop"): opt_str,
    vol.Optional("bus_destination"): opt_str,
    vol.Optional("metro_line"): opt_str,
    vol.Optional("trolley_line"): opt_str,
    vol.Optional("metro_home"): opt_str,
    vol.Optional("metro_dest"): opt_str,
    vol.Optional("trolley_home"): opt_str,
    vol.Optional("trolley_dest"): opt_str,
    vol.Optional("watches"): mapping_list,
    vol.Optional("trips"): mapping_list,
    vol.Optional("ride_tracker"): opt_str,
    vol.Optional("ride_radius_m"): _int("ride_radius_m"),
    vol.Optional("ride_min_speed_mph"): _int("ride_min_speed_mph"),
    vol.Optional("ride_matches"): _int("ride_matches"),
    vol.Optional("ride_max_accuracy_m"): _int("ride_max_accuracy_m"),
    vol.Optional("ride_request_updates"): opt_bool,
}

SERVICE_SCHEMAS = {
    "simulate_ride": SIMULATE_RIDE,
    "refresh_trips": REFRESH_TRIPS,
    "set_expected_train": SET_EXPECTED,
    "set_origin_station": STATION_SERVICE,
    "set_destination": STATION_SERVICE,
    "refresh_schedule": REFRESH_SCHEDULE,
}

WEBSOCKET_SCHEMAS = {
    "septa_live/board": WEBSOCKET_BOARD,
    "septa_live/panel": WEBSOCKET_PANEL,
    "septa_live/bus_picker": WEBSOCKET_BUS,
    "septa_live/options": WEBSOCKET_OPTIONS,
}


def _walk(node, found: list) -> None:
    if node is str or node is int or node is bool:
        found.append(node)
        return
    if isinstance(node, vol.Schema):
        _walk(node.schema, found)
        return
    marker = getattr(node, "schema", None)
    if isinstance(node, (vol.Required, vol.Optional, vol.Exclusive, vol.Inclusive)):
        _walk(node.schema, found)
        return
    validators = getattr(node, "validators", None)
    if validators is not None and not isinstance(node, (str, bytes)):
        for item in validators:
            _walk(item, found)
        return
    if isinstance(node, dict):
        for key, value in node.items():
            _walk(key, found)
            _walk(value, found)
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            _walk(item, found)
        return
    if marker is not None and marker is not node:
        _walk(marker, found)


def bare_leaves(schema) -> list:
    """Type objects str/int/bool used as validators. Literals are not counted."""
    found: list = []
    _walk(schema, found)
    return found


def all_bare_leaves() -> list:
    found: list = []
    for schema in list(SERVICE_SCHEMAS.values()) + list(WEBSOCKET_SCHEMAS.values()):
        found.extend(bare_leaves(schema))
    return found
