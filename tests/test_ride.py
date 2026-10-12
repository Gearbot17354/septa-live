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


def _et(hour, minute, second):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime(2026, 10, 12, hour, minute, second, tzinfo=ZoneInfo("America/New_York")).timestamp()


def _iphone_fixes(speed=0, course=0):
    return [
        (40.23747, -75.28388, _et(9, 46, 52), 19.6),
        (40.18434, -75.25670, _et(9, 59, 34), 18.8),
        (40.16986, -75.24350, _et(10, 2, 37), 37.9),
        (40.1560, -75.2310, _et(10, 5, 37), 30.0),
    ], speed, course


def _pair(phone, heading, distance=250, behind_s=0, speed_mps=10.7):
    """Inbound train near the phone, plus an outbound train on the opposite heading."""
    back = R.project_position(phone[0], phone[1], (heading + 180) % 360, speed_mps, behind_s) if behind_s else phone
    inbound_at = R.project_position(back[0], back[1], heading, 1, distance if not behind_s else 0)
    if behind_s:
        inbound_at = back
    outbound_at = inbound_at
    inbound = train("4302", inbound_at[0], inbound_at[1], heading, dest="Jefferson", line="Lansdale/Doylestown")
    outbound = train("4321", outbound_at[0], outbound_at[1], (heading + 180) % 360, dest="Doylestown", line="Lansdale/Doylestown")
    return [inbound, outbound]


def _replay_iphone(speed, trains_offset, place):
    points, speed, course = _iphone_fixes(speed, 0 if speed == 0 else None)
    heading = R.bearing_deg(points[1][0], points[1][1], points[2][0], points[2][1])
    samples = []
    for lat, lon, ts, acc in points:
        rows = [] if place == "none" else _pair((lat, lon), heading, distance=380 if trains_offset else 200, behind_s=trains_offset)
        samples.append(
            {
                "fix": R.Fix(lat, lon, acc, speed, course, ts),
                "trains": rows,
                "trains_ts": ts - trains_offset,
                "now": ts,
            }
        )
    live = R.RideMatcher()
    before = live.riding
    result = R.replay_fixes(samples, radius_m=300, min_speed_mps=15 * 0.44704, need_matches=2, max_accuracy_m=100)
    assert live.riding is before
    return result


def test_sparse_iphone_speed_zero_boards_inbound():
    result = _replay_iphone(0, 0, "near")
    third = result["steps"][2]
    assert third["speed_source"] == "derived"
    assert 20 < third["phone_speed_mph"] < 30
    assert third["reason"] == "candidate"
    assert result["steps"][3]["reason"] == "boarded"
    assert result["riding"] is True
    assert result["events"][-1]["train"] == "4302"


def test_sparse_iphone_missing_speed_boards_inbound():
    result = _replay_iphone(None, 0, "near")
    assert result["steps"][2]["speed_source"] == "derived"
    assert result["events"][-1]["train"] == "4302"
    assert result["riding"] is True


def test_sparse_iphone_stale_trainview_still_boards():
    result = _replay_iphone(0, 90, "near")
    assert result["riding"] is True
    assert result["events"][-1]["train"] == "4302"


def test_sparse_iphone_no_train_nearby():
    result = _replay_iphone(0, 0, "none")
    assert result["riding"] is False
    assert result["events"] == []
    assert result["steps"][-1]["reason"] == "no_train_in_radius"


def test_stationary_phone_does_not_board():
    here = train("4302", 40.17, -75.24, 150, dest="Jefferson", line="Lansdale/Doylestown")
    samples = []
    ts = _et(10, 0, 0)
    for index in range(4):
        samples.append(
            {
                "fix": R.Fix(40.17, -75.24, 20, 0, 0, ts + index * 180),
                "trains": [here],
                "trains_ts": ts + index * 180,
                "now": ts + index * 180,
            }
        )
    result = R.replay_fixes(samples, radius_m=300, min_speed_mps=15 * 0.44704, need_matches=2)
    assert result["riding"] is False
    assert result["steps"][-1]["reason"] == "not_moving"


def test_state_write_from_a_thread_is_scheduled():
    import threading

    class Loop:
        def __init__(self):
            self.calls = []

        def call_soon_threadsafe(self, fn):
            self.calls.append(fn)

    class Hass:
        def __init__(self):
            self.loop = Loop()
            self.loop_thread_id = threading.get_ident()

    hass = Hass()
    wrote = []
    box = {}

    def from_thread():
        R.write_state_on_loop(hass, lambda: wrote.append("my_train"))
        R.write_state_on_loop(hass, lambda: wrote.append("riding"))

    worker = threading.Thread(target=from_thread)
    worker.start()
    worker.join()
    assert wrote == []
    assert len(hass.loop.calls) == 2
    for call in hass.loop.calls:
        call()
    assert wrote == ["my_train", "riding"]
    sensor = (ROOT / "sensor.py").read_text()
    binary = (ROOT / "binary_sensor.py").read_text()
    assert "write_state_on_loop(self.hass, self.async_write_ha_state)" in sensor
    assert "write_state_on_loop(self.hass, self.async_write_ha_state)" in binary
    box["ok"] = True
    assert box["ok"]

