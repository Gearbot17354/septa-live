"""Replay TrainView snapshots plus a CSV of fixes.

CSV columns: ts,lat,lon,acc_m,speed_mps,course
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "ride.py"
    spec = importlib.util.spec_from_file_location("septa_ride", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["septa_ride"] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trainview", type=Path, default=Path(__file__).parent / "fixtures" / "tv_1.json")
    parser.add_argument("--fixes", type=Path, default=None)
    parser.add_argument("--matches", type=int, default=2)
    args = parser.parse_args()
    ride = _load()
    trains = ride.parse_trainview(json.loads(args.trainview.read_text()))
    matcher = ride.RideMatcher(need_matches=args.matches, min_speed_mps=5)
    if args.fixes is None:
        print(f"{len(trains)} trains in {args.trainview.name}; pass --fixes to replay")
        return
    with args.fixes.open() as handle:
        for row in csv.DictReader(handle):
            sample = ride.Fix(
                float(row["lat"]),
                float(row["lon"]),
                float(row.get("acc_m") or 10),
                float(row["speed_mps"]) if row.get("speed_mps") not in (None, "") else None,
                float(row["course"]) if row.get("course") not in (None, "") else None,
                float(row["ts"]),
            )
            event = matcher.update(sample, trains, sample.ts)
            state = matcher.payload()
            print(
                f"t={sample.ts:.0f} riding={state['riding']} train={state['train']} "
                f"conf={state['confidence']} event={event.kind if event else '-'}"
            )


if __name__ == "__main__":
    main()
