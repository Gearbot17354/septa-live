"""Entity id stability. No Home Assistant required."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("septa_ids", ROOT / "ids.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["septa_ids"] = module
    spec.loader.exec_module(module)
    return module


ids = _load()
canonical_entity_id = ids.canonical_entity_id
legacy_key = ids.legacy_key
pick_leave = ids.pick_leave
plan_registry_migration = ids.plan_registry_migration
stable_unique_id = ids.stable_unique_id


def test_unique_id_ignores_destination():
    first = stable_unique_id("abc", "my_train")
    second = stable_unique_id("abc", "my_train")
    assert first == second == "abc_my_train"
    assert "jefferson" not in first
    assert "suburban" not in first
    assert canonical_entity_id("sensor", "Lansdale", "south") == "sensor.septa_lansdale_next_southbound"
    assert canonical_entity_id("sensor", "Lansdale", "my_train") == "sensor.septa_lansdale_my_train"
    assert canonical_entity_id("binary_sensor", "Lansdale", "riding") == "binary_sensor.septa_lansdale_riding"
    assert canonical_entity_id("sensor", "Lansdale", "riders_count") == "sensor.septa_riders_count"
    assert canonical_entity_id("sensor", "Lansdale", "my_train_sam") == "sensor.septa_my_train_sam"


def test_registry_with_suffix_2_migrates_back():
    items = [
        {
            "unique_id": "lansdale_jefferson_station_leave_in",
            "entity_id": "sensor.septa_lansdale_leave_in",
            "domain": "sensor",
        },
        {
            "unique_id": "lansdale_suburban_station_leave_in",
            "entity_id": "sensor.septa_lansdale_leave_in_2",
            "domain": "sensor",
        },
        {
            "unique_id": "lansdale_suburban_station_south",
            "entity_id": "sensor.septa_lansdale_next_inbound",
            "domain": "sensor",
        },
        {
            "unique_id": "lansdale_suburban_station_my_train",
            "entity_id": "sensor.septa_lansdale_my_train_2",
            "domain": "sensor",
        },
        {
            "unique_id": "lansdale_suburban_station_riding",
            "entity_id": "binary_sensor.septa_lansdale_riding_2",
            "domain": "binary_sensor",
        },
        {
            "unique_id": "lansdale_suburban_station_my_train_brandon",
            "entity_id": "sensor.septa_my_train_brandon_2",
            "domain": "sensor",
        },
        {
            "unique_id": "lansdale_suburban_station_riding_rachael",
            "entity_id": "binary_sensor.septa_riding_rachael_2",
            "domain": "binary_sensor",
        },
        {
            "unique_id": "lansdale_suburban_station_riders_count",
            "entity_id": "sensor.septa_riders_count_2",
            "domain": "sensor",
        },
        {
            "unique_id": "lansdale_jefferson_station_status",
            "entity_id": "sensor.my_custom_status",
            "domain": "sensor",
        },
    ]
    actions = plan_registry_migration("abc", "Lansdale", items)
    removed = {item["entity_id"] for item in actions if item["op"] == "remove"}
    renamed = {item["entity_id"]: item["new_entity_id"] for item in actions if item["op"] == "rename"}
    unique = {item["entity_id"]: item["unique_id"] for item in actions if item["op"] == "unique_id"}
    assert "sensor.septa_lansdale_leave_in_2" in removed
    assert "sensor.septa_lansdale_leave_in" not in removed
    assert unique["sensor.septa_lansdale_leave_in"] == "abc_leave_in"
    assert renamed["sensor.septa_lansdale_next_inbound"] == "sensor.septa_lansdale_next_southbound"
    assert renamed["sensor.septa_lansdale_my_train_2"] == "sensor.septa_lansdale_my_train"
    assert renamed["binary_sensor.septa_lansdale_riding_2"] == "binary_sensor.septa_lansdale_riding"
    assert renamed["sensor.septa_my_train_brandon_2"] == "sensor.septa_my_train_brandon"
    assert renamed["binary_sensor.septa_riding_rachael_2"] == "binary_sensor.septa_riding_rachael"
    assert renamed["sensor.septa_riders_count_2"] == "sensor.septa_riders_count"
    assert "sensor.my_custom_status" not in renamed
    assert unique["sensor.my_custom_status"] == "abc_status"
    assert legacy_key("abc_my_train") == "my_train"


def test_adding_a_rider_does_not_change_existing_ids():
    before = {
        "my_train": stable_unique_id("abc", "my_train"),
        "riding": stable_unique_id("abc", "riding"),
        "south": stable_unique_id("abc", "south"),
    }
    after = dict(before)
    after["riding_sam"] = stable_unique_id("abc", "riding_sam")
    assert after["my_train"] == before["my_train"]
    assert after["riding"] == before["riding"]
    assert after["south"] == before["south"]
    changed_dest = stable_unique_id("abc", "leave_in")
    assert changed_dest == stable_unique_id("abc", "leave_in")


def test_primary_station_ids_rename_to_the_rider_and_custom_ids_stay():
    items = [
        {
            "unique_id": "abc_riding",
            "entity_id": "binary_sensor.septa_lansdale_riding",
            "domain": "binary_sensor",
        },
        {
            "unique_id": "abc_my_train",
            "entity_id": "sensor.septa_lansdale_my_train",
            "domain": "sensor",
        },
        {
            "unique_id": "abc_status",
            "entity_id": "sensor.my_custom_status",
            "domain": "sensor",
        },
    ]
    actions = plan_registry_migration("abc", "Lansdale", items, primary_slug="ryan")
    renamed = {item["entity_id"]: item["new_entity_id"] for item in actions if item["op"] == "rename"}
    assert renamed["binary_sensor.septa_lansdale_riding"] == "binary_sensor.septa_riding_ryan"
    assert renamed["sensor.septa_lansdale_my_train"] == "sensor.septa_my_train_ryan"
    assert "sensor.my_custom_status" not in renamed
    assert not [item for item in actions if item["op"] == "unique_id" and item["entity_id"] in renamed]
    custom = [
        {
            "unique_id": "abc_riding",
            "entity_id": "binary_sensor.my_custom_riding",
            "domain": "binary_sensor",
        },
        {
            "unique_id": "abc_my_train",
            "entity_id": "sensor.septa_lansdale_my_train",
            "domain": "sensor",
        },
        {
            "unique_id": "other_my_train_ryan",
            "entity_id": "sensor.septa_my_train_ryan",
            "domain": "sensor",
        },
    ]
    held = plan_registry_migration("abc", "Lansdale", custom, primary_slug="ryan")
    renamed = {item["entity_id"]: item["new_entity_id"] for item in held if item["op"] == "rename"}
    assert "binary_sensor.my_custom_riding" not in renamed
    assert "sensor.septa_lansdale_my_train" not in renamed
    skipped = [item for item in held if item["op"] == "skip"]
    assert skipped and skipped[0]["new_entity_id"] == "sensor.septa_my_train_ryan"
    targets = [item["new_entity_id"] for item in held if item["op"] == "rename"]
    assert len(targets) == len(set(targets))


def test_dynamic_sensors_are_named_for_every_rider():
    items = [
        {"unique_id": "abc_going_home", "entity_id": "sensor.septa_going_home", "domain": "sensor"},
        {"unique_id": "abc_day_trains", "entity_id": "sensor.septa_day_trains", "domain": "sensor"},
        {
            "unique_id": "abc_riding",
            "entity_id": "binary_sensor.septa_north_end_riding",
            "domain": "binary_sensor",
        },
    ]
    actions = plan_registry_migration("abc", "North End", items, primary_slug="alpha")
    renamed = {item["entity_id"]: item["new_entity_id"] for item in actions if item["op"] == "rename"}
    assert renamed["sensor.septa_going_home"] == "sensor.septa_going_home_alpha"
    assert renamed["sensor.septa_day_trains"] == "sensor.septa_day_trains_alpha"
    assert renamed["binary_sensor.septa_north_end_riding"] == "binary_sensor.septa_riding_alpha"
    assert not [item for item in actions if item["op"] == "unique_id"]
    moved = [
        {"unique_id": "abc_going_home", "entity_id": "sensor.septa_going_home_alpha", "domain": "sensor"},
        {"unique_id": "abc_day_trains", "entity_id": "sensor.septa_day_trains_alpha", "domain": "sensor"},
    ]
    again = plan_registry_migration("abc", "North End", moved, primary_slug="alpha")
    assert not [item for item in again if item["op"] in {"rename", "remove", "skip"}]
    taken = [
        {"unique_id": "abc_going_home", "entity_id": "sensor.septa_going_home", "domain": "sensor"},
        {"unique_id": "abc_going_home_alpha", "entity_id": "sensor.septa_going_home_alpha", "domain": "sensor"},
    ]
    blocked = plan_registry_migration("abc", "North End", taken, primary_slug="alpha")
    skipped = [item for item in blocked if item["op"] == "skip"]
    assert skipped and skipped[0]["reason"] == "target_taken"
    assert skipped[0]["new_entity_id"] == "sensor.septa_going_home_alpha"
    custom = [
        {"unique_id": "abc_going_home", "entity_id": "sensor.my_home_trains", "domain": "sensor"},
        {"unique_id": "abc_day_trains", "entity_id": "sensor.septa_day_trains_alpha", "domain": "sensor"},
    ]
    held = plan_registry_migration("abc", "North End", custom, primary_slug="bravo")
    assert not [item for item in held if item["op"] == "rename"]
    bare = [
        {"unique_id": "abc_going_home", "entity_id": "sensor.septa_going_home", "domain": "sensor"},
        {"unique_id": "abc_going_home_bravo", "entity_id": "sensor.septa_going_home_bravo", "domain": "sensor"},
    ]
    changed = plan_registry_migration("abc", "North End", bare, primary_slug="bravo")
    assert any(item["op"] == "skip" and item["new_entity_id"] == "sensor.septa_going_home_bravo" for item in changed)


def test_integration_version_matches_manifest():
    import json

    spec = importlib.util.spec_from_file_location("septa_const_ver", ROOT / "const.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert module.integration_version() == manifest["version"] == "1.13.4"


def test_leave_in_is_never_negative():
    now = datetime(2026, 10, 12, 8, 0)
    gone = {"depart_dt": now - timedelta(minutes=5), "train_id": "1"}
    later = {"depart_dt": now + timedelta(minutes=20), "train_id": "2"}
    mins, row = pick_leave([gone, later], 8, now)
    assert mins == 12
    assert row["train_id"] == "2"
    mins, row = pick_leave([gone], 8, now)
    assert mins == 0
    assert row["train_id"] == "1"
    assert pick_leave([], 8, now) == (None, None)
