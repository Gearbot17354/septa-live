"""Route lines from a GTFS zip. No Home Assistant and no network.

Shapes are parsed when the timetable refreshes. Simplifying a line is cached
per trip so a later update only moves the passed/remaining flags.
"""

from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path

try:
    from .schedule import _csv, _texts, write_schedule_file
except ImportError:  # loaded by file path in unit tests
    import importlib.util

    _spec = importlib.util.spec_from_file_location("septa_schedule_shapes", Path(__file__).with_name("schedule.py"))
    _sched = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_sched)
    _csv = _sched._csv
    _texts = _sched._texts
    write_schedule_file = _sched.write_schedule_file

MAX_SHAPE_POINTS = 200
ATTR_BYTE_LIMIT = 16384
_THIN_AT = 4000
_THIN_TO = 2000

ROUTE_KEYS = (
    "route_shape",
    "route_color",
    "route_text_color",
    "stops",
    "alight_station",
    "route_shape_simplified",
    "route_shape_points",
)


def _color(value: object) -> str | None:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        text = "".join(ch * 2 for ch in text)
    if len(text) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return "#" + text.upper()
    return None


def _round_pt(lat: float, lon: float, digits: int = 5) -> list[float]:
    return [round(float(lat), digits), round(float(lon), digits)]


def _num(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def _segment_m(point: list[float], start: list[float], end: list[float]) -> float:
    lat0 = start[0]
    scale = 111320.0 * max(0.2, math.cos(math.radians(lat0)))

    def xy(item: list[float]) -> tuple[float, float]:
        return ((item[1] - start[1]) * scale, (item[0] - start[0]) * 110540.0)

    px, py = xy(point)
    bx, by = xy(end)
    span = bx * bx + by * by
    if span <= 0:
        return math.hypot(px, py)
    tee = max(0.0, min(1.0, (px * bx + py * by) / span))
    return math.hypot(px - tee * bx, py - tee * by)


def _nearest_index(points: list[list[float]], lat: float, lon: float) -> int:
    best = 0
    best_d = None
    here = [lat, lon]
    for index, point in enumerate(points):
        dist = haversine_m(here[0], here[1], point[0], point[1])
        if best_d is None or dist < best_d:
            best = index
            best_d = dist
    return best


def orient_and_clip(points: list[list[float]], stops: list[dict]) -> list[list[float]]:
    """Trip order, clipped to the first and last stop. Reverse when the shape runs the other way."""
    if len(points) < 2 or len(stops) < 1:
        return [list(point) for point in points]
    first = stops[0]
    last = stops[-1]
    ordered = [list(point) for point in points]
    start = _nearest_index(ordered, first["lat"], first["lon"])
    end = _nearest_index(ordered, last["lat"], last["lon"])
    if end < start:
        ordered.reverse()
        start = _nearest_index(ordered, first["lat"], first["lon"])
        end = _nearest_index(ordered, last["lat"], last["lon"])
    if end < start:
        return ordered
    return ordered[start : end + 1]


def _thin(points: list[list[float]], keep: set[int], limit: int) -> tuple[list[list[float]], set[int]]:
    if len(points) <= limit:
        return points, set(keep)
    chosen = {index for index in keep if 0 <= index < len(points)}
    chosen.add(0)
    chosen.add(len(points) - 1)
    step = len(points) / float(limit)
    cursor = 0.0
    while len(chosen) < limit and cursor < len(points):
        chosen.add(min(len(points) - 1, int(cursor)))
        cursor += step
    order = sorted(chosen)
    remap = {old: new for new, old in enumerate(order)}
    return [points[index] for index in order], {remap[index] for index in keep if index in remap}


def douglas_peucker(points: list[list[float]], epsilon_m: float, keep: set[int]) -> list[int]:
    """Indexes to keep. Endpoints and `keep` always stay. Deviation stays within epsilon."""
    count = len(points)
    if count == 0:
        return []
    marked = [False] * count
    marked[0] = True
    marked[count - 1] = True
    for index in keep:
        if 0 <= index < count:
            marked[index] = True
    stack = [(0, count - 1)]
    while stack:
        left, right = stack.pop()
        if right <= left + 1:
            continue
        farthest = None
        farthest_d = -1.0
        forced = []
        for index in range(left + 1, right):
            dist = _segment_m(points[index], points[left], points[right])
            if dist > farthest_d:
                farthest = index
                farthest_d = dist
            if marked[index]:
                forced.append(index)
        if farthest is None:
            continue
        if farthest_d > epsilon_m:
            marked[farthest] = True
            stack.append((left, farthest))
            stack.append((farthest, right))
        elif forced:
            pivot = max(forced, key=lambda index: _segment_m(points[index], points[left], points[right]))
            stack.append((left, pivot))
            stack.append((pivot, right))
    return [index for index, flag in enumerate(marked) if flag]


def max_deviation_m(original: list[list[float]], simplified: list[list[float]]) -> float:
    if not original or len(simplified) < 2:
        return 0.0
    worst = 0.0
    for point in original:
        nearest = min(_segment_m(point, simplified[index], simplified[index + 1]) for index in range(len(simplified) - 1))
        if nearest > worst:
            worst = nearest
    return worst


def _keep_indexes(points: list[list[float]], stops: list[dict]) -> set[int]:
    keep = {0, len(points) - 1} if points else set()
    for stop in stops:
        if stop.get("lat") is None or stop.get("lon") is None or not points:
            continue
        keep.add(_nearest_index(points, stop["lat"], stop["lon"]))
    return keep


def simplify_shape(points: list[list[float]], stops: list[dict], max_points: int = MAX_SHAPE_POINTS) -> dict:
    """Douglas–Peucker, raising the tolerance until the line is short enough."""
    clipped = orient_and_clip(points, stops)
    if len(clipped) <= 2:
        return {"points": clipped, "epsilon_m": 0.0, "deviation_m": 0.0}
    keep = _keep_indexes(clipped, stops)
    if len(clipped) > _THIN_AT:
        clipped, keep = _thin(clipped, keep, _THIN_TO)
        keep = _keep_indexes(clipped, stops) | keep
    epsilon = 1.0
    chosen = list(range(len(clipped)))
    for _ in range(24):
        chosen = douglas_peucker(clipped, epsilon, keep)
        if len(chosen) <= max_points:
            break
        epsilon *= 1.8
    simplified = [clipped[index] for index in chosen]
    return {
        "points": simplified,
        "epsilon_m": epsilon if len(clipped) > max_points or len(simplified) < len(clipped) else 0.0,
        "deviation_m": max_deviation_m(clipped, simplified) if len(simplified) >= 2 else 0.0,
        "source_count": len(clipped),
    }


def _key_name(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _stop_index(stops: list[dict], name: object) -> int | None:
    want = _key_name(name)
    if not want:
        return None
    for index, stop in enumerate(stops):
        if _key_name(stop.get("name")) == want:
            return index
    return None


def mark_stops(stops: list[dict], next_stop: object, alight: object, boarded: object) -> list[dict]:
    """Passed stops are those before the live next stop. Remaining is the rest."""
    nxt = _stop_index(stops, next_stop)
    board = _stop_index(stops, boarded)
    alight_key = _key_name(alight)
    if nxt is None:
        nxt = 0
    out = []
    for index, stop in enumerate(stops):
        passed = index < nxt
        row = {
            "name": stop.get("name"),
            "lat": stop.get("lat"),
            "lon": stop.get("lon"),
            "passed": passed,
            "remaining": not passed,
            "alight": bool(alight_key) and _key_name(stop.get("name")) == alight_key,
        }
        if board is not None and index < board:
            row["before_board"] = True
        out.append(row)
    return out


def _size(payload: dict) -> int:
    return len(json.dumps(payload))


def _pack(points: list[list[float]], stops: list[dict], color, text_color, alight, digits: int, drop_before: bool) -> dict:
    shaped = [_round_pt(point[0], point[1], digits) for point in points]
    rows = []
    for stop in stops:
        if drop_before and stop.get("before_board"):
            continue
        row = dict(stop)
        if row.get("lat") is not None:
            row["lat"] = round(float(row["lat"]), digits)
        if row.get("lon") is not None:
            row["lon"] = round(float(row["lon"]), digits)
        rows.append(row)
    return {
        "route_shape": shaped,
        "route_color": color,
        "route_text_color": text_color,
        "stops": rows,
        "alight_station": alight,
        "route_shape_simplified": True,
        "route_shape_points": len(shaped),
    }


def fit_route(
    points: list[list[float]],
    stops: list[dict],
    *,
    color,
    text_color,
    alight,
    next_stop,
    boarded,
    byte_limit: int = ATTR_BYTE_LIMIT,
) -> tuple[dict, dict]:
    """Stay under the recorder warning. Tighter line, then 4 decimals, then drop pre-board stops."""
    marked = mark_stops(stops, next_stop, alight, boarded)
    limit = max(32, int(byte_limit))
    budgets = [MAX_SHAPE_POINTS, 120, 80, 40, 24, 12, 8]
    stages = [(budget, 5, False) for budget in budgets]
    stages += [(budget, 4, False) for budget in budgets]
    stages += [(budget, 4, True) for budget in budgets]
    best = _pack(points[:1] or points, marked, color, text_color, alight, 5, False)
    meta = {"digits": 5, "drop": False}
    for budget, digits, drop_before in stages:
        simplified = simplify_shape(points, stops, budget)["points"]
        packed = _pack(simplified, marked, color, text_color, alight, digits, drop_before)
        best = packed
        meta = {"digits": digits, "drop": drop_before, "points": packed["route_shape"]}
        if _size(packed) < limit:
            return packed, meta
    return best, meta


def cleared_route() -> dict:
    return {
        "route_shape": None,
        "route_color": None,
        "route_text_color": None,
        "stops": None,
        "route_shape_simplified": None,
        "route_shape_points": None,
    }


def _memo_key(shape_id: str, stops: list[dict]) -> tuple:
    first = "" if not stops else str(stops[0].get("name") or "")
    last = "" if not stops else str(stops[-1].get("name") or "")
    return (shape_id, first, last)


def _from_memo(cached: dict, stops: list[dict], color, text_color, alight, next_stop, boarded) -> dict:
    marked = mark_stops(stops, next_stop, alight, boarded)
    return _pack(cached["points"], marked, color, text_color, alight, int(cached.get("digits") or 5), bool(cached.get("drop")))


def attach_route(data: dict | None, cache: dict | None, memo: dict | None = None, byte_limit: int = ATTR_BYTE_LIMIT) -> dict:
    """Route attributes for an active ride. A later update reuses the simplified line."""
    if not isinstance(data, dict) or not data.get("riding"):
        return cleared_route()
    number = str(data.get("train") or "").strip()
    trains = (cache or {}).get("trains") if isinstance(cache, dict) else None
    info = trains.get(number) if isinstance(trains, dict) else None
    if not info:
        return cleared_route()
    shape_id = str(info.get("shape_id") or "")
    points = ((cache or {}).get("shapes") or {}).get(shape_id) or []
    if len(points) < 2:
        return cleared_route()
    stops = [dict(stop) for stop in info.get("stops") or [] if isinstance(stop, dict)]
    route_id = info.get("route_id")
    route = ((cache or {}).get("routes") or {}).get(route_id) or {}
    alight = data.get("alight_station") or data.get("final_destination") or None
    if isinstance(alight, str):
        alight = alight.strip() or None
    key = _memo_key(shape_id, stops) + (int(byte_limit),)
    store = memo if isinstance(memo, dict) else None
    color = route.get("color")
    text_color = route.get("text_color")
    if store is not None and isinstance(store.get(key), dict) and store[key].get("points"):
        return _from_memo(store[key], stops, color, text_color, alight, data.get("next_stop"), data.get("origin"))
    _fitted, meta = fit_route(
        points,
        stops,
        color=color,
        text_color=text_color,
        alight=alight,
        next_stop=data.get("next_stop"),
        boarded=data.get("origin"),
        byte_limit=byte_limit,
    )
    if store is not None:
        store[key] = meta
    return _fitted


def route_query(cache: dict | None, train: object = None, row: dict | None = None) -> dict:
    """Full-resolution line for a card. `not_found` when that train has no shape."""
    number = None
    if isinstance(train, bool):
        number = None
    elif isinstance(train, int):
        number = str(train)
    elif isinstance(train, float) and train.is_integer():
        number = str(int(train))
    elif train not in (None, ""):
        number = str(train).strip() or None
    if not number and isinstance(row, dict) and row.get("riding"):
        number = str(row.get("train") or "").strip() or None
    trains = (cache or {}).get("trains") if isinstance(cache, dict) else None
    info = trains.get(number) if isinstance(trains, dict) and number else None
    if not info:
        return {"error": "not_found"}
    shape = ((cache or {}).get("shapes") or {}).get(info.get("shape_id")) or []
    if len(shape) < 2:
        return {"error": "not_found"}
    route = ((cache or {}).get("routes") or {}).get(info.get("route_id")) or {}
    detail = row if isinstance(row, dict) and str(row.get("train") or "") == number else {}
    return {
        "train": number,
        "route_id": info.get("route_id"),
        "route_color": route.get("color"),
        "shape": shape,
        "stops": mark_stops(info.get("stops") or [], detail.get("next_stop"), detail.get("alight_station") or detail.get("final_destination"), detail.get("origin")),
    }


def _declared(text: str) -> bool:
    return len([line for line in str(text or "").splitlines() if line.strip()]) > 1


def _shape_points(text: str) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for row in _csv(text):
        sid = str(row.get("shape_id") or "").strip()
        lat = _num(row.get("shape_pt_lat"))
        lon = _num(row.get("shape_pt_lon"))
        if not sid or lat is None or lon is None:
            continue
        seq = _num(row.get("shape_pt_sequence"))
        grouped.setdefault(sid, []).append((0 if seq is None else seq, _round_pt(lat, lon)))
    return {sid: [point for _, point in sorted(rows, key=lambda item: item[0])] for sid, rows in grouped.items() if rows}


def _stop_table(text: str) -> dict[str, dict]:
    found = {}
    for row in _csv(text):
        sid = str(row.get("stop_id") or "").strip()
        if not sid:
            continue
        lat = _num(row.get("stop_lat"))
        lon = _num(row.get("stop_lon"))
        found[sid] = {
            "name": str(row.get("stop_name") or sid).strip(),
            "lat": None if lat is None else round(lat, 5),
            "lon": None if lon is None else round(lon, 5),
        }
    return found


def _routes(text: str) -> dict:
    found = {}
    for row in _csv(text):
        rid = str(row.get("route_id") or "").strip()
        if not rid:
            continue
        found[rid] = {"color": _color(row.get("route_color")), "text_color": _color(row.get("route_text_color"))}
    return found


def build_shape_cache(zip_bytes: bytes) -> dict:
    """GTFS zip → `{shapes, trains, routes}`. No shapes file falls back to stop-to-stop lines."""
    if not isinstance(zip_bytes, (bytes, bytearray)) or not zip_bytes:
        raise ValueError("shapes")
    try:
        files = _texts(bytes(zip_bytes))
    except (zipfile.BadZipFile, ValueError) as err:
        raise ValueError("shapes") from err
    if "stops" not in files or "trips" not in files or "stop_times" not in files:
        raise ValueError("shapes")
    raw_shapes = files.get("shapes") or ""
    if _declared(raw_shapes):
        shapes = _shape_points(raw_shapes)
        if not shapes:
            raise ValueError("shapes")
    else:
        shapes = {}
    stops = _stop_table(files.get("stops") or "")
    trips = {str(row.get("trip_id") or ""): row for row in _csv(files.get("trips") or "")}
    order: dict[str, list] = {}
    for row in _csv(files.get("stop_times") or ""):
        trip_id = str(row.get("trip_id") or "")
        stop = stops.get(str(row.get("stop_id") or ""))
        if not trip_id or not stop or stop.get("lat") is None:
            continue
        seq = _num(row.get("stop_sequence"))
        order.setdefault(trip_id, []).append((0 if seq is None else seq, dict(stop)))
    trains: dict[str, dict] = {}
    for trip_id, rows in order.items():
        trip = trips.get(trip_id) or {}
        number = str(trip.get("trip_short_name") or trip_id).strip()
        if not number:
            continue
        served = [item[1] for item in sorted(rows, key=lambda item: item[0])]
        shape_id = str(trip.get("shape_id") or "").strip()
        line = shapes.get(shape_id) if shape_id else None
        if not line or len(line) < 2:
            line = [[stop["lat"], stop["lon"]] for stop in served]
            if len(line) == 1:
                line = [line[0], line[0]]
            shape_id = f"stops:{number}"
            shapes[shape_id] = line
        if len(line) < 2:
            continue
        trains[number] = {"shape_id": shape_id, "route_id": str(trip.get("route_id") or ""), "stops": served}
    if not trains:
        raise ValueError("shapes")
    return {"shapes": shapes, "trains": trains, "routes": _routes(files.get("routes") or "")}


def _rider_match(row: dict, rider: object) -> bool:
    want = str(rider or "").strip().casefold()
    if not want or not isinstance(row, dict):
        return False
    for key in ("rider", "person"):
        if str(row.get(key) or "").strip().casefold() == want:
            return True
    return False


def _row_for_train(rows: list, train: object) -> dict | None:
    number = str(train).strip() if train not in (None, "") and not isinstance(train, bool) else ""
    if isinstance(train, float) and train.is_integer():
        number = str(int(train))
    elif isinstance(train, int) and not isinstance(train, bool):
        number = str(train)
    for row in rows or []:
        if isinstance(row, dict) and str(row.get("train") or "") == number and row.get("riding"):
            return row
    return None


def resolve_route(pairs, train: object = None, rider: object = None) -> dict:
    """Websocket result. A rider who is not on a train, or an unknown train, is `not_found`."""
    for cache, rows in pairs or []:
        rows = [row for row in (rows or []) if isinstance(row, dict)]
        if rider not in (None, ""):
            for row in rows:
                if _rider_match(row, rider) and row.get("riding"):
                    return route_query(cache, row.get("train"), row)
            continue
        if train not in (None, ""):
            hit = route_query(cache, train, _row_for_train(rows, train))
            if hit.get("error") != "not_found":
                return hit
            continue
        for row in rows:
            if row.get("riding") and row.get("train"):
                hit = route_query(cache, row.get("train"), row)
                if hit.get("error") != "not_found":
                    return hit
    return {"error": "not_found"}


def absorb_shapes(previous: dict | None, blob: bytes) -> tuple[dict | None, str | None]:
    """Keep the previous cache when this zip cannot be parsed. Schedules are untouched."""
    try:
        return build_shape_cache(blob), None
    except ValueError as err:
        return previous, str(err) or "shapes"


def read_shapes_file(path: Path | str) -> dict | None:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    data = raw.get("shapes_cache") if isinstance(raw.get("shapes_cache"), dict) else raw
    if not isinstance(data, dict) or not isinstance(data.get("trains"), dict):
        return None
    data.setdefault("shapes", {})
    data.setdefault("routes", {})
    return data


def write_shapes_file(path: Path | str, payload: dict) -> None:
    write_schedule_file(path, payload)
