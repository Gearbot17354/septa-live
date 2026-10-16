"""Through-running trains are one trip, including the stops before the junction."""

from __future__ import annotations

import importlib.util
import io
import logging
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


D = _load("septa_through_dynamic", "dynamic.py")
S = _load("septa_through_schedule", "schedule.py")
R = _load("septa_through_ride", "ride.py")
H = _load("septa_through_shapes", "shapes.py")

STOPS = "stop_id,stop_name,stop_lat,stop_lon\na,Stop A,40.00,-75.30\nb,Stop B,40.05,-75.20\nh,Hub,39.95,-75.16\nc,Stop C,39.94,-75.20\nd,Stop D,39.90,-75.40\nu,Up,40.10,-75.10\n"
TRIPS = (
    "route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id\n"
    "LAN,wk,t1,Hub,LAN5311,0,5311,sh1\n"
    "MED,wk,t2,Stop D,MED5311,0,5311,sh2\n"
    "LAN,wk,t3,Up,LAN100,0,100,sh3\n"
)
TIMES = (
    "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
    "t1,07:41:00,07:41:00,a,1\n"
    "t1,08:00:00,08:00:00,b,2\n"
    "t1,08:20:00,08:20:00,h,3\n"
    "t2,08:25:00,08:25:00,h,4\n"
    "t2,08:40:00,08:40:00,c,5\n"
    "t2,09:00:00,09:00:00,d,6\n"
    "t3,07:10:00,07:10:00,a,1\n"
    "t3,07:30:00,07:30:00,u,2\n"
)
CAL = "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nwk,1,1,1,1,1,1,1,20260101,20261231\n"
SHAPES = (
    "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
    "sh1,40.00,-75.30,1\n"
    "sh1,40.05,-75.20,2\n"
    "sh1,39.95,-75.16,3\n"
    "sh2,39.95,-75.16,1\n"
    "sh2,39.94,-75.20,2\n"
    "sh2,39.90,-75.40,3\n"
    "sh3,40.00,-75.30,1\n"
    "sh3,40.10,-75.10,2\n"
)
FILES = {
    "stops.txt": STOPS,
    "trips.txt": TRIPS,
    "stop_times.txt": TIMES,
    "calendar.txt": CAL,
    "shapes.txt": SHAPES,
}
DAY = datetime(2026, 10, 16).date()


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buf.getvalue()


def _numbers(schedule):
    found = set()
    for pack in schedule["stations"].values():
        for row in (pack.get("S") or []) + (pack.get("N") or []):
            found.add(row["n"])
    return found


def test_gtfs_join_is_one_train_without_a_duplicate_junction():
    schedule = S.build_schedule(_zip(FILES))
    assert "5311" in _numbers(schedule)
    assert "LAN5311" not in _numbers(schedule)
    assert "MED5311" not in _numbers(schedule)
    assert "LAN100" in _numbers(schedule) or "100" in _numbers(schedule)
    rows = R.remaining_from_timetable(schedule, "5311", DAY.weekday())
    assert [row["station"] for row in rows] == ["Stop A", "Stop B", "Hub", "Stop C", "Stop D"]
    assert schedule["trains"]["5311"]["segments"][0]["route_id"] == "LAN"
    assert schedule["trains"]["5311"]["segments"][1]["route_id"] == "MED"
    assert schedule["trains"]["5311"]["destination"] == "Stop D"
    other = R.remaining_from_timetable(schedule, "100", DAY.weekday())
    if not other:
        other = R.remaining_from_timetable(schedule, "LAN100", DAY.weekday())
    assert [row["station"] for row in other] == ["Stop A", "Up"]


def test_tables_match_the_zip_builder():
    schedule = D.gtfs_tables_to_schedule({name[:-4]: text for name, text in FILES.items()})
    rows = R.remaining_from_timetable(schedule, "5311", DAY.weekday())
    assert [row["station"] for row in rows] == ["Stop A", "Stop B", "Hub", "Stop C", "Stop D"]


def test_remaining_stops_cover_both_segments_and_are_not_a_transfer():
    schedule = S.build_schedule(_zip(FILES))
    pending = R.remaining_from_timetable(schedule, "5311", DAY.weekday(), None, "Stop B", "Hub")
    assert pending[0]["station"] == "Hub"
    assert [row["station"] for row in pending] == ["Hub", "Stop C", "Stop D"]
    line, where = R.through_change(
        R.remaining_from_timetable(schedule, "5311", DAY.weekday()),
        "Stop B",
        "Hub",
    )
    assert line == "MED"
    assert where == "Hub"
    assert R.approaching_connection(pending, None) is False


def test_route_shape_joins_both_segments():
    cache = H.build_shape_cache(_zip(FILES))
    info = cache["trains"]["5311"]
    points = cache["shapes"][info["shape_id"]]
    assert [point[0] for point in points] == [40.00, 40.05, 39.95, 39.94, 39.90]
    assert [stop["name"] for stop in info["stops"]] == ["Stop A", "Stop B", "Hub", "Stop C", "Stop D"]
    marked = H.mark_stops(info["stops"], "Hub", "Stop D", "Stop A")
    assert [row["name"] for row in marked if row["passed"]] == ["Stop A", "Stop B"]
    assert marked[-1]["alight"] is True


def test_planner_counts_the_merged_train_as_direct():
    schedule = S.build_schedule(_zip(FILES))
    rows = D.build_itineraries(schedule, "Stop A", "Stop D", DAY, window="today")
    assert len(rows) == 1
    assert rows[0]["direct"] is True
    assert rows[0]["through"] is True
    assert rows[0]["connection"] is None
    assert rows[0]["train_number"] == "5311"
    assert rows[0]["stops_count"] == 5
    assert "09:00" in rows[0]["arrive_sched"]


def test_a_split_schedule_still_joins_when_the_times_chain():
    schedule = {
        "feed": "split",
        "stations": {
            "Stop A": {"S": [{"t": "07:41", "n": "LAN5311", "line": "LAN", "days": 127, "d": "Hub"}]},
            "Stop B": {"S": [{"t": "08:00", "n": "LAN5311", "line": "LAN", "days": 127, "d": "Hub"}]},
            "Hub": {
                "S": [
                    {"t": "08:20", "n": "LAN5311", "line": "LAN", "days": 127, "d": "Hub"},
                    {"t": "08:25", "n": "MED5311", "line": "MED", "days": 127, "d": "Stop D"},
                ]
            },
            "Stop C": {"S": [{"t": "08:40", "n": "MED5311", "line": "MED", "days": 127, "d": "Stop D"}]},
            "Stop D": {"S": [{"t": "09:00", "n": "MED5311", "line": "MED", "days": 127, "d": "Stop D"}]},
        },
    }
    rows = R.remaining_from_timetable(schedule, "5311", DAY.weekday(), None, "Stop A", "Stop B")
    assert [row["station"] for row in rows] == ["Stop B", "Hub", "Stop C", "Stop D"]


def test_missing_next_stop_is_logged_once():
    schedule = S.build_schedule(_zip(FILES))
    R._MISSED_NEXT.clear()
    logs = []

    class Grab(logging.Handler):
        def emit(self, record):
            logs.append(record.getMessage())

    handler = Grab()
    logging.getLogger("septa_through_ride").addHandler(handler)
    try:
        R.remaining_from_timetable(schedule, "5311", DAY.weekday(), None, "Stop A", "Not A Stop")
        R.remaining_from_timetable(schedule, "5311", DAY.weekday(), None, "Stop A", "Not A Stop")
    finally:
        logging.getLogger("septa_through_ride").removeHandler(handler)
    assert len(logs) == 1
    assert "Not A Stop" in logs[0]


def test_a_prefixed_shape_cache_still_draws_the_whole_ride():
    cache = {
        "shapes": {
            "sh1": [[40.0, -75.3], [40.05, -75.2], [39.95, -75.16]],
            "sh2": [[39.95, -75.16], [39.94, -75.2], [39.9, -75.4]],
        },
        "routes": {
            "LAN": {"color": "#4E87A0", "name": "Lansdale/Doylestown"},
            "MED": {"color": "#6D2077", "name": "Media/Wawa"},
        },
        "trains": {
            "LAN5311": {
                "shape_id": "sh1",
                "route_id": "LAN",
                "stops": [
                    {"name": "Stop A", "lat": 40.0, "lon": -75.3, "sched": "07:41", "route_id": "LAN"},
                    {"name": "Stop B", "lat": 40.05, "lon": -75.2, "sched": "08:00", "route_id": "LAN"},
                    {"name": "Hub", "lat": 39.95, "lon": -75.16, "sched": "08:20", "route_id": "LAN"},
                ],
            },
            "MED5311": {
                "shape_id": "sh2",
                "route_id": "MED",
                "stops": [
                    {"name": "Hub", "lat": 39.95, "lon": -75.16, "sched": "08:25", "route_id": "MED"},
                    {"name": "Stop C", "lat": 39.94, "lon": -75.2, "sched": "08:40", "route_id": "MED"},
                    {"name": "Penn Medicine Station", "lat": 39.9, "lon": -75.4, "sched": "09:00", "route_id": "MED"},
                ],
            },
        },
    }
    ride = {
        "riding": True,
        "train": "5311",
        "next_stop": "Stop B",
        "current_stop": "Stop A",
        "alight_station": "Penn Medicine",
        "origin": "Stop A",
        "remaining_stops": [{"station": "Stop B", "sched": "08:00", "est": "08:04"}],
    }
    H._MISSED_SHAPE.clear()
    route = H.attach_route(ride, cache, {})
    assert route["route_shape_source"] == "gtfs"
    assert route["route_color"] == "#4E87A0"
    assert route["route_shape"][0] == [40.0, -75.3]
    assert route["route_shape"][-1] == [39.9, -75.4]
    assert [row["name"] for row in route["stops"]] == ["Stop A", "Stop B", "Hub", "Stop C", "Penn Medicine Station"]
    assert [row["name"] for row in route["stops"] if row["passed"]] == ["Stop A"]
    assert route["stops"][1]["est"] == "08:04"
    assert route["stops"][-1]["alight"] is True
    later = H.attach_route({**ride, "next_stop": "Stop C"}, cache, {})
    assert [row["name"] for row in later["stops"] if row["passed"]] == ["Stop A", "Stop B", "Hub"]
    assert later["route_color"] == "#6D2077"
    assert H.line_title("MED", cache["routes"], {"MED": "Media/Wawa"}) == "Media/Wawa"


def test_missing_shape_falls_back_to_the_stops():
    cache = {
        "shapes": {},
        "routes": {"LAN": {"color": "#111111", "name": "Lansdale/Doylestown"}},
        "trains": {
            "LAN5311": {
                "shape_id": "missing",
                "route_id": "LAN",
                "stops": [
                    {"name": "Stop A", "lat": 40.0, "lon": -75.3, "route_id": "LAN"},
                    {"name": "Stop B", "lat": 40.05, "lon": -75.2, "route_id": "LAN"},
                ],
            }
        },
    }
    H._MISSED_SHAPE.clear()
    logs = []

    class Grab(logging.Handler):
        def emit(self, record):
            logs.append(record.getMessage())

    handler = Grab()
    logging.getLogger("septa_through_shapes").addHandler(handler)
    try:
        ride = {"riding": True, "train": "5311", "next_stop": "Stop B", "origin": "Stop A"}
        route = H.attach_route(ride, cache, {})
        H.attach_route(ride, cache, {})
    finally:
        logging.getLogger("septa_through_shapes").removeHandler(handler)
    assert route["route_shape_source"] == "stops"
    assert route["route_shape"] == [[40.0, -75.3], [40.05, -75.2]]
    assert route["route_color"] == "#111111"
    assert len(logs) == 1


def test_loose_destination_is_the_canonical_alight_stop():
    order = ["Stop A", "Hub", "Penn Medicine Station"]
    name, source = R.choose_alight(None, 1, None, order, "Stop A", "Penn Medicine", "service")
    assert name == "Penn Medicine Station"
    assert source == "service"
    selected, source = R.choose_alight(None, 1, "Hub", order, "Stop A", "nowhere", "select")
    assert selected == "Hub" and source == "home"

