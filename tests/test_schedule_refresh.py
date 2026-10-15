"""Timetable refresh. Synthetic GTFS only. No network."""

from __future__ import annotations

import importlib.util
import io
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S = _load("septa_schedule_refresh", "schedule.py")
R = _load("septa_ride_for_schedule", "ride.py")

TODAY = date(2026, 10, 14)
NOW = datetime(2026, 10, 14, 12, 0)


def _zip(files: dict[str, str], wrap: bool = False) -> bytes:
    def pack(payload: dict[str, str]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            for name, text in payload.items():
                archive.writestr(name, text)
        return buf.getvalue()

    inner = pack(files)
    if not wrap:
        return inner
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as archive:
        archive.writestr("google_rail.zip", inner)
    return outer.getvalue()


def _files(end: str = "20261121", extra_date: str = "") -> dict[str, str]:
    dates = ""
    if extra_date:
        dates = f"service_id,date,exception_type\nwk,{extra_date},1\n"
    return {
        "stops.txt": "stop_id,stop_name\n1,North End\n2,Hub\n",
        "trips.txt": "trip_id,route_id,service_id,trip_headsign,trip_short_name,direction_id\nt1,NORTH,wk,Hub,100,0\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nt1,09:00:00,09:00:00,1,1\nt1,09:20:00,09:20:00,2,2\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nwk,1,1,1,1,1,0,0,20260901,"
        + end
        + "\n",
        "calendar_dates.txt": dates or "service_id,date,exception_type\n",
        "feed_info.txt": "feed_publisher_name,feed_version,feed_end_date\nSEPTA,v-test," + end + "\n",
    }


def test_build_schedule_matches_the_timetable_shape():
    schedule = S.build_schedule(_zip(_files(), wrap=True))
    assert set(schedule) >= {"feed", "validUntil", "stations"}
    assert schedule["feed"] == "v-test"
    assert schedule["validUntil"] == "20261121"
    assert "North End" in schedule["stations"]
    assert schedule["stations"]["North End"]["S"][0]["n"] == "100"
    rows = R.remaining_from_timetable(schedule, "100", 0, None, None, None, None)
    assert rows[0]["station"] == "North End"
    assert rows[-1]["station"] == "Hub"
    extended = S.build_schedule(_zip(_files(end="20261001", extra_date="20261215")))
    assert extended["validUntil"] == "20261215"


def test_load_order():
    bundled = {"validUntil": "20261101", "stations": {"North End": {"S": []}}, "feed": "bundled"}
    fresh = {"validUntil": "20261201", "stations": {"Hub": {"S": []}}, "feed": "cache"}
    book = S.ScheduleBook()
    book.load(bundled, fresh, TODAY)
    assert book.origin == "downloaded"
    assert book.schedule["feed"] == "cache"
    assert book.expired is False

    expired_cache = {"validUntil": "20260101", "stations": {"Hub": {"S": []}}}
    book.load(bundled, expired_cache, TODAY)
    assert book.origin == "bundled"
    assert book.schedule is bundled

    old_bundle = {"validUntil": "20260101", "stations": {"North End": {"S": []}}}
    newer_cache = {"validUntil": "20260801", "stations": {"Hub": {"S": []}}}
    book.load(old_bundle, newer_cache, TODAY)
    assert book.expired is True
    assert book.schedule is newer_cache

    book.load(bundled, None, TODAY)
    assert book.origin == "bundled"
    assert S.read_schedule_file(ROOT / "missing-schedule.json") is None


def test_corrupt_cache_falls_back(tmp_path):
    path = tmp_path / "septa_live_rail_schedule.json"
    path.write_text("{not json", encoding="utf-8")
    assert S.read_schedule_file(path) is None
    bundled = {"validUntil": "20261201", "stations": {"North End": {"S": []}}}
    book = S.ScheduleBook()
    book.load(bundled, S.read_schedule_file(path), TODAY)
    assert book.schedule is bundled
    assert book.origin == "bundled"


def test_refresh_decision_and_304():
    current = {"validUntil": "20261024", "stations": {"North End": {"S": []}}}
    assert S.needs_download(current, TODAY) is False
    assert S.needs_download(current, TODAY, etag_changed=True) is True
    soon = {"validUntil": "20261019", "stations": {"North End": {"S": []}}}
    assert S.needs_download(soon, TODAY) is True
    expired = {"validUntil": "20261001", "stations": {"North End": {"S": []}}}
    assert S.needs_download(expired, TODAY) is True
    book = S.ScheduleBook()
    book.load(current, None, TODAY)
    book.note_not_modified(NOW)
    assert book.last_check == NOW
    assert book.schedule["validUntil"] == "20261024"
    assert book.last_error is None


def test_failed_refresh_keeps_the_schedule_and_repairs_only_when_close():
    bundled = {"validUntil": "20261024", "stations": {f"S{i}": {"S": []} for i in range(4)}}
    book = S.ScheduleBook()
    book.load(bundled, None, TODAY)
    book.fail(NOW, "download")
    assert book.schedule is bundled
    assert book.last_error == "download"
    assert book.needs_repair(TODAY) is False
    tiny = {"validUntil": "20261201", "stations": {"Only": {"S": []}}, "feed": "x"}
    assert book.accept(tiny, NOW, TODAY) is False
    assert book.schedule is bundled
    assert book.last_error == "too_small"
    near = {"validUntil": "20261015", "stations": {"North End": {"S": []}}}
    book.load(near, None, TODAY)
    book.fail(NOW, "download")
    assert book.needs_repair(TODAY) is True
    good = {"validUntil": "20261201", "stations": {"North End": {"S": []}, "Hub": {"S": []}}, "feed": "v2"}
    assert book.accept(good, NOW, TODAY) is True
    assert book.last_error is None
    assert book.needs_repair(TODAY) is False
    assert book.origin == "downloaded"


def test_sensor_reports_the_transition():
    bundled = {"validUntil": "20261017", "stations": {"North End": {"S": []}}, "feed": "bundled-feed"}
    book = S.ScheduleBook()
    book.load(bundled, None, date(2026, 10, 17))
    first = book.sensor(date(2026, 10, 17))
    assert first["state"] == "2026-10-17"
    assert first["source"] == "bundled"
    assert first["feed"] == "bundled-feed"
    assert first["days_remaining"] == 0
    downloaded = {"validUntil": "20261121", "stations": {"Hub": {"S": []}}, "feed": "v-next"}
    assert book.accept(downloaded, NOW, date(2026, 10, 17)) is True
    second = book.sensor(date(2026, 10, 17))
    assert second["state"] == "2026-11-21"
    assert second["source"] == "downloaded"
    assert second["feed"] == "v-next"
    assert second["last_success"] == NOW
    assert second["last_error"] is None


def test_refresh_does_not_write_the_package(tmp_path):
    package = ROOT / "rail-schedule.json"
    before = package.stat().st_mtime
    dest = tmp_path / "storage" / "septa_live_rail_schedule.json"
    S.write_schedule_file(dest, {"schedule": {"validUntil": "20261201", "stations": {"North End": {"S": []}}}})
    assert dest.is_file()
    assert S.read_schedule_file(dest)["stations"]
    assert package.stat().st_mtime == before
    assert not (ROOT / "septa_live_rail_schedule.json").exists()
