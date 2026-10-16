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
    assert T.nta_station("Gray 30th St Station") == "30th Street Station"
    assert T.nta_station("30th St") == "30th Street Station"
    assert T.nta_station("Gray 30th Street") == "30th Street Station"
    assert T.nta_station("Fern Rock Transit Center") == "Fern Rock Transportation Center"
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


def test_connection_uses_term_arrival_and_delay():
    now = datetime(2026, 10, 13, 15, 0, tzinfo=NY)
    raw = [
        {
            "orig_train": "6541",
            "orig_line": "Lansdale/Doylestown",
            "orig_departure_time": "3:14PM",
            "orig_arrival_time": "4:12PM",
            "orig_delay": "On time",
            "term_train": "449",
            "term_line": "Airport",
            "term_depart_time": "4:25PM",
            "term_arrival_time": "4:32PM",
            "Connection": "Suburban Station",
            "term_delay": "On time",
            "isdirect": "false",
        }
    ]
    rows, error = T.parse_next_to_arrive(raw, now, 4, 3)
    assert error is None
    row = rows[0]
    assert row["direct"] is False
    assert row["delay_min"] == 0
    assert row["depart_sched"].startswith("2026-10-13T15:14:00")
    assert row["arrive_sched"].startswith("2026-10-13T16:32:00")
    assert row["arrive_est"].startswith("2026-10-13T16:32:00")
    link = row["connection"]
    assert link["station"] == "Suburban Station"
    assert link["train"] == "449"
    assert link["arrive_sched"].startswith("2026-10-13T16:12:00")
    assert link["depart_sched"].startswith("2026-10-13T16:25:00")
    assert link["arrive_final_sched"].startswith("2026-10-13T16:32:00")
    assert link["delay_min"] == 0
    assert link["wait_min"] == 13
    assert link["at_risk"] is False


def test_day_merge_and_transfer_window():
    schedule = {
        "stations": {
            "Origin": {
                "N": [
                    {"t": "09:00", "n": "10", "line": "LAN", "days": 127, "d": "Dest"},
                    {"t": "08:00", "n": "11", "line": "LAN", "days": 127, "d": "Mid"},
                ]
            },
            "Mid": {
                "S": [
                    {"t": "08:20", "n": "11", "line": "LAN", "days": 127, "d": "Mid"},
                    {"t": "08:22", "n": "20", "line": "AIR", "days": 127, "d": "Dest"},
                    {"t": "08:24", "n": "21", "line": "AIR", "days": 127, "d": "Dest"},
                ]
            },
            "Dest": {
                "S": [
                    {"t": "09:40", "n": "10", "line": "LAN", "days": 127, "d": "Dest"},
                    {"t": "08:40", "n": "20", "line": "AIR", "days": 127, "d": "Dest"},
                    {"t": "08:50", "n": "21", "line": "AIR", "days": 127, "d": "Dest"},
                ]
            },
        }
    }
    day = datetime(2026, 10, 13, 7, 0, tzinfo=NY).date()
    skeleton = T.timetable_day(schedule, "Origin", "Dest", day, 3)
    by_train = {row["train"]: row for row in skeleton}
    assert by_train["10"]["direct"] is True
    assert by_train["10"]["source"] == "timetable"
    assert by_train["11"]["direct"] is False
    assert by_train["11"]["connection"]["train"] == "21"
    assert by_train["11"]["connection"]["wait_min"] == 4
    live, _error = T.parse_next_to_arrive(
        [
            {
                "orig_train": "10",
                "orig_line": "Lansdale/Doylestown",
                "orig_departure_time": "9:00AM",
                "orig_arrival_time": "9:45AM",
                "orig_delay": "5 mins",
                "isdirect": "true",
            },
            {
                "orig_train": "77",
                "orig_line": "Airport",
                "orig_departure_time": "10:00AM",
                "orig_arrival_time": "10:30AM",
                "orig_delay": "On time",
                "isdirect": "true",
            },
        ],
        datetime(2026, 10, 13, 7, 0, tzinfo=NY),
        10,
    )
    merged = T.merge_day(skeleton, live, datetime(2026, 10, 13, 7, 0, tzinfo=NY))
    found = {row["train"]: row for row in merged}
    assert found["10"]["delay_min"] == 5
    assert found["10"]["source"] == "live"
    assert found["10"]["depart_sched"].startswith("2026-10-13T09:00:00")
    assert "77" in found and found["77"]["source"] == "live"
    assert [row["train"] for row in merged] == sorted(found, key=lambda number: found[number]["depart_sched"])


def test_track_blank_is_null_and_delay_does_not_repeat():
    places = T.places_from_arrivals(
        [
            {"train_id": "10", "track": "", "platform": "", "track_change": None, "platform_change": None},
            {"train_id": "11", "track": "2", "platform": "A", "track_change": "2", "platform_change": None},
        ]
    )
    assert places["10"]["track"] is None
    assert places["10"]["platform"] is None
    assert places["10"]["track_changed"] is False
    assert places["11"]["track"] == "2"
    assert places["11"]["platform"] == "A"
    assert places["11"]["track_changed"] is True
    first = T.track_deltas({}, places, "Origin")
    assert any(item["train"] == "11" for item in first)
    second = T.track_deltas(places, places, "Origin")
    assert second == []
    assert T.delay_deltas({"10": 5}, {"10": 5}) == []
    assert T.delay_deltas({"10": 5}, {"10": 8}) == [{"train": "10", "old_delay": 5, "new_delay": 8}]


def test_service_hint_beats_the_entity():
    assert T.resolve_hint({"train": "6541"}, "999")["train"] == "6541"
    assert T.resolve_hint({"train": ""}, '{"train":"999"}') is None
    assert T.resolve_hint(None, '{"train":"449","connection_train":"12"}')["connection_train"] == "12"
    assert T.resolve_hint(None, "321")["train"] == "321"
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
