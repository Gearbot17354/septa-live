"""Arrive-by suggestions and the read-only trip planner. Synthetic GTFS only."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
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


D = _load("septa_plan_dynamic", "dynamic.py")
S = _load("septa_plan_schema", "schema.py")
NY = D.NY
NAMES = ["Stop A", "Stop B", "Stop C", "Stop D", "Stop E", "Stop F", "Stop X"]
FRIDAY = datetime(2026, 10, 16, 9, 0, tzinfo=NY)


def _files() -> dict[str, str]:
    return {path.stem: path.read_text(encoding="utf-8") for path in FIXTURE.glob("*.txt")}


def _schedule():
    return D.gtfs_tables_to_schedule(_files())


def _row(train: str, arrive: str, depart: str = "07:00") -> dict:
    return {
        "train": train,
        "depart_est": f"2026-10-16T{depart}:00-04:00",
        "depart_sched": f"2026-10-16T{depart}:00-04:00",
        "arrive_est": f"2026-10-16T{arrive}:00-04:00",
        "arrive_sched": f"2026-10-16T{arrive}:00-04:00",
        "direct": True,
    }


def test_walk_minutes_round_up():
    assert D.walk_minutes_for(1000) == 17
    assert D.walk_minutes_for(None) == 0


def test_suggestion_includes_the_walk_and_keeps_the_old_deadline():
    rows = [_row("1", "08:00"), _row("2", "08:10"), _row("3", "08:15", "07:30")]
    event = datetime(2026, 10, 16, 8, 30, tzinfo=NY)
    assert D.suggest_itinerary(rows, event, 10, 10)["train"] == "2"
    assert D.suggest_itinerary(rows, event, 10)["train"] == "3"
    link = {
        "train": "22",
        "arrive_final_sched": "2026-10-16T08:05:00-04:00",
        "arrive_sched": "2026-10-16T07:40:00-04:00",
    }
    transfer = {
        "train": "21",
        "direct": False,
        "connection": link,
        "depart_sched": "2026-10-16T07:00:00-04:00",
        "arrive_sched": "2026-10-16T08:05:00-04:00",
        "arrive_est": "2026-10-16T08:05:00-04:00",
    }
    later = _row("9", "08:20", "07:50")
    picked = D.suggest_itinerary([transfer, later], event, 10, 10)
    assert picked["train"] == "21"
    assert picked["arrive_est"].startswith("2026-10-16T08:05")


def test_transfer_uses_the_final_arrival():
    schedule = _schedule()
    rows = D.build_itineraries(schedule, "Stop A", "Stop F", FRIDAY.date(), transfer_min=3, window="today")
    transfer = next(row for row in rows if row["train"] == "91021")
    assert transfer["direct"] is False
    assert "07:45:00" in transfer["arrive_sched"]
    assert "07:15:00" not in transfer["arrive_sched"]
    assert transfer["connection"]["train"] == "91006"


def test_tomorrow_and_a_day_with_no_service():
    schedule = _schedule()
    thursday_night = datetime(2026, 10, 15, 22, 0, tzinfo=NY)
    today = D.build_itineraries(
        schedule, "Stop A", "Stop F", thursday_night.date(), transfer_min=3, now=thursday_night, window="rest_of_day"
    )
    assert today == []
    friday = D.build_itineraries(schedule, "Stop A", "Stop F", datetime(2026, 10, 16).date(), transfer_min=3, window="today")
    event = {"summary": "Visit", "start": "2026-10-16T08:30:00-04:00", "location": "Stop F"}
    fields = D.suggestion_fields(
        friday,
        event,
        buffer_min=10,
        egress_walk_min=0,
        walk_minutes=12,
        destination="Stop F",
        destination_source="calendar",
    )
    assert fields["suggest_reason"] == "ok"
    assert fields["suggested_train"] == "91011"
    assert "07:28:00" in fields["leave_by"]
    assert fields["spare_min"] == 15
    assert fields["arrive_deadline"].startswith("2026-10-16T08:20")
    saturday = D.build_itineraries(schedule, "Stop A", "Stop F", datetime(2026, 10, 17).date(), window="today")
    assert saturday == []
    weekend = D.suggestion_fields(
        saturday,
        {"summary": "Visit", "start": "2026-10-17T08:30:00-04:00", "location": "Stop F"},
        buffer_min=10,
        destination="Stop F",
        destination_source="calendar",
        empty_service=True,
    )
    assert weekend["suggest_reason"] == "no_service"


def test_all_day_and_missing_location_and_nothing_in_time():
    now = datetime(2026, 10, 15, 22, 0, tzinfo=NY)
    chosen, reason = D.pick_calendar_event(
        None,
        [{"summary": "Off", "start": "2026-10-16", "all_day": True, "location": "Stop F"}],
        now,
    )
    assert chosen is None and reason == "no_event"
    bare = {"summary": "Visit", "start": "2026-10-16T08:30:00-04:00"}
    assert D.suggestion_fields([], bare, destination="Stop F", destination_source="default")["suggest_reason"] == "no_location"
    rows = D.build_itineraries(_schedule(), "Stop A", "Stop F", datetime(2026, 10, 16).date(), window="today")
    tight = D.suggestion_fields(
        rows,
        {"summary": "Visit", "start": "2026-10-16T07:30:00-04:00", "location": "Stop F"},
        buffer_min=10,
        egress_walk_min=10,
        destination="Stop F",
        destination_source="calendar",
    )
    assert tight["suggest_reason"] == "none_in_time"
    assert tight["suggested_train"] is None


def test_planner_after_and_arrive_by():
    schedule = _schedule()
    after = D.plan_query(
        schedule,
        NAMES,
        origin="Stop A",
        destination="Stop F",
        after="09:00",
        count=2,
        now=FRIDAY,
    )
    assert [row["train"] for row in after["rows"]] == ["91001", "91004"]
    assert after["day"] == "2026-10-16"
    rolled = D.plan_query(schedule, NAMES, origin="Stop A", destination="Stop F", after="22:00", count=1, now=datetime(2026, 10, 16, 22, 0, tzinfo=NY))
    assert rolled["day"] == "2026-10-18"
    assert rolled["rows"][0]["train"] == "91021"
    by = D.plan_query(
        schedule,
        NAMES,
        origin="Stop A",
        destination="Stop F",
        arrive_by="08:10",
        now=FRIDAY,
    )
    assert by["rows"][0]["train"] == "91011"
    assert by["rows"][0]["suggested"] is True
    assert by["suggested_train"] == "91011"
    assert all(row["arrive"] <= by["rows"][0]["arrive"] for row in by["rows"])
    live = D.plan_query(
        schedule,
        NAMES,
        origin="Stop A",
        destination="Stop F",
        after="09:00",
        count=1,
        now=FRIDAY,
        live_rows=[{"train": "91001", "delay_min": 4}],
    )
    assert live["rows"][0]["live"] is True
    assert live["rows"][0]["delay"] == 4


def test_plan_defaults_to_home_and_does_not_touch_origin():
    schedule = _schedule()
    manual = {"alpha": "Stop A"}
    before = dict(manual)
    home = D.plan_query(schedule, NAMES, origin="Stop F", home="Stop A", after="09:00", count=1, now=FRIDAY)
    assert home["destination"] == "Stop A"
    assert home["origin"] == "Stop F"
    assert manual == before
    assert D.plan_query(schedule, NAMES, origin="Nowhere", home="Stop A") == {"error": "not_found"}
    explicit = D.plan_query(schedule, NAMES, origin="Stop A", destination="Stop F", home="Stop B", after="09:00", count=1, now=FRIDAY)
    assert explicit["destination"] == "Stop F"
    text = (ROOT / "__init__.py").read_text()
    start = text.index("async def _plan_trips")
    end = text.index('DOMAIN,\n        "plan_trips"', start)
    assert "set_origin" not in text[start:end]
    assert "SupportsResponse.ONLY" in text
    assert "websocket_plan" in text
    assert S.WEBSOCKET_PLAN[vol.Required("type")] == "septa_live/plan"
    parsed = vol.Schema(S.PLAN_TRIPS)({"origin": "Stop A", "count": "3", "after": "09:06"})
    assert parsed["count"] == 3 and parsed["after"] == "09:06"
    assert vol.Schema(S.PLAN_TRIPS)({"origin": "Stop A", "count": 4})["count"] == 4
    socket = vol.Schema(S.WEBSOCKET_PLAN)({"type": "septa_live/plan", "origin": "Stop A", "rider": " alpha ", "count": "2"})
    assert socket["rider"] == "alpha" and socket["count"] == 2
    assert S.all_bare_leaves() == []
