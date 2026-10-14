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


def test_hint_does_not_override_radius_or_heading():
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=100)
    matcher.set_expected({"train": "999"})
    far = train("999", 41.0, -76.0, 0)
    near = train("111", 40.0, -75.0, 0)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [far, near], 0)
    assert matcher.riding_train.trainno == "111"


def test_hint_is_preferred_inside_the_radius():
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=300)
    matcher.set_expected({"train": "222", "connection_train": "333", "connection_station": "Suburban Station"})
    other = train("111", 40.0, -75.0, 0)
    hinted = train("222", 40.0, -75.0, 0)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [other, hinted], 0)
    assert matcher.riding_train.trainno == "222"
    boarded = matcher.boarded_ts
    arrived = train("222", 40.0, -75.0, 0, current="Suburban Station")
    matcher.update(fix(40.0, -75.0, 20, speed=20, course=0), [arrived], 20)
    assert matcher.leg == 2
    assert matcher.boarded_ts == boarded
    second = train("333", 40.0, -75.0, 0)
    matcher.update(fix(40.0, -75.0, 40, speed=20, course=0), [second], 40)
    assert matcher.riding_train.trainno == "333"
    assert matcher.boarded_ts == boarded
    assert matcher.payload()["leg"] == 2
    assert matcher.payload()["expected_train"] == "333"
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


def _train_6581():
    real = {
        "Chalfont",
        "Link Belt",
        "Fortuna",
        "9TH Street Lansdale",
        "Lansdale",
        "North Wales",
        "Penllyn",
        "Ambler",
        "Fort Washington",
    }
    names = [
        "Doylestown",
        "Delaware Valley College",
        "New Britain",
        "Chalfont",
        "Link Belt",
        "Fortuna",
        "Colmar",
        "Pennbrook",
        "Lansdale",
        "9TH Street Lansdale",
        "North Wales",
        "Penllyn",
        "Gwynedd Valley",
        "Ambler",
        "Fort Washington",
        "Temple University",
        "Jefferson Station",
        "Suburban Station",
        "Gray 30th Street",
    ]
    return [
        {"station": name, "sched_tm": "7:00 am", "est_tm": "7:08 am", "act_tm": "7:08 am" if name in real else "na"}
        for name in names
    ]


def test_remaining_stops_6581_starts_after_current():
    rows = _train_6581()
    pending = R.remaining_stops(rows, "Fort Washington", "Temple University")
    assert [row["station"] for row in pending] == [
        "Temple University",
        "Jefferson Station",
        "Suburban Station",
        "Gray 30th Street",
    ]
    assert pending[0]["station"] == "Temple University"
    assert pending[0]["sched"] == "7:00 am"


def test_remaining_stops_falls_back_to_last_actual():
    rows = _train_6581()
    pending = R.remaining_stops(rows, "Not A Stop")
    assert pending[0]["station"] == "Temple University"


def test_remaining_stops_not_departed_keeps_the_list():
    rows = [
        {"station": "Doylestown", "sched_tm": "6:00 am", "est_tm": "6:00 am", "act_tm": "na"},
        {"station": "Lansdale", "sched_tm": "6:20 am", "est_tm": "6:20 am", "act_tm": ""},
        {"station": "Temple University", "sched_tm": "7:00 am", "est_tm": "7:00 am", "act_tm": "na"},
    ]
    pending = R.remaining_stops(rows)
    assert [row["station"] for row in pending] == ["Doylestown", "Lansdale", "Temple University"]


def test_timetable_remaining_starts_after_current():
    schedule = {
        "stations": {
            "Doylestown": {"S": [{"t": "06:10", "n": "6581", "days": 127}]},
            "Fort Washington": {"S": [{"t": "06:40", "n": "6581", "days": 127}]},
            "Temple University": {"S": [{"t": "07:05", "n": "6581", "days": 127}]},
            "Gray 30th Street": {"S": [{"t": "07:20", "n": "6581", "days": 127}]},
        }
    }
    pending = R.remaining_from_timetable(schedule, "6581", 0, 7 * 60, "Fort Washington", "Temple University")
    assert [row["station"] for row in pending] == ["Temple University", "Gray 30th Street"]
    assert pending[0]["station"] == "Temple University"


def test_stop_name_normalisation():
    rows = _train_6581()
    by_current = R.remaining_stops(rows, "Fort Washington Station")
    by_gray = R.remaining_stops(rows, "30th Street Gray")
    assert by_current[0]["station"] == "Temple University"
    assert by_gray == []
    aligned = R.remaining_stops(rows, "Ambler", "temple university station")
    assert aligned[0]["station"] == "Temple University"


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


def test_old_tracker_option_is_the_primary_rider():
    riders = R.configured_riders({}, {"ride_tracker": "device_tracker.alex_phone"})
    assert riders == ["device_tracker.alex_phone"]
    specs = R.dedupe_riders(
        riders,
        {"person.alex": "device_tracker.alex_phone"},
    )
    assert specs[0]["slug"] == "alex"
    assert specs[0]["primary"] is True
    assert specs[0]["person"] == "person.alex"


def test_person_and_their_phone_are_one_rider():
    specs = R.dedupe_riders(
        ["person.alex", "device_tracker.alex_phone", "person.sam", "person.jordan"],
        {
            "person.alex": "device_tracker.alex_phone",
            "person.sam": "device_tracker.sam_phone",
            "person.jordan": "device_tracker.jordan_phone",
        },
    )
    assert [item["slug"] for item in specs] == ["alex", "sam", "jordan"]
    assert sum(1 for item in specs if item["primary"]) == 1


def test_two_riders_do_not_share_a_matcher():
    first = _replay_iphone(0, 0, "near")
    second = _replay_iphone(0, 0, "none")
    assert first["riding"] is True
    assert second["riding"] is False
    summary = R.riders_summary(
        [
            {
                "rider": "alex",
                "riding": True,
                "train": "4302",
                "person": "person.alex",
                "friendly_name_rider": "Alex",
                "entity_picture": "/api/image/alex",
                "line": "Lansdale/Doylestown",
                "next_stop": "Penllyn",
            },
            {
                "rider": "sam",
                "riding": True,
                "train": "4302",
                "person": "person.sam",
                "friendly_name_rider": "Sam",
                "line": "Lansdale/Doylestown",
                "next_stop": "Penllyn",
            },
        ]
    )
    assert summary["count"] == 2
    assert summary["trains"]["4302"] == ["alex", "sam"]
    assert summary["riding"][0]["entity_picture"] == "/api/image/alex"


def test_one_trainview_fetch_for_three_riders():
    import asyncio

    cache = R.TrainCache(15)

    async def fetch():
        return [{"trainno": "4302"}]

    async def main():
        await asyncio.gather(cache.get(1_000, fetch), cache.get(1_000, fetch), cache.get(1_001, fetch))

    asyncio.run(main())
    assert cache.fetches == 1


def test_riders_count_starts_at_zero():
    idle = [
        {"rider": "alex", "riding": False, "person": "person.alex", "friendly_name_rider": "Alex", "entity_picture": None, "train": None, "line": None, "next_stop": None},
        {"rider": "sam", "riding": False, "person": "person.sam", "friendly_name_rider": "Sam", "entity_picture": None, "train": None, "line": None, "next_stop": None},
        {"rider": "jordan", "riding": False, "person": "person.jordan", "friendly_name_rider": "Jordan", "entity_picture": None, "train": None, "line": None, "next_stop": None},
    ]
    quiet = R.riders_summary(idle)
    assert quiet["count"] == 0
    assert quiet["riding"] == []
    assert quiet["riders"] == ["alex", "sam", "jordan"]
    idle[1]["riding"] = True
    idle[1]["train"] = "4302"
    idle[1]["line"] = "Lansdale/Doylestown"
    idle[1]["next_stop"] = "Penllyn"
    idle[1]["entity_picture"] = "/api/image/sam"
    boarded = R.riders_summary(idle)
    assert boarded["count"] == 1
    assert boarded["riding"] == [
        {
            "rider": "sam",
            "person": "person.sam",
            "friendly_name": "Sam",
            "entity_picture": "/api/image/sam",
            "train": "4302",
            "line": "Lansdale/Doylestown",
            "next_stop": "Penllyn",
        }
    ]
    assert boarded["trains"] == {"4302": ["sam"]}
    sensor = (ROOT / "sensor.py").read_text()
    assert "class SeptaRidersCountSensor" in sensor
    assert "def _on_ride" in sensor.split("class SeptaRidersCountSensor", 1)[1]
    assert "rider.signal()" in sensor
    assert 'self.entity_id = "sensor.septa_riders_count"' in sensor


def _exits(events):
    return [item for item in events if item.kind == "exited"]


def test_arrived_when_the_train_leaves():
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=300)
    matcher.set_expected({"train": "8", "destination": "Lansdale"})
    here = train("8", 40.24278, -75.285, 0, current="Lansdale", line="Lansdale/Doylestown")
    matcher.update(fix(40.24278, -75.285, 0, speed=20, course=0), [here], 0)
    assert matcher.riding is True
    stayed = matcher.update(fix(40.24278, -75.285, 20, speed=20, course=0), [here], 20)
    assert stayed is None
    assert matcher.riding is True
    gone = train("8", 40.30, -75.20, 0, current="Doylestown", line="Lansdale/Doylestown")
    event = matcher.update(fix(40.24278, -75.285, 40, speed=20, course=0), [gone], 40)
    assert event is not None and event.kind == "exited"
    assert event.payload["reason"] == "arrived"
    assert len(_exits(matcher.events)) == 1
    assert matcher.payload()["ended_reason"] == "arrived"
    assert matcher.payload()["ended_at"]


def test_walk_beside_estimated_train_ends_slow():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    when = datetime(2026, 10, 13, 16, 0, tzinfo=ZoneInfo("America/New_York"))
    ts = when.timestamp()
    row = train(
        "3544",
        39.9538889,
        -75.1677778,
        342,
        dest="Doylestown",
        line="Lansdale/Doylestown",
        current="Temple University",
        nxt="Fort Washington",
    )
    row.consist = []
    row.late = 0
    phone = (39.98139, -75.14944)
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=400)
    matcher.update(fix(phone[0], phone[1], ts, speed=20, course=342), [row], ts)
    assert matcher.riding is True
    event = None
    for step in (60, 120, 200):
        event = matcher.update(
            fix(phone[0], phone[1], ts + step, speed=3 * 0.44704, course=342),
            [row],
            ts,
        )
    assert event is not None and event.kind == "exited"
    assert event.payload["reason"] == "slow"
    assert len(_exits(matcher.events)) == 1
    assert matcher.payload()["ended_reason"] == "slow"


def test_live_train_stopped_at_a_signal_stays_on():
    here = train("8", 40.0, -75.0, 0, current="Between", dest="Doylestown")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=200)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [here], 0)
    event = None
    for ts in (60, 120, 200):
        event = matcher.update(fix(40.0, -75.0, ts, speed=0, course=0), [here], ts)
    assert matcher.riding is True
    assert event is None


def test_estimated_train_separates_after_two_far_fixes():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    when = datetime(2026, 10, 13, 16, 0, tzinfo=ZoneInfo("America/New_York"))
    ts = when.timestamp()
    row = train(
        "3544",
        39.9538889,
        -75.1677778,
        342,
        line="Lansdale/Doylestown",
        current="Temple University",
        nxt="Fort Washington",
    )
    row.consist = []
    row.late = 0
    phone = (39.98139, -75.14944)
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=400)
    matcher.update(fix(phone[0], phone[1], ts, speed=20, course=342), [row], ts)
    assert matcher.riding is True
    one = matcher.update(fix(41.2, -74.2, ts + 30, speed=20, course=0), [row], ts)
    assert one is None
    assert matcher.riding is True
    two = matcher.update(fix(41.2, -74.2, ts + 50, speed=20, course=0), [row], ts)
    assert two is not None and two.payload["reason"] == "separated"
    assert len(_exits(matcher.events)) == 1
    assert matcher.payload()["ended_reason"] == "separated"


def test_leaving_the_corridor_ends_the_ride():
    phone = (39.98139, -75.14944)
    here = train("8", phone[0], phone[1], 342, line="Lansdale/Doylestown", current="Temple University")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=300)
    matcher.update(fix(phone[0], phone[1], 0, speed=20, course=342), [here], 0)
    assert matcher.riding is True
    east = -75.14944 + (550 / 85_000)
    moved = train("8", phone[0], east, 342, line="Lansdale/Doylestown", current="Temple University")
    first = matcher.update(fix(phone[0], east, 20, speed=20, course=90), [moved], 20)
    assert first is None and matcher.riding is True
    second = matcher.update(fix(phone[0], east, 40, speed=20, course=90), [moved], 40)
    assert second is not None and second.payload["reason"] == "left_corridor"
    assert len(_exits(matcher.events)) == 1
    assert matcher.payload()["ended_reason"] == "left_corridor"


def test_terminal_ends_on_the_next_fix():
    here = train("8", 40.0, -75.0, 0, dest="Doylestown", current="Penllyn")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=200)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [here], 0)
    done = train("8", 40.0, -75.0, 0, dest="Doylestown", current="Doylestown")
    marked = matcher.update(fix(40.0, -75.0, 20, speed=20, course=0), [done], 20)
    assert marked is None and matcher.riding is True
    event = matcher.update(fix(40.0, -75.0, 40, speed=20, course=0), [done], 40)
    assert event is not None and event.payload["reason"] == "terminal"
    assert len(_exits(matcher.events)) == 1
    assert matcher.payload()["ended_reason"] == "terminal"


def test_max_duration_ends_the_ride():
    here = train("zz", 40.0, -75.0, 0, current="Penllyn")
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=200, max_ride_seconds=100)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [here], 0)
    event = matcher.tick(101, [here], 101)
    assert event is not None and event.payload["reason"] == "max_duration"
    assert len(_exits(matcher.events)) == 1
    assert matcher.payload()["ended_reason"] == "max_duration"


def test_reboard_cooldown_blocks_only_that_train():
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=200)
    first = train("111", 40.0, -75.0, 0)
    second = train("222", 40.0, -75.0, 0)
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [first], 0)
    assert matcher.riding_train.trainno == "111"
    matcher.set_tracker_state("home", ts=10)
    assert matcher.riding is False
    blocked = matcher.update(fix(40.0, -75.0, 30, speed=20, course=0), [first], 30)
    assert blocked is None and matcher.riding is False
    other = matcher.update(fix(40.0, -75.0, 40, speed=20, course=0), [second], 40)
    assert other is not None and matcher.riding_train.trainno == "222"
    matcher.set_tracker_state("home", ts=50)
    later = matcher.update(fix(40.0, -75.0, 660, speed=20, course=0), [first], 660)
    assert later is not None and matcher.riding_train.trainno == "111"


def test_handover_is_not_blocked_by_cooldown():
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=300)
    matcher.set_expected({"train": "222", "connection_train": "333", "connection_station": "Suburban Station"})
    first = train("222", 40.0, -75.0, 0, current="Temple University")
    matcher.update(fix(40.0, -75.0, 0, speed=20, course=0), [first], 0)
    matcher.leg = 2
    matcher._cooldown["333"] = 0
    second = train("333", 40.0, -75.0, 0, current="Suburban Station")
    event = matcher.update(fix(40.0, -75.0, 30, speed=20, course=0), [second], 30)
    assert event is not None and event.kind == "boarded"
    assert matcher.riding_train.trainno == "333"


def test_geo_files_are_read_once_and_preloaded_off_loop():
    import asyncio

    R._GEO = None
    R._TIMES = None
    calls = {"n": 0}
    original = Path.read_text

    def wrapped(self, *args, **kwargs):
        if self.name in {"rail-geo.json", "rail-schedule.json"}:
            calls["n"] += 1
        return original(self, *args, **kwargs)

    Path.read_text = wrapped
    try:
        R._load_geo()
        R._load_times()
        R._load_geo()
        R._load_times()
        assert calls["n"] == 2
    finally:
        Path.read_text = original

    class Hass:
        def __init__(self):
            self.jobs = []

        async def async_add_executor_job(self, func, *args):
            self.jobs.append(func.__name__)
            return func(*args)

    hass = Hass()
    asyncio.run(R.async_preload(hass))
    assert hass.jobs == ["_load_geo", "_load_times"]


def _frozen_3544():
    row = train(
        "3544",
        39.9538889,
        -75.1677778,
        120,
        dest="Doylestown",
        line="Lansdale/Doylestown",
        current="Temple University",
        nxt="Fort Washington",
    )
    row.service = "EXP TO FT WASH"
    row.late = 9
    row.consist = []
    return row


def test_frozen_trainview_uses_estimated_position():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    when = datetime(2026, 10, 13, 16, 48, tzinfo=ZoneInfo("America/New_York"))
    ts = when.timestamp()
    speed = 58 * 0.44704
    phone = (40.0329, -75.1415)
    samples = []
    for index in range(2):
        samples.append(
            {
                "fix": fix(phone[0], phone[1], ts + index * 5, speed=speed, course=0),
                "trains": [_frozen_3544()],
                "trains_ts": ts,
            }
        )
    result = R.replay_fixes(samples, need_matches=2, radius_m=300, min_speed_mps=5)
    assert result["riding"] is True
    assert result["steps"][-1]["train"] == "3544"
    assert result["position_source"] == "estimated"
    assert result["steps"][-1]["position_source"] == "estimated"


def test_fresh_gps_still_beats_a_stale_train():
    fresh = train("111", 40.0329, -75.1415, 0, dest="Doylestown", line="Lansdale/Doylestown", current="Wayne Junction", nxt="Fern Rock T C")
    stale = _frozen_3544()
    from datetime import datetime
    from zoneinfo import ZoneInfo

    when = datetime(2026, 10, 13, 16, 48, tzinfo=ZoneInfo("America/New_York"))
    ts = when.timestamp()
    speed = 58 * 0.44704
    samples = [
        {
            "fix": fix(40.0329, -75.1415, ts + index * 20, speed=speed, course=0),
            "trains": [stale, fresh],
            "trains_ts": ts,
        }
        for index in range(2)
    ]
    result = R.replay_fixes(samples, need_matches=2, radius_m=300, min_speed_mps=5)
    assert result["riding"] is True
    assert result["steps"][-1]["train"] == "111"
    assert result["position_source"] == "gps"


def test_parked_phone_does_not_board():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    when = datetime(2026, 10, 13, 16, 48, tzinfo=ZoneInfo("America/New_York"))
    ts = when.timestamp()
    result = R.replay_fixes(
        [
            {
                "fix": fix(39.95389, -75.16778, ts, speed=0, course=0),
                "trains": [_frozen_3544()],
                "trains_ts": ts,
            }
        ],
        need_matches=1,
        radius_m=300,
        min_speed_mps=5,
    )
    assert result["riding"] is False


def test_fast_phone_far_from_the_corridor_does_not_board():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    when = datetime(2026, 10, 13, 16, 48, tzinfo=ZoneInfo("America/New_York"))
    ts = when.timestamp()
    speed = 58 * 0.44704
    samples = [
        {
            "fix": fix(41.2, -74.2, ts + index * 30, speed=speed, course=0),
            "trains": [_frozen_3544()],
            "trains_ts": ts,
        }
        for index in range(2)
    ]
    result = R.replay_fixes(samples, need_matches=2, radius_m=300, min_speed_mps=5)
    assert result["riding"] is False


def test_same_timestamp_accepts_a_move_and_drops_an_identical_fix():
    matcher = R.RideMatcher(need_matches=2, radius_m=300, min_speed_mps=1)
    first = R.Fix(40.0, -75.0, 8, 22.8, 0, 1_000.0)
    matcher.update(first, [], 1_000.0, now=1_000.0)
    assert matcher.last_reason != "duplicate_ts"
    moved = R.Fix(40.01, -75.0, 8, 22.8, 0, 1_000.0)
    matcher.update(moved, [], 1_000.0, now=1_000.0)
    assert matcher.last_reason != "duplicate_ts"
    assert matcher.accepted_fix_count == 2
    assert matcher.last_fix.ts == 1_001.0
    again = R.Fix(
        matcher.last_fix.lat,
        matcher.last_fix.lon,
        matcher.last_fix.acc_m,
        matcher.last_fix.speed_mps,
        matcher.last_fix.course,
        matcher.last_fix.ts,
    )
    matcher.update(again, [], 1_001.0, now=1_001.0)
    assert matcher.last_reason == "duplicate_ts"
    assert matcher.skipped_fix_count == 1
    assert matcher.accepted_fix_count == 2


def test_speed_confirms_stale_estimated_train_and_rejects_the_wrong_heading():
    phone_lat = 39.0 - (842 / 111_320)
    phone_lon = -75.0
    original = R.estimate_position

    def estimate(train, when):
        if train.trainno == "6581":
            return (39.0, -75.0, 0.0)
        if train.trainno == "6583":
            return (39.0 + (8689 / 111_320), -75.0, 0.0)
        return original(train, when)

    R.estimate_position = estimate
    try:
        here = train(
            "6581",
            40.24278,
            -75.285,
            0,
            line="Lansdale/Doylestown",
            current="North Wales",
            nxt="Pennbrook",
        )
        other = train(
            "6583",
            40.24278,
            -75.285,
            0,
            line="Lansdale/Doylestown",
            current="North Wales",
            nxt="Pennbrook",
        )
        wrong = train(
            "7284",
            phone_lat,
            phone_lon - 0.12,
            108,
            dest="Norristown",
            line="Manayunk/Norristown",
            current="",
            nxt="",
        )
        samples = []
        for index in (0, 1):
            ts = 1_000.0 + index * 30
            samples.append(
                {
                    "fix": R.Fix(phone_lat, phone_lon, 16, 51 * 0.44704, 0, ts),
                    "trains": [here, other, wrong],
                    "trains_ts": ts - 0.7,
                    "now": ts,
                }
            )
        result = R.replay_fixes(
            samples,
            need_matches=2,
            radius_m=300,
            min_speed_mps=5,
            preferred_line="Lansdale/Doylestown",
        )
    finally:
        R.estimate_position = original
    assert result["riding"] is True
    assert result["train"] == "6581"
    assert result["position_source"] == "estimated"
    assert result["confidence"] == "estimated"
    assert result["steps"][0]["riding"] is False
    assert all(step["train"] != "7284" for step in result["steps"] if step["riding"])
    row = next(item for item in result["candidates"] if item["train"] == "6581")
    assert row["stale_gps"] is True
    assert row["position_source"] == "estimated"
    assert row["stale_reason"] == "station_mismatch"
    blocked = next(item for item in result["candidates"] if item["train"] == "7284")
    assert blocked["heading_diff"] == 108
    assert blocked["last_reject_reason"] == "heading"

