"""Dynamic trips. No Home Assistant."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


D = _load("septa_dynamic", "dynamic.py")
T = _load("septa_trips_cap", "trips.py")

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=NY)
DAY = NOW.date()


def _schedule():
    days = 127
    return {
        "validUntil": "20261201",
        "stations": {
            "North End": {
                "S": [
                    {"t": "09:00", "d": "South End", "n": "100", "line": "NORTH", "days": days},
                    {"t": "11:00", "d": "South End", "n": "101", "line": "NORTH", "days": days},
                ]
            },
            "Hub": {
                "S": [
                    {"t": "09:20", "d": "South End", "n": "100", "line": "NORTH", "days": days},
                    {"t": "11:20", "d": "South End", "n": "101", "line": "NORTH", "days": days},
                ],
                "N": [
                    {"t": "09:30", "d": "South Spur", "n": "300", "line": "SOUTH", "days": days},
                ],
            },
            "South End": {
                "S": [
                    {"t": "09:30", "d": "South End", "n": "100", "line": "NORTH", "days": days},
                    {"t": "11:40", "d": "South End", "n": "101", "line": "NORTH", "days": days},
                ]
            },
            "South Spur": {
                "N": [
                    {"t": "09:50", "d": "South Spur", "n": "300", "line": "SOUTH", "days": days},
                ]
            },
        },
    }


def _stops():
    return [
        {"name": "North End", "lat": 40.0, "lon": -75.0},
        {"name": "Hub", "lat": 40.01, "lon": -75.0},
        {"name": "South End", "lat": 39.95, "lon": -75.0},
    ]


def test_nearest_radius_hysteresis_home_and_accuracy():
    stops = _stops()
    near = D.nearest_station(40.002, -75.0, stops, 1500)
    assert near["name"] == "North End"
    assert near["distance_m"] < 1500
    outside = D.nearest_station(41.5, -75.0, stops, 1500)
    assert outside is None
    stay = D.nearest_station(40.0052, -75.0, stops, 5000, current="North End")
    assert stay["name"] == "North End"
    switched = D.nearest_station(40.0065, -75.0, stops, 5000, current="North End")
    assert switched["name"] == "Hub"
    home = D.resolve_origin(
        at_home=True,
        lat=40.002,
        lon=-75.0,
        accuracy=10,
        stops=stops,
        city_station="Hub",
        home_station="North End",
    )
    assert home["reason"] == "at_home_station"
    assert home["origin_source"] == "home"
    fuzzy = D.resolve_origin(
        lat=40.002,
        lon=-75.0,
        accuracy=800,
        max_accuracy=100,
        stops=stops,
        city_station="Hub",
        home_station="North End",
    )
    assert fuzzy["origin_source"] == "default"
    assert fuzzy["origin"] == "Hub"
    assert fuzzy["origin_skip_reason"] == "inaccurate"


def test_destination_priority_and_unknown_location():
    names = ["North End", "Hub", "South End", "30th Street Station"]
    stops = _stops() + [{"name": "30th Street Station", "lat": 39.95, "lon": -75.18}]
    event = {"summary": "Desk", "start": "2026-10-12T10:00:00-04:00", "location": "30th street"}
    manual = D.resolve_destination(
        manual="Hub", entity_state="South End", event=event, default_station="North End", names=names, stops=stops
    )
    assert manual["destination"] == "Hub" and manual["destination_source"] == "manual"
    entity = D.resolve_destination(
        entity_state="South End", event=event, default_station="North End", names=names, stops=stops
    )
    assert entity["destination_source"] == "entity"
    calendar = D.resolve_destination(event=event, default_station="North End", names=names, stops=stops)
    assert calendar["destination"] == "30th Street Station"
    assert calendar["destination_source"] == "calendar"
    coords = D.resolve_destination(
        event={
            "summary": "Site",
            "start": "2026-10-12T10:00:00-04:00",
            "location": "somewhere new",
            "latitude": 40.009,
            "longitude": -75.0,
        },
        default_station="North End",
        names=names,
        stops=stops,
        near_radius_m=1500,
    )
    assert coords["destination"] == "Hub"
    unknown = D.resolve_destination(
        event={"summary": "Site", "start": "2026-10-12T10:00:00-04:00", "location": "not a station"},
        default_station="North End",
        names=names,
        stops=stops,
    )
    assert unknown["destination"] == "North End"
    assert unknown["destination_source"] == "default"


def test_transfer_direct_preferred_and_suggested():
    schedule = _schedule()
    direct = D.build_itineraries(schedule, "North End", "South End", DAY, transfer_min=3, now=NOW)
    assert direct
    assert direct[0]["direct"] is True
    assert direct[0]["connection"] is None
    assert direct[0]["train"] == "100"
    hopped = D.build_itineraries(schedule, "North End", "South Spur", DAY, transfer_min=20, now=NOW)
    assert len(hopped) == 1
    assert hopped[0]["direct"] is False
    link = hopped[0]["connection"]
    assert link["station"] == "Hub"
    assert link["train"] == "300"
    assert link["wait_min"] == 10
    assert link["at_risk"] is True
    rows = [D.present_row(row, NOW) for row in direct]
    early = D.suggest_itinerary(rows, datetime(2026, 10, 12, 10, 0, tzinfo=NY), 15)
    assert early["train"] == "100"
    later = D.suggest_itinerary(rows, datetime(2026, 10, 12, 12, 0, tzinfo=NY), 15)
    assert later["train"] == "101"
    assert rows[0]["late_min"] == rows[0]["delay_min"]
    assert rows[0]["transfer"] is None
    assert "live" in rows[0]


def test_migration_keeps_trips_and_is_idempotent():
    data = {
        "station": "North End",
        "destination": "Hub",
        "trips": [{"id": "abc", "origin": "South End", "destination": "North End"}],
    }
    options = {
        "destination": "Hub",
        "trips": [{"id": "abc", "origin": "South End", "destination": "North End", "count": 4}],
    }
    first = D.migrate_options(data, options)
    assert first["home_station"] == "North End"
    assert first["default_city_station"] == "Hub"
    assert first["trips"] == options["trips"]
    assert first["trips"][0]["id"] == "abc"
    again = D.migrate_options({"station": "Other"}, first)
    assert again["home_station"] == "North End"
    assert again["trips"][0]["id"] == "abc"
    assert again["default_city_station"] == "Hub"


def test_clean_trips_cap_and_default_count():
    raw = [{"origin": f"A{i}", "destination": f"B{i}"} for i in range(25)]
    cleaned = T.clean_trips(raw)
    assert len(cleaned) == 20
    assert cleaned[0]["count"] == 4
    wide = T.clean_trips([{"origin": "A", "destination": "B", "count": 50}])
    assert wide[0]["count"] == 20


def test_expired_schedule_skips_timetable():
    bundled = {"validUntil": "20200101", "stations": {"North End": {"S": []}}}
    chosen, source = D.select_schedule(bundled, None, date(2026, 10, 13))
    assert source == "expired"
    assert D.timetable_allowed(source) is False
    assert chosen is bundled
    fresh = {"validUntil": "20261201", "stations": {"North End": {"S": []}}, "feed": "gtfs"}
    cached, cached_source = D.select_schedule(bundled, fresh, date(2026, 10, 13))
    assert cached_source == "gtfs"
    assert cached is fresh
    current = {"validUntil": "20261201", "stations": {"Keep": {"S": []}}}
    _kept, bundled_source = D.select_schedule(current, fresh, date(2026, 10, 13))
    assert bundled_source == "bundled"


def test_gtfs_tables_build_a_station_row():
    files = {
        "stops": "stop_id,stop_name\n1,North End\n2,Hub\n",
        "trips": "trip_id,route_id,service_id,trip_headsign,trip_short_name\nt1,NORTH,wk,Hub,100\n",
        "calendar": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday\nwk,1,1,1,1,1,0,0\n",
        "stop_times": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nt1,09:00:00,09:00:00,1,1\nt1,09:20:00,09:20:00,2,2\n",
        "feed_info": "feed_end_date\n20261201\n",
    }
    schedule = D.gtfs_tables_to_schedule(files)
    assert schedule["validUntil"] == "20261201"
    assert schedule["feed"] == "gtfs"
    rows = schedule["stations"]["North End"]["S"]
    assert rows[0]["n"] == "100"
    assert rows[0]["t"] == "09:00"
    assert rows[0]["line"] == "NORTH"


def test_dynamic_entity_ids_stay_stable():
    ids = _load("septa_ids_dyn", "ids.py")
    assert ids.dynamic_key("going_home", "alex", True) == "going_home"
    assert ids.dynamic_key("day_trains", "alex", False) == "day_trains_alex"
    assert ids.canonical_entity_id("sensor", "North End", "going_home") == "sensor.septa_going_home"
    assert ids.canonical_entity_id("sensor", "North End", "day_trains_alex") == "sensor.septa_day_trains_alex"
    assert ids.legacy_key("abc123_going_home") == "going_home"
    assert ids.legacy_key("abc123_going_home_alex") == "going_home_alex"
    assert ids.stable_unique_id("abc123", "going_home") == "abc123_going_home"
    unique, entity = ids.dynamic_ids("abc123", "going_home", "alpha", True)
    assert unique == "abc123_going_home"
    assert entity == "sensor.septa_going_home_alpha"
    unique, entity = ids.dynamic_ids("abc123", "day_trains", "bravo", False)
    assert unique == "abc123_day_trains_bravo"
    assert entity == "sensor.septa_day_trains_bravo"


def _class_body(text: str, name: str) -> str:
    start = text.index(f"class {name}")
    rest = text[start:]
    nxt = rest.find("\nclass ", 1)
    return rest if nxt < 0 else rest[:nxt]


def test_unrecorded_attributes_on_entity_classes():
    const = _load("septa_const_rec", "const.py")
    assert const.UNRECORDED_TRAIN_ATTRS == frozenset(
        {"trains", "trips", "suggested", "candidates", "day", "remaining_stops"}
    )
    sensor = (ROOT / "sensor.py").read_text()
    binary = (ROOT / "binary_sensor.py").read_text()
    for name, src in (
        ("SeptaTripSensor", sensor),
        ("SeptaDynamicSensor", sensor),
        ("SeptaMyTrainSensor", sensor),
        ("SeptaRidingBinarySensor", binary),
    ):
        assert "_unrecorded_attributes = UNRECORDED_TRAIN_ATTRS" in _class_body(src, name)
    for name, src in (("SeptaRiderTrainSensor", sensor), ("SeptaRiderBinarySensor", binary)):
        assert "_unrecorded_attributes" not in _class_body(src, name)


def test_calendar_option_is_global_and_per_rider():
    flow = (ROOT / "config_flow.py").read_text()
    body = _class_body(flow, "SeptaOptionsFlow")
    assert body.count("calendar_entity") >= 2
    assert "CONF_MAX_TRAINS" in body
    ha = (ROOT / "dynamic_ha.py").read_text()
    assert 'pick("calendar_entity", opt.get("calendar_entity")' in ha


def test_campus_address_without_geocoder_transfers_at_30th():
    names = ["North End", "Gray 30th St Station", "Penn Medicine Station"]
    stops = [
        {"name": "North End", "lat": 40.24, "lon": -75.28},
        {"name": "Gray 30th St Station", "lat": 39.95667, "lon": -75.18166},
        {"name": "Penn Medicine Station", "lat": 39.94806, "lon": -75.19028},
    ]
    event = {
        "summary": "Class",
        "start": "2026-10-12T10:30:00-04:00",
        "location": "202 S 36th St, Philadelphia, PA 19104",
    }
    dest = D.resolve_destination(event=event, default_station="North End", names=names, stops=stops)
    assert dest["destination"] == "Penn Medicine Station"
    assert dest["destination_source"] == "calendar"
    street = D.resolve_destination(
        event={
            "summary": "Class",
            "start": "2026-10-12T10:30:00-04:00",
            "location": "202 S 36th St, Philadelphia",
        },
        default_station="North End",
        names=names,
        stops=stops,
        near_radius_m=2000,
    )
    assert street["destination"] == "Penn Medicine Station"
    assert street["destination_source"] == "calendar"
    phrase = D.resolve_destination(
        event={"summary": "Lab", "start": "2026-10-12T10:30:00-04:00", "location": "University City"},
        default_station="North End",
        names=names,
        stops=stops,
    )
    assert phrase["destination"] == "Penn Medicine Station"
    days = 127
    schedule = {
        "stations": {
            "North End": {
                "S": [{"t": "09:00", "d": "Gray 30th St Station", "n": "100", "line": "NORTH", "days": days}]
            },
            "Gray 30th St Station": {
                "S": [
                    {"t": "09:40", "d": "Gray 30th St Station", "n": "100", "line": "NORTH", "days": days},
                    {"t": "09:50", "d": "Penn Medicine Station", "n": "400", "line": "AIR", "days": days},
                ]
            },
            "Penn Medicine Station": {
                "S": [{"t": "10:00", "d": "Penn Medicine Station", "n": "400", "line": "AIR", "days": days}]
            },
        }
    }
    rows = D.build_itineraries(schedule, "North End", dest["destination"], DAY, transfer_min=3, now=NOW)
    assert rows and rows[0]["direct"] is False
    assert rows[0]["connection"]["station"] == "Gray 30th St Station"
    assert rows[0]["connection"]["train"] == "400"
    unknown = D.resolve_destination(
        event={"summary": "X", "start": "2026-10-12T10:00:00-04:00", "location": "1 Main St, Nowhere"},
        default_station="North End",
        names=names,
        stops=stops,
    )
    assert unknown["destination_source"] == "default"


def test_cap_trains_reports_total_and_suggest_uses_the_full_list():
    rows = [{"train": str(index), "arrive_est": f"2026-10-12T{9 + index:02d}:00:00-04:00"} for index in range(5)]
    shown, total = D.cap_trains(rows, 2)
    assert total == 5
    assert [row["train"] for row in shown] == ["0", "1"]
    suggested = D.suggest_itinerary(rows, datetime(2026, 10, 12, 14, 0, tzinfo=NY), 0)
    assert suggested["train"] == "4"


def test_origin_uses_the_person_when_the_tracker_has_no_coordinates():
    stops = _stops() + [{"name": "Far", "lat": 40.02, "lon": -75.0}]
    names = [stop["name"] for stop in stops]
    chosen = D.pick_fix(
        [
            {"entity": "device_tracker.old", "lat": None, "lon": None, "updated": 50, "state": "not_home"},
            {"entity": "person.alpha", "lat": 40.0006, "lon": -75.0, "updated": 10, "state": "not_home"},
        ]
    )
    assert chosen["entity"] == "person.alpha"
    nearest = D.resolve_origin(
        lat=chosen["lat"],
        lon=chosen["lon"],
        accuracy=17,
        stops=stops,
        current="Far",
        city_station="Hub",
        home_station="South End",
        origin_entity=chosen["entity"],
    )
    assert nearest["origin"] == "North End"
    assert nearest["origin_source"] == "nearest"
    assert nearest["origin_distance_m"] < 200
    assert nearest["origin_skip_reason"] is None
    zone = D.resolve_origin(
        zone=D.zone_station("North End", names),
        city_station="Hub",
        home_station="South End",
        stops=stops,
    )
    assert zone["origin"] == "North End"
    assert zone["origin_source"] == "zone"
    assert zone["origin_distance_m"] == 0
    assert D.zone_station("not_home", names) is None
    assert D.zone_station("home", names) is None
    missing = D.resolve_origin(city_station="Hub", home_station="South End", stops=stops)
    assert missing["origin_source"] == "default"
    assert missing["origin_skip_reason"] == "no_coords"
    home = D.resolve_origin(at_home=True, home_station="South End", city_station="Hub", stops=stops)
    assert home["reason"] == "at_home_station"
    before = D.watch_entities(
        [{"slug": "alpha", "tracker": "device_tracker.old", "person": "person.alpha", "configured": "device_tracker.old"}]
    )
    after = D.watch_entities(
        [{"slug": "alpha", "tracker": "device_tracker.new", "person": "person.alpha", "configured": "device_tracker.old"}]
    )
    assert before != after
    assert "device_tracker.new" in after
    assert "person.alpha" in after
    text = (ROOT / "dynamic_ha.py").read_text()
    start = text.index("async def _on_tracker")
    body = text[start : text.index("\n    def ", start + 10)]
    assert "self._listen()" in body


def test_going_home_origin_while_riding_or_stale():
    stops = _stops()
    riding = D.resolve_origin(
        stale=True,
        ride_origin="Hub",
        lat=40.0,
        lon=-75.0,
        accuracy=17,
        city_station="South End",
        home_station="North End",
        stops=stops,
    )
    assert riding["origin_source"] == "ride"
    assert riding["origin"] == "Hub"
    remembered = D.resolve_origin(
        stale=True,
        last="Hub",
        last_recent=True,
        city_station="South End",
        home_station="North End",
        stops=stops,
    )
    assert remembered["origin_source"] == "last"
    assert remembered["origin"] == "Hub"
    fresh = D.resolve_origin(
        lat=40.0006,
        lon=-75.0,
        accuracy=17,
        city_station="Hub",
        home_station="South End",
        stops=stops,
    )
    assert fresh["origin"] == "North End"
    assert fresh["origin_source"] == "nearest"
    home = D.resolve_origin(at_home=True, home_station="South End", city_station="Hub", stops=stops)
    assert home["reason"] == "at_home_station"
    fallback = D.resolve_origin(stale=True, city_station="Hub", home_station="South End", stops=stops)
    assert fallback["origin_source"] == "default"
    assert fallback["origin_skip_reason"]
