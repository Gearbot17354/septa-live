"""Timetable index, transfer rules, and attribute size. Synthetic data plus the bundled feed."""

from __future__ import annotations

import importlib.util
import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gtfs_min"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


D = _load("septa_perf_dynamic", "dynamic.py")
R = _load("septa_perf_ride", "ride.py")
NY = D.NY


def _fixture_schedule():
    files = {path.stem: path.read_text(encoding="utf-8") for path in FIXTURE.glob("*.txt")}
    return D.gtfs_tables_to_schedule(files)


def _core(row):
    link = row.get("connection") if isinstance(row.get("connection"), dict) else None
    return (
        row.get("train"),
        row.get("depart_sched"),
        row.get("arrive_sched"),
        bool(row.get("direct")),
        None if not link else link.get("train"),
        None if not link else link.get("station"),
    )


def test_index_matches_the_old_scan_on_the_fixture():
    schedule = _fixture_schedule()
    day = datetime(2026, 10, 16).date()
    new = D.build_itineraries(
        schedule, "Stop A", "Stop F", day, transfer_min=3, window="today", enforce_transfer=False, through=False
    )
    old = D.build_itineraries_scan(schedule, "Stop A", "Stop F", day, transfer_min=3, window="today")
    assert [_core(row) for row in new] == [_core(row) for row in old]


def test_bundled_search_is_fast_and_cached():
    path = ROOT / "rail-schedule.json"
    if not path.is_file():
        return
    schedule = json.loads(path.read_text())
    names = list(schedule["stations"])
    day = datetime(2026, 10, 15).date()
    started = time.perf_counter()
    D.build_itineraries(schedule, names[0], names[min(20, len(names) - 1)], day, window="today", limit=6)
    first = (time.perf_counter() - started) * 1000
    assert first < 800
    origin = "Suburban Station" if "Suburban Station" in schedule["stations"] else names[0]
    dest = "Lansdale" if "Lansdale" in schedule["stations"] else names[-1]
    started = time.perf_counter()
    rows = D.build_itineraries(schedule, origin, dest, day, window="today", limit=6)
    searched = (time.perf_counter() - started) * 1000
    assert searched < 50
    assert rows
    started = time.perf_counter()
    D.build_itineraries(schedule, origin, dest, day, window="today", limit=6)
    assert (time.perf_counter() - started) * 1000 < 5
    rng = random.Random(1139)
    pairs = []
    for _ in range(20):
        a, b = rng.sample(names, 2)
        pairs.append((a, b))
    for origin_name, dest_name in pairs:
        fresh = D.build_itineraries(
            schedule,
            origin_name,
            dest_name,
            day,
            transfer_min=0,
            window="today",
            enforce_transfer=False,
            through=False,
            limit=8,
        )
        old = D.build_itineraries_scan(schedule, origin_name, dest_name, day, transfer_min=0, window="today")
        assert [_core(row) for row in fresh] == [_core(row) for row in old[:8]]
    late = datetime(2026, 10, 15, 23, 59, tzinfo=NY)
    started = time.perf_counter()
    rolled = D.plan_trips(schedule, origin, dest, after=late, count=2)
    assert (time.perf_counter() - started) * 1000 < 100
    assert rolled["day"] >= "2026-10-15"


def test_transfer_min_prefers_a_legal_connection():
    day = datetime(2026, 10, 16).date()
    schedule = {
        "feed": "xfer",
        "stations": {
            "Stop A": {"S": [{"t": "07:00", "n": "101", "line": "L1", "days": 127, "d": "Stop C"}]},
            "Stop C": {
                "S": [
                    {"t": "07:20", "n": "101", "line": "L1", "days": 127, "d": "Stop C"},
                    {"t": "07:20", "n": "201", "line": "L2", "days": 127, "d": "Stop F"},
                    {"t": "07:26", "n": "202", "line": "L2", "days": 127, "d": "Stop F"},
                ]
            },
            "Stop F": {
                "S": [
                    {"t": "07:40", "n": "201", "line": "L2", "days": 127, "d": "Stop F"},
                    {"t": "07:50", "n": "202", "line": "L2", "days": 127, "d": "Stop F"},
                ]
            },
        },
    }
    rows = D.build_itineraries(schedule, "Stop A", "Stop F", day, transfer_min=3, window="today")
    assert rows and rows[0]["connection"]["train"] == "202"
    assert rows[0]["connection"]["wait_min"] == 6
    assert rows[0]["connection"]["at_risk"] is False


def test_through_running_is_one_direct_row():
    day = datetime(2026, 10, 16).date()
    schedule = {
        "feed": "through",
        "stations": {
            "Stop A": {"S": [{"t": "08:00", "n": "AIR4584", "line": "AIR", "days": 127, "d": "Stop F"}]},
            "Stop C": {
                "S": [
                    {"t": "08:20", "n": "AIR4584", "line": "AIR", "days": 127, "d": "Stop F"},
                    {"t": "08:22", "n": "LAN4584", "line": "LAN", "days": 127, "d": "Stop F"},
                ]
            },
            "Stop F": {"S": [{"t": "08:40", "n": "LAN4584", "line": "LAN", "days": 127, "d": "Stop F"}]},
        },
    }
    rows = D.build_itineraries(schedule, "Stop A", "Stop F", day, window="today")
    assert len(rows) == 1
    assert rows[0]["direct"] is True
    assert rows[0]["through"] is True
    assert rows[0]["connection"] is None
    assert rows[0]["train_number"] == "4584"
    assert "08:40" in rows[0]["arrive_sched"]


def test_express_skips_stations_the_other_trips_serve():
    day = datetime(2026, 10, 16).date()
    schedule = {
        "feed": "express",
        "stations": {
            "Stop A": {
                "S": [
                    {"t": "09:00", "n": "301", "line": "L1", "days": 127, "d": "Stop F"},
                    {"t": "09:30", "n": "302", "line": "L1", "days": 127, "d": "Stop F"},
                ]
            },
            "Stop B": {"S": [{"t": "09:10", "n": "301", "line": "L1", "days": 127, "d": "Stop F"}]},
            "Stop C": {"S": [{"t": "09:15", "n": "301", "line": "L1", "days": 127, "d": "Stop F"}]},
            "Stop F": {
                "S": [
                    {"t": "09:25", "n": "301", "line": "L1", "days": 127, "d": "Stop F"},
                    {"t": "09:40", "n": "302", "line": "L1", "days": 127, "d": "Stop F"},
                ]
            },
        },
    }
    rows = D.build_itineraries(schedule, "Stop A", "Stop F", day, window="today")
    by_train = {row["train"]: row for row in rows}
    assert by_train["302"]["service_type"] == "Express"
    assert by_train["302"]["skipped"] == ["Stop B", "Stop C"]
    assert by_train["301"]["service_type"] == "Local"
    assert by_train["301"]["stops_count"] == 4


def test_expected_train_prefix_and_midnight():
    matcher = R.RideMatcher()
    matcher.set_expected({"train": "LAN5305", "connection_train": "AIR22"})
    assert matcher.active_expected() == "5305"
    assert matcher.expected["connection_train"] == "22"
    matcher.set_expected({"train": "5305"})
    assert matcher.active_expected() == "5305"
    day = datetime(2026, 10, 16).date()
    schedule = {
        "feed": "late",
        "stations": {
            "Stop A": {"S": [{"t": "23:50", "n": "401", "line": "L1", "days": 127, "d": "Stop F"}]},
            "Stop F": {"S": [{"t": "24:27", "n": "401", "line": "L1", "days": 127, "d": "Stop F"}]},
        },
    }
    rows = D.build_itineraries(schedule, "Stop A", "Stop F", day, window="today")
    arrive = datetime.fromisoformat(rows[0]["arrive_sched"])
    assert arrive.date() == day + timedelta(days=1)
    assert arrive.hour == 0 and arrive.minute == 27
    published = D.present_row(rows[0])
    assert published["transfer"] is None
    assert published["connection"] is None
    trimmed = D.trim_published([{"train": str(i), "stops": [{"station": "Stop A"}]} for i in range(30)], keep_stops=4)
    assert trimmed[3]["stops"] and not trimmed[4]["stops"]
    payload = {"trains": trimmed[:20], "suggested": None, "event": None}
    assert len(json.dumps(payload)) < 8192
