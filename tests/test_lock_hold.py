"""Locked rides hold through weak GPS and follow the route shape, not station chords."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = _load("septa_ride_hold", "ride.py")


def train(number, lat, lon, heading=None, line="Lansdale/Doylestown", current="", dest="Doylestown", block=""):
    return R.Train(str(number), lat, lon, heading, dest, line, "LOCAL", current, "", 0, ["1"], "", block)


def fix(lat, lon, ts, speed=20, course=0, acc=10):
    return R.Fix(lat, lon, acc, speed, course, ts)


def _east(lon, meters):
    return lon + meters / 85000.0


def _curve():
    north = (40.10, -75.0)
    south = (40.00, -75.0)
    bow = _east(-75.0, 400)
    shape = []
    for index in range(11):
        mix = index / 10
        lat = north[0] + (south[0] - north[0]) * mix
        bulge = 1 - abs(mix - 0.5) * 2
        lon = -75.0 + (bow + 75.0) * bulge
        shape.append([round(lat, 5), round(lon, 5)])
    return north, south, (40.05, bow), shape


def test_curve_uses_the_shape_and_a_missing_shape_uses_the_wider_chord():
    north, south, bend, shape = _curve()
    here = train("1001", bend[0], bend[1], current="North Stop")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=400)
    matcher.set_route_shape(shape, "1001")
    matcher.set_stops(
        [
            {"lat": north[0], "lon": north[1], "stopname": "North Stop"},
            {"lat": south[0], "lon": south[1], "stopname": "South Stop"},
        ]
    )
    event = matcher.update(fix(bend[0], bend[1], 0, speed=20, course=0), [here], 0)
    assert event is not None and event.kind == "boarded"
    kept = matcher.update(fix(bend[0], bend[1], 30, speed=25, course=0, acc=12), [here], 30)
    assert kept is None and matcher.riding_train.trainno == "1001"
    assert matcher.corridor_source == "shape"
    assert matcher.corridor_gap_m <= 50

    bare = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=400)
    saved = R._GEO
    R._GEO = {
        "by_key": {},
        "by_coord": {},
        "lines": {
            "FOX": [
                {"n": "North Stop", "lat": north[0], "lon": north[1]},
                {"n": "South Stop", "lat": south[0], "lon": south[1]},
            ]
        },
    }
    try:
        fox = train("1001", bend[0], bend[1], line="FOX", current="North Stop")
        bare.update(fix(bend[0], bend[1], 0, speed=20, course=0), [fox], 0)
        assert bare.riding is True
        again = bare.update(fix(bend[0], bend[1], 40, speed=25, course=0), [fox], 40)
        assert again is None and bare.riding is True
        assert bare.corridor_source == "chord"
        assert bare.corridor_gap_m < R.CORRIDOR_CHORD_M
    finally:
        R._GEO = saved


def test_weak_fixes_hold_the_lock_until_three_good_fixes():
    _north, _south, bend, shape = _curve()
    locked = train("1001", bend[0], bend[1], current="Stop U")
    other = train("2002", bend[0], bend[1], line="Chestnut Hill East", current="Stop U")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=400, hold_exit_s=60)
    matcher.set_route_shape(shape, "1001")
    matcher.set_underground(["Stop U"])
    matcher.set_stops([{"lat": bend[0], "lon": bend[1], "stopname": "Stop U"}])
    started = matcher.update(fix(bend[0], bend[1], 0, speed=20, course=0), [locked], 0)
    assert started is not None and matcher.lock_state == "locked"
    for index, acc in enumerate((80, 120, 150, 90, 110), start=1):
        event = matcher.update(fix(bend[0], bend[1], 30 * index, speed=10, course=0, acc=acc), [locked, other], 30 * index)
        assert event is None
        assert matcher.riding_train.trainno == "1001"
        assert matcher.lock_state == "holding"
        assert matcher.switches == []
    assert matcher.hold_reason == "weak_gps"
    for ts in (400, 430, 470):
        event = matcher.update(fix(bend[0], bend[1], ts, speed=20, course=0, acc=12), [locked], ts)
        assert event is None
        assert matcher.riding_train.trainno == "1001"
    assert matcher.lock_state == "locked"
    assert matcher.hold_reason is None


def test_a_sustained_other_train_can_switch_unless_the_locked_train_is_fresh():
    spot = (40.0, -75.0)
    first = train("1001", spot[0], spot[1])
    other = train("2002", spot[0], spot[1], line="Warminster")
    matcher = R.RideMatcher(
        need_matches=1, min_speed_mps=5, radius_m=400, switch_good_fixes=4, switch_good_s=90, hold_exit_s=0
    )
    matcher.update(fix(spot[0], spot[1], 0, speed=20, course=0), [first], 0)
    assert matcher.riding_train.trainno == "1001"
    gone = train("1001", 40.08, -75.0)
    switched = False
    event = None
    for ts in (100, 140, 180, 220, 260):
        event = matcher.update(fix(spot[0], spot[1], ts, speed=20, course=0, acc=10), [gone, other], ts)
        if matcher.riding_train and matcher.riding_train.trainno == "2002":
            switched = True
            break
        if matcher.switch_blocked_reason not in {None, "sticky", "weak_gps"}:
            break
    assert switched, (
        matcher.switch_blocked_reason,
        matcher.distance_m,
        matcher.riding_train.trainno if matcher.riding_train else None,
        [(row["train"], row.get("dist_m"), row.get("last_reject_reason")) for row in matcher.candidates],
    )
    assert event is not None and event.kind == "boarded"

    fresh = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=300, switch_good_fixes=1, switch_good_s=0, hold_exit_s=0, apart_fixes=5)
    near = train("1001", spot[0], spot[1])
    fresh.update(fix(spot[0], spot[1], 0, speed=20, course=0), [near], 0)
    for ts in (40, 80, 120, 160):
        blocked = fresh.update(fix(spot[0], spot[1], ts, speed=20, course=0), [near, other], ts)
        assert blocked is None
        assert fresh.riding_train.trainno == "1001"
    assert fresh.switches == []


def test_a_false_end_resumes_the_same_train_and_does_not_cool_it_down():
    spot = (40.05, -75.0)
    here = train("1001", spot[0], spot[1], line="FOX", current="North Stop")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=300, recover_s=300)
    matcher.update(fix(spot[0], spot[1], 0, speed=20, course=0), [here], 0)
    boarded_at = matcher.boarded_at
    boarded_ts = matcher.boarded_ts
    matcher._exit(30, "left_corridor")
    assert matcher.riding is False
    assert matcher.cooldown_train is None
    resumed = matcher.update(fix(spot[0], spot[1], 60, speed=20, course=0, acc=8), [here], 60)
    assert resumed is None
    assert matcher.riding_train.trainno == "1001"
    assert matcher.boarded_at == boarded_at
    assert matcher.boarded_ts == boarded_ts
    assert matcher.resumed == 1
    assert matcher.last_reason == "resumed"
    assert not any(event.kind == "boarded" for event in matcher.events)


def test_after_a_false_end_a_passing_train_does_not_board():
    spot = (40.20, -75.20)
    ended = train("1001", 41.0, -76.0, line="FOX")
    passing = train("2002", spot[0], spot[1], line="CHE")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=300, recover_s=300)
    matcher._recover_train = "1001"
    matcher._recover_until = 400
    matcher._recover_boarded_at = "North Stop"
    matcher._recover_boarded_ts = 0
    event = matcher.update(fix(spot[0], spot[1], 100, speed=15.6, course=0, acc=8), [passing, ended], 100)
    assert event is None
    assert matcher.riding is False
    assert matcher.last_reason == "no_dwell"


def test_a_real_arrival_still_cools_the_train_down():
    here = train("111", 40.0, -75.0, line="FOX", current="Hub", dest="Hub")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=200)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [here], 0)
    matcher._exit(20, "arrived")
    assert matcher.cooldown_train == "111"
    blocked = matcher.update(fix(40.0, -75.0, 40, speed=20, course=0), [here], 40)
    assert blocked is None
    assert matcher.riding is False


def test_three_weak_rides_learn_an_underground_stop_and_options_override():
    matcher = R.RideMatcher()
    assert matcher.note_underground_ride("Stop U") is False
    assert matcher.note_underground_ride("Stop U") is False
    assert matcher.note_underground_ride("Stop U") is True
    assert "Stop U" in matcher.learned_underground
    matcher.set_underground(["Added Stop"], learned=[])
    assert matcher._stop_is_underground("Added Stop") is True
    assert matcher._stop_is_underground("Stop U") is False
    matcher.set_underground([], learned=["Stop U"])
    assert matcher._stop_is_underground("Stop U") is True


def test_replay_stays_on_the_boarded_train_through_the_curve():
    north = (40.10, -75.00)
    bend = (40.05, _east(-75.0, 380))
    samples = []
    for ts, point, speed in ((0, north, 20), (40, bend, 25), (80, bend, 25), (120, bend, 30)):
        others = [train("2002", point[0], point[1], line="Warminster")] if ts >= 80 else []
        samples.append(
            {
                "fix": fix(point[0], point[1], ts, speed=speed, course=0, acc=20),
                "trains": [train("1001", point[0], point[1], current="North Stop")] + others,
                "trains_ts": ts,
            }
        )
    result = R.replay_fixes(samples, need_matches=1, min_speed_mps=5, radius_m=400)
    assert result["riding"] is True
    assert result["train"] == "1001"
    assert all(event.get("train") != "2002" for event in result["events"])


def test_payload_carries_the_new_scalars():
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=200)
    here = train("1001", 40.0, -75.0)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0, acc=12), [here], 0)
    payload = matcher.payload()
    for key in (
        "gps_quality",
        "gps_accuracy_m",
        "fix_age_s",
        "hold_reason",
        "hold_since",
        "good_fix_streak",
        "corridor_gap_m",
        "corridor_source",
        "resumed",
        "last_end_reason",
        "last_end_ts",
    ):
        assert key in payload
    blob = json.dumps({key: payload[key] for key in payload if key not in {"candidates", "switches", "consist"}})
    assert len(blob.encode()) < 16_000
    assert payload["gps_quality"] == "good"
    assert payload["candidates"][0]["accuracy_m"] == 12
