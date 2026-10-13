"""Trip parsing. No Home Assistant."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")


def _load():
    spec = importlib.util.spec_from_file_location("septa_trips", ROOT / "trips.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["septa_trips"] = module
    spec.loader.exec_module(module)
    return module


T = _load()


def test_parse_delay_and_on_time():
    now = datetime(2026, 10, 13, 13, 0, tzinfo=NY)
    raw = [
        {
            "orig_train": "6582",
            "orig_line": "Lansdale/Doylestown",
            "orig_departure_time": "2:20PM",
            "orig_arrival_time": "3:05PM",
            "orig_delay": "15 mins",
            "isdirect": "true",
        },
        {
            "orig_train": "6584",
            "orig_line": "Lansdale/Doylestown",
            "orig_departure_time": "3:00PM",
            "orig_arrival_time": "3:40PM",
            "orig_delay": "On time",
            "isdirect": "false",
            "term_train": "6701",
            "term_line": "Airport",
            "term_depart_time": "3:20PM",
            "Connection": "Suburban Station",
        },
    ]
    rows, error = T.parse_next_to_arrive(raw, now, 4)
    assert error is None
    assert rows[0]["train"] == "6582"
    assert rows[0]["delay_min"] == 15
    assert rows[0]["minutes"] == 95
    assert rows[0]["direct"] is True
    assert rows[0]["connection"] is None
    assert rows[0]["depart_sched"].startswith("2026-10-13T14:20:00")
    assert rows[0]["depart_est"].startswith("2026-10-13T14:35:00")
    assert rows[1]["delay_min"] == 0
    assert rows[1]["minutes"] == 120
    assert rows[1]["direct"] is False
    assert rows[1]["connection"]["station"] == "Suburban Station"
    assert rows[1]["connection"]["train"] == "6701"
    assert rows[1]["connection"]["line"] == "Airport"
    assert rows[1]["connection"]["depart"].startswith("2026-10-13T15:20:00")


def test_30th_street_aliases():
    assert T.nta_station("Gray 30th Street") == "30th Street Station"
    assert T.nta_station("30th Street Gray") == "30th Street Station"
    assert T.nta_station("gray-30th street station") == "30th Street Station"
    assert T.nta_station("Lansdale") == "Lansdale"


def test_rejected_station_does_not_raise():
    rows, error = T.parse_next_to_arrive({"error": "Invalid station"}, datetime(2026, 10, 13, 13, 0, tzinfo=NY))
    assert rows == []
    assert "Invalid" in error


def test_timetable_fallback_direct_trains():
    schedule = {
        "stations": {
            "Suburban Station": {"N": [{"t": "15:10", "n": "123", "line": "LAN", "days": 127, "d": "Doylestown"}]},
            "Lansdale": {"N": [{"t": "15:55", "n": "123", "line": "LAN", "days": 127, "d": "Doylestown"}]},
            "Jefferson Station": {"N": [{"t": "15:00", "n": "999", "line": "LAN", "days": 127, "d": "Doylestown"}]},
        }
    }
    now = datetime(2026, 10, 13, 14, 0, tzinfo=NY)
    rows = T.timetable_trips(schedule, "Suburban Station", "Lansdale", now, 4, {"LAN": "Lansdale/Doylestown"})
    assert rows
    assert rows[0]["train"] == "123"
    assert rows[0]["line"] == "Lansdale/Doylestown"
    assert rows[0]["delay_min"] is None
    assert rows[0]["direct"] is True
    assert rows[0]["minutes"] == 70
    assert all(row["train"] != "999" for row in rows)


def test_entity_id_stays_when_stations_change():
    first = T.trip_ids("abc", "homebound")
    second = T.trip_ids("abc", "homebound")
    assert first == second == ("abc_trip_homebound", "sensor.septa_trip_homebound")
    saved = T.clean_trips(
        [{"id": "homebound", "origin": "Suburban Station", "destination": "Lansdale", "count": 4}]
    )
    changed = T.clean_trips(
        [{"id": "homebound", "origin": "Jefferson Station", "destination": "Lansdale", "count": 6, "label": "Home"}]
    )
    assert saved[0]["id"] == changed[0]["id"] == "homebound"
    assert T.trip_ids("abc", saved[0]["id"]) == T.trip_ids("abc", changed[0]["id"])
    assert "suburban" not in first[0]
    assert "jefferson" not in first[1]
