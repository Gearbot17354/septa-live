"""Regional Rail station picker. Names come from the timetable, not a blocklist."""

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


D = _load("septa_dynamic_picker", "dynamic.py")
C = _load("septa_const_picker", "const.py")


def _schedule(names, line="NORTH"):
    return {"stations": {name: {"S": [{"line": line, "n": "100", "t": "09:00"}]} for name in names}}


def test_options_are_the_schedule_and_not_other_modes():
    shared = next(iter(C.METRO_STATIONS))
    schedule = _schedule(["North End", "Hub", shared])
    options = D.rail_picker_options(schedule, list(C.STATIONS))
    rail = {name.casefold() for name in D.rail_station_names(schedule)}
    other = {name.casefold() for name in list(C.METRO_STATIONS) + list(C.TROLLEY_STATIONS)} - rail
    assert {name.casefold() for name in options} == rail
    assert not ({name.casefold() for name in options} & other)
    assert any(name.casefold() == shared.casefold() for name in options)


def test_a_shared_hub_stays_when_the_timetable_has_it():
    shared = next(iter(C.METRO_STATIONS))
    options = D.rail_picker_options(_schedule([shared]), [])
    assert shared in options or any(name.casefold() == shared.casefold() for name in options)


def test_submit_normalises_a_rail_name_and_rejects_other_modes():
    schedule = _schedule(["North End", "Hub"])
    names = D.rail_station_names(schedule)
    metro_only = next(
        name
        for name in list(C.METRO_STATIONS) + list(C.TROLLEY_STATIONS)
        if name.casefold() not in {item.casefold() for item in names}
    )
    assert D.canonical_rail_station(metro_only, names) is None
    canonical = names[0]
    assert D.canonical_rail_station(f"  {canonical.upper()}  ", names) == canonical


def test_a_new_schedule_changes_the_list():
    first = D.rail_picker_options(_schedule(["North End"]), [])
    second = D.rail_picker_options(_schedule(["Hub", "South End"]), [])
    assert first != second
    assert second == ["Hub", "South End"]


def test_a_legacy_other_mode_value_is_reported_and_not_rewritten():
    schedule = _schedule(["North End"])
    metro_only = next(name for name in C.METRO_STATIONS if name.casefold() != "north end")
    saved = [metro_only, "North End"]
    bad = D.legacy_non_rail(saved, schedule, list(C.METRO_STATIONS), list(C.TROLLEY_STATIONS))
    assert metro_only in bad
    assert "North End" not in bad
    assert saved == [metro_only, "North End"]


def test_a_renamed_gtfs_station_matches_every_old_spelling():
    bundled = ["30th Street Station", "Fern Rock Transportation Center", "Lansdale"]
    refreshed = ["Gray 30th St Station", "Fern Rock Transit Center", "Lansdale"]
    asked = [
        "30th Street",
        "30th St",
        "30th Street Station",
        "Gray 30th Street",
        "William H. Gray III 30th Street Station",
        "Gray 30th St Station",
    ]
    for names, expected in ((bundled, "30th Street Station"), (refreshed, "Gray 30th St Station")):
        for text in asked:
            assert D.match_station(text, names) == expected
    assert D.match_station("Fern Rock Transit Center", bundled) == "Fern Rock Transportation Center"
    assert D.match_station("Fern Rock Transportation Center", refreshed) == "Fern Rock Transit Center"
    assert D.match_station("Jefferson", ["North End"]) is None
    assert D.match_station("End", ["North End", "South End"]) is None
    assert D.short_station("Gray 30th St Station") == "Gray 30th Street"


def test_version_lookup_does_not_open_the_manifest():
    text = (ROOT / "const.py").read_text()
    init = (ROOT / "__init__.py").read_text()
    assert "manifest.json" not in text
    assert "read_text" not in text
    assert "async_get_integration" in init
    assert "source.exists()" not in init
    assert "septa_live/stations" in (ROOT / "schema.py").read_text()
