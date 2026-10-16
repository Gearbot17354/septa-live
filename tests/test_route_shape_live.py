"""Route line and alight on an existing install. No network and no Home Assistant."""

from __future__ import annotations

import importlib.util
import io
import sys
import zipfile
from datetime import date
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 16)


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S = _load("septa_live_shapes", "shapes.py")
R = _load("septa_live_ride_alight", "ride.py")
C = _load("septa_live_sched_shapes", "schedule.py")


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def _feed() -> dict[str, str]:
    stops = "\n".join(
        [
            "stop_id,stop_name,stop_lat,stop_lon",
            "wawa,Wawa,39.90,-75.40",
            "fern,Fern Rock Transit Center,40.04,-75.13",
            "hub,Center City,39.95,-75.16",
            "home,Home Town,40.20,-75.28",
            "end,Doylestown,40.31,-75.13",
        ]
    )
    routes = "\n".join(
        [
            "route_id,route_short_name,route_long_name,route_color,route_text_color",
            "AAA,AAA,Alpha Line,4F758B,FFFFFF",
            "BBB,BBB,Beta/Gamma Line,6D2077,FFFFFF",
        ]
    )
    trips = "\n".join(
        [
            "route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id",
            "AAA,WEEK,aaa,Center City,AAA3544,0,3544,shA",
            "BBB,WEEK,bbb,Doylestown,BBB3544,0,3544,shB",
            "AAA,WEEKEND,aaa2,Center City,AAA3544,0,3544,shA",
            "BBB,WEEKEND,bbb2,Doylestown,BBB3544,0,3544,shB",
        ]
    )
    times = "\n".join(
        [
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence",
            "aaa,08:00:00,08:00:00,wawa,1",
            "aaa,08:20:00,08:20:00,fern,2",
            "aaa,08:40:00,08:40:00,hub,3",
            "bbb,08:45:00,08:45:00,hub,1",
            "bbb,09:10:00,09:10:00,home,2",
            "bbb,09:40:00,09:40:00,end,3",
            "aaa2,18:00:00,18:00:00,wawa,1",
            "aaa2,18:20:00,18:20:00,fern,2",
            "aaa2,18:40:00,18:40:00,hub,3",
            "bbb2,18:45:00,18:45:00,hub,1",
            "bbb2,19:10:00,19:10:00,home,2",
            "bbb2,19:40:00,19:40:00,end,3",
        ]
    )
    calendar = "\n".join(
        [
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date",
            "WEEK,1,1,1,1,1,0,0,20260101,20261231",
            "WEEKEND,0,0,0,0,0,1,1,20260101,20261231",
        ]
    )
    shapes = "\n".join(
        [
            "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence",
            "shA,39.90,-75.40,1",
            "shA,40.04,-75.13,2",
            "shA,39.95,-75.16,3",
            "shB,39.95,-75.16,1",
            "shB,40.20,-75.28,2",
            "shB,40.31,-75.13,3",
        ]
    )
    return {
        "stops.txt": stops + "\n",
        "routes.txt": routes + "\n",
        "trips.txt": trips + "\n",
        "stop_times.txt": times + "\n",
        "calendar.txt": calendar + "\n",
        "shapes.txt": shapes + "\n",
    }


def test_joined_shape_uses_the_live_next_stop():
    cache = S.build_shape_cache(_zip(_feed()), DAY)
    route = S.attach_route(
        {
            "riding": True,
            "train": "3544",
            "next_stop": "Fern Rock T C",
            "remaining_stops": [{"station": "Fern Rock Transit Center", "sched": "08:20", "est": "08:24"}],
        },
        cache,
        {},
    )
    assert route["route_shape"]
    assert len(route["route_shape"]) <= 200
    assert all(len(point) == 2 and point[0] == round(point[0], 5) for point in route["route_shape"])
    assert route["route_shape_source"] == "gtfs"
    assert route["route_color"] == "#4F758B"
    names = [row["name"] for row in route["stops"]]
    assert names[:3] == ["Wawa", "Fern Rock Transit Center", "Center City"]
    assert "Home Town" in names and names[-1] == "Doylestown"
    fern = next(row for row in route["stops"] if "Fern" in row["name"])
    assert fern["passed"] is False
    assert route["stops"][0]["passed"] is True
    assert fern["est"] == "08:24"
    assert all(row["lat"] is not None and row["lon"] is not None for row in route["stops"])


def test_empty_cache_draws_the_stops_it_knows():
    geo = {"by_key": {"home town": ("Home Town", 40.2, -75.28), "center city": ("Center City", 39.95, -75.16)}}
    route = S.attach_route(
        {
            "riding": True,
            "train": "3544",
            "next_stop": "Home Town",
            "remaining_stops": [
                {"station": "Center City", "est": "08:40"},
                {"station": "Home Town", "est": "09:10"},
            ],
        },
        {"shapes": {}, "trains": {}, "routes": {}},
        {},
        geo=geo,
    )
    assert route["route_shape_source"] == "stops"
    assert len(route["route_shape"]) >= 2
    assert route["route_shape_reason"] == "cache_empty"
    assert route["route_shape"] is not None
    empty = S.attach_route(
        {"riding": True, "train": "3544", "remaining_stops": [{"station": "Nowhere"}]},
        {"shapes": {}, "trains": {}, "routes": {}},
        {},
        geo=geo,
    )
    assert empty["route_shape_source"] == "none"
    assert empty["route_shape_reason"]


def test_shapes_are_needed_even_when_the_timetable_is_fresh():
    assert C.shapes_needed({"trains": {}, "format": 2}, S.SHAPES_FORMAT) is True
    assert C.shapes_needed({"trains": {"1": {}}, "format": 1}, 2) is True
    assert C.shapes_needed({"trains": {"1": {}}, "format": 2}, 2) is False
    assert C.shapes_retry_unconditional(304, {"trains": {}}, 2) is True
    assert C.shapes_retry_unconditional(304, {"trains": {"1": {}}, "format": 2}, 2) is False
    assert C.shapes_retry_unconditional(200, {"trains": {}}, 2) is False


def test_an_old_shapes_file_still_loads(tmp_path):
    path = tmp_path / "septa_live_rail_shapes.json"
    path.write_text('{"trains": {"3544": {"shape_id": "sh"}}, "shapes": {}, "routes": {}}', encoding="utf-8")
    loaded = S.read_shapes_file(path)
    assert loaded["trains"]["3544"]["shape_id"] == "sh"
    assert C.shapes_needed(loaded, S.SHAPES_FORMAT) is True


def test_auto_select_falls_through_to_home_on_a_mapping_proxy():
    options = MappingProxyType(
        {
            "riders_cfg": {"ryan": {"home_station": "Home Town", "destination_entity": "input_select.dest"}},
            "home_station": "",
        }
    )
    data = MappingProxyType({"station": "Other"})
    home = R.rider_home(options, data, "ryan")
    order = ["Wawa", "Fern Rock Transit Center", "Center City", "Home Town", "Doylestown"]
    name, source, checked = R.alight_plan(order, "Fern Rock T C", home=home, select="Auto")
    assert home == "Home Town"
    assert name == "Home Town" and source == "home"
    assert checked[0]["source"] == "select" and checked[0]["result"] == "auto"
    rows = [
        {"station": "Center City", "est": "08:40", "est_source": "delay"},
        {"station": "Home Town", "est": "09:10", "est_source": "delay"},
        {"station": "Doylestown", "est": "09:40", "est_source": "delay"},
    ]
    kept = []
    for row in rows:
        kept.append(row)
        if R._loose_name(row["station"]) == R._loose_name(name):
            break
    assert [row["station"] for row in kept] == ["Center City", "Home Town"]
    assert kept[-1]["est"] == "09:10"


def test_home_behind_the_train_is_not_the_alight_stop():
    order = ["Wawa", "Home Town", "Fern Rock Transit Center", "Doylestown"]
    name, source, checked = R.alight_plan(order, "Fern Rock Transit Center", home="Home Town")
    assert name is None and source == "none"
    assert checked[-1]["result"] == "behind"


def test_home_resolves_when_the_slug_is_the_person_not_the_tracker():
    options = {"riders_cfg": {"phone": {"home_station": "Home Town"}}}
    assert R.rider_home(options, {}, "ryan", person="person.ryan", tracker="device_tracker.phone") == "Home Town"


def test_remaining_rows_keep_estimates_and_gain_coordinates():
    rows = R.annotate_coords(
        [{"station": "Home Town", "est": "09:10", "est_source": "delay", "sched": "09:05", "line": "BBB"}],
        [{"name": "Home Town", "lat": 40.2, "lon": -75.28}],
        {},
    )
    assert rows[0]["lat"] == 40.2 and rows[0]["lon"] == -75.28
    assert rows[0]["est_source"] == "delay"
    geo = {"by_key": {"center": ("Center City", 39.95, -75.16)}}
    other = R.annotate_coords([{"station": "Center City", "est_source": "sched"}], [], geo)
    assert other[0]["lat"] == 39.95
    assert other[0]["est_source"] == "sched"


def test_the_active_service_day_supplies_the_clocks():
    cache = S.build_shape_cache(_zip(_feed()), DAY)
    info = cache["trains"]["3544"]
    clocks = [stop["sched"] for stop in info["stops"]]
    assert clocks[0] == "08:00"
    assert "18:00" not in clocks
    assert info["service"] == "WEEK"


def test_entry_options_are_not_checked_with_isinstance_dict():
    for path in ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "isinstance(self.entry.options, dict)" not in text
        assert "isinstance(self.entry.data, dict)" not in text
        assert "isinstance(entry.options, dict)" not in text
        assert "isinstance(entry.data, dict)" not in text
