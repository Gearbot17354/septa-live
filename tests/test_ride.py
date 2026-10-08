"""Ride matcher tests. Loads ride.py directly so the integration package is not imported."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures"


def _load():
    spec = importlib.util.spec_from_file_location("septa_ride", ROOT / "ride.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["septa_ride"] = module
    spec.loader.exec_module(module)
    return module


R = _load()


def train(number, lat, lon, heading, dest="Doylestown", line="Lansdale/Doylestown", current="", nxt=""):
    return R.Train(
        trainno=str(number),
        lat=lat,
        lon=lon,
        heading=heading,
        dest=dest,
        line=line,
        service="LOCAL",
        currentstop=current,
        nextstop=nxt,
        late=1,
        consist=["1", "2"],
    )


def fix(lat, lon, ts, speed=20, course=0, acc=8):
    return R.Fix(lat, lon, acc, speed, course, ts)


def test_haversine_and_bearing():
    assert R.haversine_m(40.0, -75.0, 40.0, -75.0) == 0
    north = R.haversine_m(40.0, -75.0, 41.0, -75.0)
    assert 110_000 < north < 112_000
    assert R.bearing_deg(40.0, -75.0, 41.0, -75.0) < 1
    assert R.angle_diff(10, 350) == 20


def test_board_after_n_matches_along_3540():
    snaps = []
    for index in range(1, 6):
        rows = json.loads((FIX / f"tv_{index}.json").read_text())
        snaps.append(next(item for item in R.parse_trainview(rows) if item.trainno == "3540"))
    matcher = R.RideMatcher(need_matches=2, min_speed_mps=5, radius_m=300)
    first = snaps[0]
    early = matcher.update(fix(first.lat, first.lon, 1_700_000_000, course=first.heading), [first], 1_700_000_000)
    assert early is None
    assert matcher.riding is False
    second = snaps[1]
    boarded = matcher.update(
        fix(second.lat, second.lon, 1_700_000_015, course=second.heading),
        [second],
        1_700_000_015,
    )
    assert boarded is not None and boarded.kind == "boarded"
    assert matcher.riding is True
    assert boarded.payload["train"] == "3540"


def test_no_board_when_stationary_or_inaccurate():
    here = train("3540", 40.16, -75.24, 320)
    still = R.RideMatcher(need_matches=1, min_speed_mps=5)
    still.update(fix(40.16, -75.24, 100, speed=0, course=320), [here], 100)
    assert still.riding is False
    sloppy = R.RideMatcher(need_matches=1, min_speed_mps=5, max_accuracy_m=100)
    sloppy.update(fix(40.16, -75.24, 100, speed=20, course=320, acc=150), [here], 100)
    assert sloppy.riding is False
    assert sloppy.candidate is None


def test_opposite_heading_rejected():
    north = train("N", 40.0, -75.0, 0)
    south = train("S", 40.0, -75.0, 180)
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5)
    event = matcher.update(fix(40.0, -75.0, 50, speed=20, course=0), [north, south], 50)
    assert event.payload["train"] == "N"


def test_thirty_second_skew_still_matches():
    origin = train("3540", 40.0, -75.0, 0)
    matcher = R.RideMatcher(radius_m=250, need_matches=2, min_speed_mps=5)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [origin], 0)
    phone = R.project_position(40.0, -75.0, 0, 20, 30)
    event = matcher.update(fix(phone[0], phone[1], 30, speed=20, course=0), [origin], 0)
    assert event is not None and event.kind == "boarded"


def test_glitch_train_ignored():
    start = train("9", 40.0, -75.0, 0)
    jumped = R.project_position(40.0, -75.0, 0, 19_000, 1)
    later = train("9", jumped[0], jumped[1], 0)
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=300)
    matcher.update(fix(39.0, -75.0, 0, speed=20, course=0), [start], 0)
    event = matcher.update(fix(jumped[0], jumped[1], 15, speed=20, course=0), [later], 15)
    assert event is None
    assert matcher.riding is False


def test_gps_gap_keeps_riding():
    here = train("3540", 40.2, -75.28, 10, current="Lansdale", nxt="Penllyn")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5)
    matcher.update(fix(40.2, -75.28, 1_000, speed=20, course=10), [here], 1_000)
    assert matcher.riding is True
    event = matcher.tick(1_000 + 6 * 60, [here], 1_000 + 6 * 60)
    assert event is None
    assert matcher.riding is True
    assert matcher.gps_gap is True
    assert matcher.payload()["confidence"] == "gps_gap"


def test_three_misses_exit():
    here = train("3540", 40.0, -75.0, 0)
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=200)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [here], 0)
    event = None
    for index in range(1, 4):
        event = matcher.update(fix(40.0, -74.8, index * 20, speed=20, course=90), [here], index * 20)
    assert event is not None and event.kind == "exited"
    assert matcher.riding is False
    assert event.payload["reason"] == "misses"


def test_stationary_at_station_exits():
    station = train("3540", 40.0, -75.0, 0, current="Lansdale")
    gone = train("3540", 40.05, -75.0, 0, current="Ambler")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=200)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [station], 0)
    assert matcher.riding is True
    event = None
    for ts in (30, 90, 200):
        event = matcher.update(fix(40.0, -75.0, ts, speed=0, course=0), [gone], ts)
    assert event is not None and event.kind == "exited"
    assert event.payload["reason"] == "stationary"


def test_home_exits():
    here = train("3540", 40.0, -75.0, 0)
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5)
    matcher.update(fix(40.0, -75.0, 10, speed=20, course=0), [here], 10)
    event = matcher.set_tracker_state("home", ts=40)
    assert event.kind == "exited"
    assert event.payload["reason"] == "home"
    assert matcher.riding is False


def test_switch_requires_n_matches():
    first = train("111", 40.0, -75.0, 0, dest="Doylestown")
    other_at = R.project_position(40.0, -75.0, 0, 2000, 1)
    second = train("222", other_at[0], other_at[1], 0, dest="Warminster", line="Warminster")
    matcher = R.RideMatcher(need_matches=2, min_speed_mps=5, radius_m=200)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [first], 0)
    matcher.update(fix(40.0, -75.0, 15, speed=20, course=0), [first], 15)
    assert matcher.riding_train.trainno == "111"
    phone = fix(other_at[0], other_at[1], 40, speed=20, course=0)
    held = matcher.update(phone, [second], 40)
    assert matcher.riding_train.trainno == "111"
    assert held is None or held.kind != "boarded"
    switched = matcher.update(fix(other_at[0], other_at[1], 55, speed=20, course=0), [second], 55)
    assert switched is not None and switched.kind == "boarded"
    assert matcher.riding_train.trainno == "222"
    kinds = [item.kind for item in matcher.events]
    assert kinds == ["exited", "boarded"]


def test_remaining_stops_filter_actual_times():
    rows = json.loads((FIX / "rr3540.json").read_text())
    pending = R.remaining_stops(rows)
    assert pending
    assert all(item["station"] for item in pending)
    target = pending[0]["station"]
    for row in rows:
        if row.get("station") == target:
            row["act_tm"] = "4:09 pm"
            break
    again = R.remaining_stops(rows)
    assert len(again) == len(pending) - 1
    assert again[0]["station"] != target


def test_parse_trainview_sample():
    rows = json.loads((FIX / "trainview_sample.json").read_text())
    trains = R.parse_trainview(rows)
    assert any(item.trainno == "3540" and item.consist for item in trains)
    blank = next(item for item in trains if item.consist == [] or item.trainno == "1082")
    assert isinstance(blank.consist, list)
