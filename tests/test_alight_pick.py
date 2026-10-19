"""A stop chosen during the ride, and names that are not spelled the same. No network and no Home Assistant."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER = [
    "North A",
    "Middle B",
    "Center One Station",
    "Center Two Station",
    "Gray 30th St Station",
    "Medical Center Station",
    "South End",
]
CURRENT = "Middle B"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = _load("septa_live_alight_pick", "ride.py")
T = _load("septa_live_alight_trips", "trips.py")


def _rows():
    names = ORDER[ORDER.index(CURRENT) + 1 :]
    rows = []
    for index, name in enumerate(names):
        minute = 20 + index * 5
        rows.append(
            {
                "station": name,
                "sched": f"08:{minute:02d}",
                "est": f"08:{minute + 4:02d}",
                "line": "AAA",
                "est_source": "delay",
            }
        )
    return rows


def _train(current, dest="South End"):
    return R.Train(
        trainno="100",
        lat=40.0,
        lon=-75.0,
        heading=0,
        dest=dest,
        line="Lansdale/Doylestown",
        service="LOCAL",
        currentstop=current,
        nextstop="",
        late=1,
        consist=["1"],
    )


def _fix(ts):
    return R.Fix(40.0, -75.0, 8, 20, 0, ts)


def test_a_select_changed_after_boarding_beats_the_plan():
    name, source, checked = R.alight_plan(
        ORDER,
        CURRENT,
        expected={"destination": "Center Two"},
        select="Medical Center",
        select_explicit=True,
    )
    assert name == "Medical Center Station" and source == "select"
    assert checked[0]["explicit"] is True


def test_an_older_select_does_not_override_the_plan():
    name, source, checked = R.alight_plan(
        ORDER,
        CURRENT,
        expected={"destination": "Center Two"},
        select="Medical Center",
        select_explicit=False,
        select_at=100,
        boarded_ts=1000,
    )
    assert name == "Center Two Station" and source == "planned"
    select = next(row for row in checked if row["source"] == "select")
    assert select["explicit"] is False
    assert R.choice_is_explicit(1000 - R.EXPLICIT_DEST_GRACE_S, 1000) is True
    assert R.choice_is_explicit(1000 - R.EXPLICIT_DEST_GRACE_S - 1, 1000) is False


def test_set_destination_during_the_ride_beats_select_and_plan():
    planned = {"destination": "Center Two"}
    name, source, _checked = R.alight_plan(
        ORDER,
        CURRENT,
        expected=planned,
        service="Gray 30th St",
        service_explicit=True,
        select="Medical Center",
        select_explicit=True,
    )
    assert name == "Gray 30th St Station" and source == "service"
    fallen, fallen_source, _checked = R.alight_plan(
        ORDER,
        CURRENT,
        expected=planned,
        service=None,
        select="Medical Center",
        select_explicit=True,
    )
    assert fallen == "Medical Center Station" and fallen_source == "select"
    station, at = R.dest_parts("Center Two Station")
    assert station == "Center Two Station" and at is None
    station, at = R.dest_parts({"station": "Medical Center", "at": 50})
    assert station == "Medical Center" and at == 50


def test_auto_and_a_stop_behind_the_train_fall_through_to_the_plan():
    auto, source, checked = R.alight_plan(
        ORDER,
        CURRENT,
        expected={"destination": "Center Two"},
        select="Auto",
        select_explicit=True,
    )
    assert auto == "Center Two Station" and source == "planned"
    assert checked[0]["result"] == "auto"
    behind, source, checked = R.alight_plan(
        ORDER,
        CURRENT,
        expected={"destination": "Center Two"},
        select="North A",
        select_explicit=True,
    )
    assert behind == "Center Two Station" and source == "planned"
    assert checked[0]["source"] == "select" and checked[0]["result"] == "behind"


def test_station_names_match_when_the_shorter_one_is_unique():
    assert T.match_in(ORDER, "30th Street") == "Gray 30th St Station"
    assert T.same_station("30th Street", "Gray 30th St Station", ORDER)
    assert T.match_in(ORDER, "Medical Center") == "Medical Center Station"
    fern = ["Fern Rock Transit Center", "Temple University"]
    assert T.match_in(fern, "Fern Rock T C") == "Fern Rock Transit Center"
    ninth = ["9th St Lansdale", "Fort Washington"]
    assert T.match_in(ninth, "9TH Street Lansdale") == "9th St Lansdale"
    both = ["30th Street", "Gray 30th Street"]
    assert T.match_in(both, "30th") is None
    centers = ["North Center", "South Center"]
    assert T.match_in(centers, "Center") is None
    assert T.match_in(ORDER, "Street") is None
    assert T.same_station("30th Street", "Gray 30th St Station") is True
    assert T.same_station("Plaza Stop", "University Plaza Stop", ["University Plaza Stop"]) is True
    assert T.same_station("Plaza Stop", "University Plaza Stop") is False


def test_remaining_stops_keep_the_later_stops_and_mark_the_alight_stop():
    marked = R.finish_remaining(_rows(), "Medical Center")
    assert [row["station"] for row in marked["rows"]] == ORDER[ORDER.index(CURRENT) + 1 :]
    flagged = [row for row in marked["rows"] if row["is_alight"]]
    assert len(flagged) == 1 and flagged[0]["station"] == "Medical Center Station"
    assert marked["alight_index"] == 3
    assert marked["stops_to_alight"] == 4
    assert marked["alight_est"] == flagged[0]["est"]
    assert flagged[0]["est_source"] == "delay"


def test_the_terminal_is_the_trains_last_stop_and_the_ride_still_ends_at_alight():
    matcher = R.RideMatcher(need_matches=1, min_speed_mps=5, radius_m=200)
    matcher.update(_fix(0), [_train("Middle B")], 0)
    assert matcher.riding is True
    matcher.alight_station = "Medical Center Station"
    matcher.remaining_stops = _rows()
    mid = _train("Medical Center Station")
    south = _train("South End")
    assert matcher._is_terminal(mid) is False
    assert matcher._is_terminal(south) is True
    held = matcher.update(_fix(20), [mid], 20)
    assert held is None and matcher.riding is True
    event = matcher.update(_fix(40), [mid], 40)
    assert event is not None and event.payload["reason"] == "terminal"


def test_no_alight_station_leaves_the_list_unmarked():
    marked = R.finish_remaining(_rows(), None)
    assert marked["alight_index"] is None and marked["stops_to_alight"] is None
    assert all(row["is_alight"] is False for row in marked["rows"])
    assert [row["station"] for row in marked["rows"]] == [row["station"] for row in _rows()]


def test_changing_the_select_while_riding_asks_for_a_republish():
    assert R.should_republish_destination(True, "Center Two", "Medical Center") is True
    assert R.should_republish_destination(True, "Auto", "Center Two") is True
    assert R.should_republish_destination(True, "Medical Center", "Medical Center") is False
    assert R.should_republish_destination(False, "Center Two", "Medical Center") is False
