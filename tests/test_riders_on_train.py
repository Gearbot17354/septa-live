"""Who is on a train. Synthetic riders only."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("septa_ride_riders", ROOT / "ride.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["septa_ride_riders"] = module
    spec.loader.exec_module(module)
    return module


R = _load()


def _row(rider, train, picture, name=None, riding=True):
    return {
        "rider": rider,
        "riding": riding,
        "train": train,
        "person": f"person.{rider}",
        "friendly_name_rider": name or rider.title(),
        "entity_picture": picture,
        "boarded_at": "2026-10-14T08:00:00-04:00",
        "origin": "North End",
        "destination": "Hub",
        "line": "NORTH",
        "next_stop": "Midway",
    }


def test_riders_on_the_same_train_are_sorted_with_pictures():
    rows = [
        _row("bravo", "100", "/api/bravo", "Bravo"),
        _row("alpha", "100", "/api/alpha", "Alpha"),
        _row("charlie", "200", "/api/charlie", "Charlie"),
    ]
    party = R.riders_on_train(rows, "100")
    assert [item["rider"] for item in party] == ["alpha", "bravo"]
    assert party[0]["entity_picture"] == "/api/alpha"
    assert party[0]["entity_id"] == "person.alpha"
    assert R.rider_pictures(party) == ["/api/alpha", "/api/bravo"]
    summary = R.riders_summary(rows)
    assert summary["trains"]["100"] == ["bravo", "alpha"]
    listed = next(item for item in summary["parties"] if item["train"] == "100")
    assert [item["name"] for item in listed["riders"]] == ["Alpha", "Bravo"]


def test_missing_picture_is_null_and_omitted_from_the_url_list():
    rows = [_row("alpha", "100", None, "Alpha")]
    party = R.riders_on_train(rows, "100")
    assert party[0]["entity_picture"] is None
    assert R.rider_pictures(party) == []


def test_a_new_picture_shows_up_on_the_next_call():
    first = R.riders_on_train([_row("alpha", "100", "/api/old")], "100")
    second = R.riders_on_train([_row("alpha", "100", "/api/new")], "100")
    assert first[0]["entity_picture"] == "/api/old"
    assert second[0]["entity_picture"] == "/api/new"


def test_a_finished_ride_drops_the_rider_and_an_empty_train():
    riding = [_row("alpha", "100", "/api/alpha"), _row("bravo", "100", None, "Bravo")]
    assert len(R.riders_on_train(riding, "100")) == 2
    done = [_row("alpha", "100", "/api/alpha", riding=False), _row("bravo", "200", None, "Bravo")]
    assert R.riders_on_train(done, "100") == []
    summary = R.riders_summary(done)
    assert "100" not in summary["trains"]
    assert all(item["train"] != "100" for item in summary["parties"])


def test_the_list_is_capped():
    rows = [_row(f"rider{i:02d}", "100", f"/api/{i}", f"Rider {i:02d}") for i in range(25)]
    party = R.riders_on_train(rows, "100")
    assert len(party) == 20
    assert party[0]["name"] == "Rider 00"


def test_my_train_lists_the_other_riders():
    rows = [
        _row("alpha", "100", "/api/alpha", "Alpha"),
        _row("bravo", "100", "/api/bravo", "Bravo"),
    ]
    assert [item["rider"] for item in R.companions(rows, "alpha", "100")] == ["bravo"]
