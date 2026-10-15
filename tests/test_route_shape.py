"""Route lines for the train a rider is on. Synthetic GTFS only."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gtfs_min"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S = _load("septa_shapes", "shapes.py")
T = _load("septa_tracker_route", "tracker.py")
C = _load("septa_const_route", "const.py")
SCH = _load("septa_schema_route", "schema.py")


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buf.getvalue()


def _files(include_shapes: bool = True) -> dict[str, str]:
    found = {}
    for path in FIXTURE.iterdir():
        if path.suffix != ".txt":
            continue
        if not include_shapes and path.name == "shapes.txt":
            continue
        found[path.name] = path.read_text(encoding="utf-8")
    return found


def _ride(train, next_stop, alight="Stop E", origin="Stop A", riding=True):
    return {
        "riding": riding,
        "train": train,
        "next_stop": next_stop,
        "alight_station": alight,
        "final_destination": alight,
        "origin": origin,
        "rider": "alpha",
    }


def _near(point, stop, limit):
    return S.haversine_m(point[0], point[1], stop["lat"], stop["lon"]) <= limit


def test_douglas_peucker_keeps_stops_and_endpoints():
    cache = S.build_shape_cache(_zip(_files()))
    info = cache["trains"]["91001"]
    full = cache["shapes"][info["shape_id"]]
    assert len(full) == 1000
    clipped = S.orient_and_clip(full, info["stops"])
    result = S.simplify_shape(full, info["stops"], 200)
    assert len(result["points"]) <= 200
    assert result["points"][0] == clipped[0]
    assert result["points"][-1] == clipped[-1]
    assert result["deviation_m"] <= result["epsilon_m"] + 1
    for stop in info["stops"]:
        nearest = min(S.haversine_m(stop["lat"], stop["lon"], point[0], point[1]) for point in result["points"])
        assert nearest <= 50


def test_reverse_trip_starts_at_its_first_stop():
    cache = S.build_shape_cache(_zip(_files()))
    memo = {}
    forward = S.attach_route(_ride("91001", "Stop C"), cache, memo)
    backward = S.attach_route(_ride("91002", "Stop D", origin="Stop F", alight="Stop B"), cache, memo)
    stops = {row["name"]: row for row in cache["trains"]["91001"]["stops"]}
    assert _near(forward["route_shape"][0], stops["Stop A"], 50)
    assert _near(backward["route_shape"][0], stops["Stop F"], 50)
    assert S.haversine_m(backward["route_shape"][0][0], backward["route_shape"][0][1], stops["Stop A"]["lat"], stops["Stop A"]["lon"]) > 1000
    assert forward["route_shape"] != backward["route_shape"]


def test_short_turn_is_clipped_to_its_stops():
    cache = S.build_shape_cache(_zip(_files()))
    short = S.attach_route(_ride("91003", "Stop C", alight="Stop D", origin="Stop B"), cache, {})
    stops = {row["name"]: row for row in cache["trains"]["91003"]["stops"]}
    assert _near(short["route_shape"][0], stops["Stop B"], 50)
    assert _near(short["route_shape"][-1], stops["Stop D"], 50)
    far = cache["trains"]["91001"]["stops"][0]
    assert S.haversine_m(short["route_shape"][0][0], short["route_shape"][0][1], far["lat"], far["lon"]) > 1000


def test_missing_shapes_fall_back_to_stops():
    cache = S.build_shape_cache(_zip(_files(include_shapes=False)))
    route = S.attach_route(_ride("91001", "Stop C"), cache, {})
    assert route["route_color"] == "#00A0DF"
    assert 2 <= len(route["route_shape"]) <= 6
    assert route["route_shape"][0][0] == cache["trains"]["91001"]["stops"][0]["lat"]


def test_active_ride_publishes_the_line_and_clears_it():
    cache = S.build_shape_cache(_zip(_files()))
    memo = {}
    alpha = _ride("91001", "Stop C", alight="Stop E", origin="Stop B")
    line = S.attach_route(alpha, cache, memo)
    assert line["route_color"] == "#00A0DF"
    assert line["route_text_color"] == "#FFFFFF"
    assert line["route_shape_simplified"] is True
    assert line["route_shape_points"] == len(line["route_shape"]) <= 200
    assert line["alight_station"] == "Stop E"
    names = [row["name"] for row in line["stops"]]
    assert names == ["Stop A", "Stop B", "Stop C", "Stop D", "Stop E", "Stop F"]
    flags = {row["name"]: row["passed"] for row in line["stops"]}
    assert flags["Stop A"] is True and flags["Stop B"] is True
    assert flags["Stop C"] is False and flags["Stop C"] == (not line["stops"][2]["remaining"])
    assert line["stops"][0]["before_board"] is True
    assert "before_board" not in line["stops"][1]
    token = next(iter(memo.values()))
    moved = S.attach_route(_ride("91001", "Stop E", alight="Stop E", origin="Stop B"), cache, memo)
    assert next(iter(memo.values())) is token
    assert moved["route_shape"] == line["route_shape"]
    assert [row["name"] for row in moved["stops"] if row["passed"]] == ["Stop A", "Stop B", "Stop C", "Stop D"]
    bravo = S.attach_route(_ride("91002", "Stop D", alight="Stop B", origin="Stop F"), cache, memo)
    bravo["rider"] = "bravo"
    assert bravo["route_shape"][0] != line["route_shape"][0]
    tracker = T.tracker_attributes(
        train="91001",
        line="SYN",
        next_stop="Stop C",
        destination="Stop F",
        delay_min=1,
        consist=["1"],
        last_update=None,
        riders=[{"rider": "alpha", "name": "Alpha", "entity_picture": None}],
        stale=False,
        route=line,
    )
    mine = dict(alpha)
    mine.update(line)
    assert tracker["route_shape"] == mine["route_shape"]
    assert tracker["route_color"] == mine["route_color"] == "#00A0DF"
    ended = S.attach_route({"riding": False, "train": "91001", "alight_station": "Stop E"}, cache, memo)
    assert ended["route_shape"] is None
    assert ended["stops"] is None
    assert ended["route_color"] is None


def test_attribute_payload_stays_under_16kb():
    cache = S.build_shape_cache(_zip(_wide()))
    route = S.attach_route(_ride("91040", "Stop 10", alight="Stop 30", origin="Stop 2"), cache, {})
    assert len(route["stops"]) == 40
    assert len(json.dumps(route)) < 16384
    tight = S.attach_route(_ride("91001", "Stop C", origin="Stop B"), S.build_shape_cache(_zip(_files())), {}, byte_limit=2000)
    assert len(json.dumps(tight)) < 2000


def test_recorder_skips_the_line_and_the_stops():
    assert "route_shape" in C.UNRECORDED_TRAIN_ATTRS
    assert "stops" in C.UNRECORDED_TRAIN_ATTRS
    tracker = (ROOT / "device_tracker.py").read_text()
    sensor = (ROOT / "sensor.py").read_text()
    assert "_unrecorded_attributes = UNRECORDED_TRAIN_ATTRS" in tracker
    assert "route_for" in sensor


def test_websocket_route_by_rider_or_train_number():
    cache = S.build_shape_cache(_zip(_files()))
    rows = [_ride("91001", "Stop C")]
    parsed = vol.Schema(SCH.WEBSOCKET_ROUTE)({"type": "septa_live/route", "train": 91001, "rider": " alpha "})
    assert parsed["train"] == "91001"
    assert parsed["rider"] == "alpha"
    by_train = S.resolve_route([(cache, rows)], train=parsed["train"])
    by_rider = S.resolve_route([(cache, rows)], rider="alpha")
    assert len(by_train["shape"]) == 1000
    assert by_train["route_color"] == "#00A0DF"
    assert by_rider["train"] == "91001"
    assert by_rider["shape"][0] == by_train["shape"][0]
    assert S.resolve_route([(cache, rows)], train=42) == {"error": "not_found"}
    assert S.resolve_route([(cache, [])], rider="bravo") == {"error": "not_found"}
    assert SCH.all_bare_leaves() == []


def test_a_bad_shape_file_keeps_the_old_cache(tmp_path):
    good = _zip(_files())
    cache = S.build_shape_cache(good)
    schedule = S._sched.build_schedule(good) if hasattr(S, "_sched") else None
    if schedule is None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("septa_schedule_kept", ROOT / "schedule.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        schedule = module.build_schedule(good)
    assert "Stop A" in schedule["stations"]
    kept, err = S.absorb_shapes(cache, b"not-a-zip")
    assert kept is cache
    assert err
    broken = _zip(
        {
            "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\n1,Stop A,20,10\n2,Stop B,21,10\n",
            "trips.txt": "trip_id,route_id,service_id,trip_headsign,trip_short_name,direction_id,shape_id\nt,SYN,wk,Stop B,91001,0,sh1\n",
            "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nt,09:00:00,09:00:00,1,1\nt,09:10:00,09:10:00,2,2\n",
            "shapes.txt": "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\nsh1,nope,10,1\n",
        }
    )
    again, reason = S.absorb_shapes(cache, broken)
    assert again is cache
    assert reason
    dest = tmp_path / "septa_live_rail_shapes.json"
    S.write_shapes_file(dest, cache)
    assert dest.is_file()
    assert not (ROOT / "septa_live_rail_shapes.json").exists()
    assert S.read_shapes_file(tmp_path / "missing.json") is None


def _wide() -> dict[str, str]:
    import math

    count = 1000
    stops = 40

    def point(i):
        lat = round(20.0 + (i / (count - 1)), 5)
        lon = round(10.0 + 0.05 * math.sin(i / (count - 1) * math.pi * 8), 5)
        return lat, lon

    indexes = [round(i * (count - 1) / (stops - 1)) for i in range(stops)]
    stops_txt = "stop_id,stop_name,stop_lat,stop_lon\n"
    ids = []
    for seq, index in enumerate(indexes, start=1):
        lat, lon = point(index)
        sid = f"s{seq}"
        ids.append(sid)
        stops_txt += f"{sid},Stop {seq},{lat:.5f},{lon:.5f}\n"
    times = "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
    for seq, sid in enumerate(ids, start=1):
        times += f"t,{8 + seq // 60:02d}:{seq % 60:02d}:00,{8 + seq // 60:02d}:{seq % 60:02d}:00,{sid},{seq}\n"
    shapes = "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
    for i in range(count):
        lat, lon = point(i)
        shapes += f"sh,{lat:.5f},{lon:.5f},{i + 1}\n"
    return {
        "stops.txt": stops_txt,
        "trips.txt": "trip_id,route_id,service_id,trip_headsign,trip_short_name,direction_id,shape_id\nt,SYN,wk,End,91040,0,sh\n",
        "stop_times.txt": times,
        "routes.txt": "route_id,route_color,route_text_color\nSYN,00A0DF,FFFFFF\n",
        "shapes.txt": shapes,
    }
