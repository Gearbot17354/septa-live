"""Map marker for the train a rider is on."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


T = _load("septa_tracker", "tracker.py")
R = _load("septa_ride_for_tracker", "ride.py")


def test_a_boarded_train_publishes_its_position():
    state = T.project_tracker(riding=True, latitude=40.1, longitude=-75.2, now=1_000, previous=None)
    assert state["available"] is True
    assert state["latitude"] == 40.1
    assert state["longitude"] == -75.2
    assert state["stale"] is False
    assert state["source"] == "trainview"
    assert state["location_accuracy"] == 100
    riders = R.riders_on_train(
        [
            {
                "rider": "alpha",
                "riding": True,
                "train": "100",
                "person": "person.alpha",
                "friendly_name_rider": "Alpha",
                "entity_picture": "/api/alpha",
                "destination": "Hub",
            }
        ],
        "100",
    )
    attrs = T.tracker_attributes(
        train="100",
        line="NORTH",
        next_stop="Midway",
        destination="Hub",
        delay_min=3,
        consist=["1"],
        last_update="2026-10-14T08:00:00-04:00",
        riders=riders,
        stale=False,
    )
    assert attrs["train"] == "100"
    assert attrs["riders"][0]["entity_picture"] == "/api/alpha"
    assert attrs["rider_pictures"] == ["/api/alpha"]
    assert T.tracker_icon("/api/alpha") == "mdi:train"


def test_a_new_fix_moves_the_marker():
    first = T.project_tracker(riding=True, latitude=40.0, longitude=-75.0, now=1_000, previous=None)
    second = T.project_tracker(
        riding=True,
        latitude=40.2,
        longitude=-75.1,
        now=1_030,
        previous=first["previous"],
    )
    assert (second["latitude"], second["longitude"]) == (40.2, -75.1)
    assert second["stale"] is False


def test_a_missing_fix_stays_then_drops():
    seen = T.project_tracker(riding=True, latitude=40.0, longitude=-75.0, now=1_000, previous=None)
    held = T.project_tracker(riding=True, latitude=None, longitude=None, now=1_000 + 299, previous=seen["previous"])
    assert held["stale"] is True
    assert held["available"] is True
    assert held["latitude"] == 40.0
    gone = T.project_tracker(riding=True, latitude=None, longitude=None, now=1_000 + 301, previous=seen["previous"])
    assert gone["available"] is False
    assert gone["latitude"] is None


def test_ride_end_clears_the_point_and_reload_keeps_one_entity():
    seen = T.project_tracker(riding=True, latitude=40.0, longitude=-75.0, now=1_000, previous=None)
    ended = T.project_tracker(riding=False, latitude=40.0, longitude=-75.0, now=1_100, previous=seen["previous"])
    assert ended["available"] is False
    assert ended["latitude"] is None
    assert ended["previous"] is None
    entry = "entry1"
    slugs = ["alpha", "bravo"]
    ids = [item["unique_id"] for item in T.tracker_entities(entry, slugs)]
    assert ids == ["entry1_alpha_train", "entry1_bravo_train"]
    assert [item["entity_id"] for item in T.tracker_entities(entry, slugs)] == [
        "device_tracker.septa_alpha_train",
        "device_tracker.septa_bravo_train",
    ]
    registry = ids + ["entry1_old_train"]
    assert T.leftover_trackers(entry, slugs, registry) == ["entry1_old_train"]
    assert T.leftover_trackers(entry, slugs, ids) == []


def test_no_picture_uses_the_train_icon():
    assert T.tracker_icon(None) == "mdi:train"
    attrs = T.tracker_attributes(
        train="100",
        line=None,
        next_stop=None,
        destination=None,
        delay_min=None,
        consist=None,
        last_update=None,
        riders=[{"rider": "alpha", "name": "Alpha", "entity_picture": None}],
        stale=False,
    )
    assert attrs["rider_pictures"] == []
    assert attrs["source"] == "trainview"
