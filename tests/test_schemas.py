"""Service schemas accept numbers from templates. No Home Assistant."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1]


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S = _load("septa_schema", "schema.py")


def _sample_train() -> int:
    raw = json.loads((ROOT / "rail-schedule.json").read_text())
    for pack in (raw.get("stations") or {}).values():
        if not isinstance(pack, dict):
            continue
        for direction in ("N", "S"):
            for row in pack.get(direction) or []:
                number = str((row or {}).get("n") or "")
                if number.isdigit():
                    return int(number)
    raise AssertionError("bundled schedule has no train number")


def test_expected_train_accepts_an_int():
    number = _sample_train()
    parsed = S.SET_EXPECTED({"train": number})
    assert parsed["train"] == str(number)
    assert isinstance(parsed["train"], str)


def test_train_text_is_stripped_and_whole_floats_drop_the_decimal():
    assert S.SET_EXPECTED({"train": " 1234 "})["train"] == "1234"
    assert S.SET_EXPECTED({"train": "1234"})["train"] == "1234"
    assert S.SET_EXPECTED({"train": 1234.0})["train"] == "1234"
    assert S.train_id("12A") == "12A"


def test_blank_train_matches_a_missing_train():
    assert S.SET_EXPECTED({"train": ""}).get("train") is None
    assert S.SET_EXPECTED({"train": None}).get("train") is None
    assert S.SET_EXPECTED({}).get("train") is None


def test_other_ids_accept_ints():
    assert S.SET_EXPECTED({"connection_train": 42})["connection_train"] == "42"
    assert S.SIMULATE_RIDE({"entry_id": "abc", "fixes": [], "expected_train": 42})["expected_train"] == "42"
    assert S.REFRESH_TRIPS({"trip_id": 7})["trip_id"] == "7"
    assert S.STATION_SERVICE({"station": 30, "rider": 2})["station"] == "30"
    assert S.STATION_SERVICE({"rider": " alpha "})["rider"] == "alpha"


def test_bus_stop_and_radius_coerce():
    assert S.opt_str(12345) == "12345"
    schema = vol.Schema(S.WEBSOCKET_OPTIONS)
    parsed = schema({"type": "septa_live/options", "entry_id": "abc", "ride_radius_m": "300"})
    assert parsed["ride_radius_m"] == 300
    try:
        schema({"type": "septa_live/options", "entry_id": "abc", "ride_radius_m": "10"})
    except vol.Invalid:
        failed = True
    else:
        failed = False
    assert failed
    bus = vol.Schema(S.WEBSOCKET_BUS)
    assert bus({"type": "septa_live/bus_picker", "entry_id": "abc", "stop_id": 12345})["stop_id"] == "12345"


def test_existing_string_payloads_stay_strings():
    payload = {
        "entry_id": "abc",
        "rider": "alpha",
        "train": "1001",
        "origin": "North End",
        "destination": "Hub",
        "connection_train": "1002",
        "connection_station": "Hub",
        "valid_until": "2026-10-14T18:00:00",
    }
    assert S.SET_EXPECTED(payload)["train"] == "1001"
    assert S.SET_EXPECTED(payload)["origin"] == "North End"
    assert S.REFRESH_TRIPS({"entry_id": "abc", "trip_id": "trip-1"})["trip_id"] == "trip-1"


def test_no_bare_str_int_or_bool_validators():
    assert S.all_bare_leaves() == []
    text = (ROOT / "__init__.py").read_text()
    assert "SET_EXPECTED" in text
    assert "WEBSOCKET_OPTIONS" in text
    assert "): str" not in text
    assert "): int" not in text
    assert "): bool" not in text
