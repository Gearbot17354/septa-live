"""Route lines from a GTFS zip. No Home Assistant and no network.

Shapes are parsed when the timetable refreshes. Simplifying a line is cached
per trip so a later update only moves the passed/remaining flags.
"""

from __future__ import annotations

import json
import math
import zipfile
from datetime import date
from pathlib import Path

SHAPES_FORMAT = 2

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


_LOOSE = None
_MATCH = None
_SAME = None


def _bind_names() -> None:
    global _LOOSE, _MATCH, _SAME
    if _LOOSE is not None:
        return
    try:
        from .trips import loose_key, match_in, same_station
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location("septa_trips_loose", Path(__file__).with_name("trips.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loose_key = module.loose_key
        match_in = module.match_in
        same_station = module.same_station
    _LOOSE = loose_key
    _MATCH = match_in
    _SAME = same_station


def _loose(value: object) -> str:
    _bind_names()
    return _LOOSE(value)


def _match_name(order: list, name: object) -> str | None:
    _bind_names()
    if _MATCH is None:
        return None
    return _MATCH(order, name)


def _same_stop(left: object, right: object) -> bool:
    _bind_names()
    if _SAME is None:
        return bool(_key_name(left)) and _key_name(left) == _key_name(right)
    return _SAME(left, right)


def _key_name(value: object) -> str:
    return _loose(value) or " ".join(tok for tok in str(value or "").casefold().split() if tok and tok != "station")


def _stop_index(stops: list[dict], name: object) -> int | None:
    labels = [stop.get("name") for stop in stops or []]
    found = _match_name(labels, name)
    if not found:
        return None
    for index, stop in enumerate(stops):
        if stop.get("name") == found:
            return index
    return None


def _nearest_stop_index(stops: list[dict], here: tuple | None) -> int | None:
    if not here or len(here) < 2:
        return None
    best = None
    best_d = None
    for index, stop in enumerate(stops or []):
        if stop.get("lat") is None or stop.get("lon") is None:
            continue
        dist = haversine_m(float(here[0]), float(here[1]), float(stop["lat"]), float(stop["lon"]))
        if best_d is None or dist < best_d:
            best = index
            best_d = dist
    return best


def mark_stops(stops: list[dict], next_stop: object, alight: object, boarded: object, here: tuple | None = None) -> list[dict]:
    """Passed stops are those before the live next stop. Remaining is the rest."""
    nxt = _stop_index(stops, next_stop)
    board = _stop_index(stops, boarded)
    names = [stop.get("name") for stop in stops or []]
    alight_name = _match_name(names, alight)
    if nxt is None and here is not None:
        nxt = _nearest_stop_index(stops, here)
    if nxt is None:
        nxt = 0
    out = []
    for index, stop in enumerate(stops):
        passed = index < nxt
        row = {
            "name": stop.get("name"),
            "lat": stop.get("lat"),
            "lon": stop.get("lon"),
            "sched": stop.get("sched"),
            "est": stop.get("est") or stop.get("sched"),
            "passed": passed,
            "remaining": not passed,
            "alight": bool(alight_name) and stop.get("name") == alight_name,
        }
        if board is not None and index < board:
            row["before_board"] = True
        out.append(row)
    return out


def _size(payload: dict) -> int:
    return len(json.dumps(payload))


def _pack(points: list[list[float]], stops: list[dict], color, text_color, alight, digits: int, drop_before: bool, source: str | None) -> dict:
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
        "route_shape_source": source,
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
    source: str | None = "gtfs",
    here: tuple | None = None,
) -> tuple[dict, dict]:
    """Stay under the recorder warning. Tighter line, then 4 decimals, then drop pre-board stops."""
    marked = mark_stops(stops, next_stop, alight, boarded, here)
    limit = max(32, int(byte_limit))
    budgets = [MAX_SHAPE_POINTS, 120, 80, 40, 24, 12, 8]
    stages = [(budget, 5, False) for budget in budgets]
    stages += [(budget, 4, False) for budget in budgets]
    stages += [(budget, 4, True) for budget in budgets]
    best = _pack(points[:1] or points, marked, color, text_color, alight, 5, False, source)
    meta = {"digits": 5, "drop": False, "source": source}
    for budget, digits, drop_before in stages:
        simplified = simplify_shape(points, stops, budget)["points"]
        packed = _pack(simplified, marked, color, text_color, alight, digits, drop_before, source)
        best = packed
        meta = {"digits": digits, "drop": drop_before, "points": packed["route_shape"], "source": source}
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
        "route_shape_source": None,
    }


def _memo_key(shape_id: str, stops: list[dict]) -> tuple:
    first = "" if not stops else str(stops[0].get("name") or "")
    last = "" if not stops else str(stops[-1].get("name") or "")
    return (shape_id, first, last)


def _from_memo(cached: dict, stops: list[dict], color, text_color, alight, next_stop, boarded, here: tuple | None = None) -> dict:
    marked = mark_stops(stops, next_stop, alight, boarded, here)
    return _pack(
        cached["points"],
        marked,
        color,
        text_color,
        alight,
        int(cached.get("digits") or 5),
        bool(cached.get("drop")),
        cached.get("source") or "gtfs",
    )


_MISSED_SHAPE: set[tuple] = set()


def _bare_number(value: object) -> str:
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits or text


def line_title(code: object, routes: dict | None = None, names: dict | None = None) -> str | None:
    """Full line name. A route code uses routes.txt, then the same table TrainView uses."""
    text = str(code or "").strip()
    if not text:
        return None
    table = routes if isinstance(routes, dict) else {}
    route = table.get(text) or table.get(text.upper()) or {}
    if isinstance(route, dict) and route.get("name"):
        return str(route["name"])
    known = names if isinstance(names, dict) else {}
    if text in known and known[text]:
        return str(known[text])
    if text.upper() in known and known[text.upper()]:
        return str(known[text.upper()])
    return text


def note_missing_shape(train: object, reason: str, day: object) -> None:
    key = (str(train or ""), str(day or ""))
    if not key[0] or key in _MISSED_SHAPE:
        return
    _MISSED_SHAPE.add(key)
    import logging

    logging.getLogger(__name__).warning("SEPTA route shape for train %s used stop coordinates: %s", train, reason)


def _overlay_times(stops: list[dict], rows: list | None) -> list[dict]:
    labels = []
    by = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("station") or row.get("name") or "")
        labels.append(label)
        by[label] = row
    out = []
    for stop in stops:
        item = dict(stop)
        found = _match_name(labels, stop.get("name"))
        live = by.get(found) if found else None
        if isinstance(live, dict):
            if live.get("sched"):
                item["sched"] = live.get("sched")
            if live.get("est"):
                item["est"] = live.get("est")
        item.setdefault("est", item.get("sched"))
        out.append(item)
    return out


def _join_records(records: list[dict], shapes: dict) -> dict | None:
    """One ride, even when an older cache stored each half under LAN5311 and MED5311."""
    unique: list[dict] = []
    seen: set[int] = set()
    for record in records:
        if not isinstance(record, dict) or not record.get("stops"):
            continue
        if id(record) in seen:
            continue
        seen.add(id(record))
        unique.append(record)
    if not unique:
        return None
    used: set[int] = set()
    chain: list[dict] = []
    for record in unique:
        if id(record) in used:
            continue
        first = str((record.get("stops") or [{}])[0].get("name") or "")
        if any(_same_stop(first, (other.get("stops") or [{}])[-1].get("name")) for other in unique if other is not record):
            continue
        used.add(id(record))
        chain.append(record)
        break
    if not chain:
        chain.append(unique[0])
        used.add(id(unique[0]))
    grew = True
    while grew:
        grew = False
        last = str((chain[-1].get("stops") or [{}])[-1].get("name") or "")
        for record in unique:
            if id(record) in used:
                continue
            first = str((record.get("stops") or [{}])[0].get("name") or "")
            if _same_stop(first, last):
                used.add(id(record))
                chain.append(record)
                grew = True
                break
    stops: list[dict] = []
    points: list = []
    segments: list[dict] = []
    used_shape = False
    for record in chain:
        part = [dict(stop) for stop in record.get("stops") or []]
        route_id = str(record.get("route_id") or "")
        for stop in part:
            stop.setdefault("route_id", route_id)
        if stops and part and _same_stop(part[0].get("name"), stops[-1].get("name")):
            part = part[1:]
        if record.get("stops"):
            segments.append(
                {
                    "route_id": route_id,
                    "line": route_id,
                    "shape_id": str(record.get("shape_id") or ""),
                    "first": record["stops"][0].get("name"),
                    "last": record["stops"][-1].get("name"),
                }
            )
        stops.extend(part)
        shape_id = str(record.get("shape_id") or "")
        line = shapes.get(shape_id) if shape_id else None
        if line and len(line) >= 2 and not str(shape_id).startswith("stops:"):
            if points and line[0] == points[-1]:
                line = line[1:]
            points.extend(line)
            used_shape = True
        else:
            extra = [[stop["lat"], stop["lon"]] for stop in part if stop.get("lat") is not None and stop.get("lon") is not None]
            points.extend(extra)
    if len(stops) < 1:
        return None
    source = "gtfs" if used_shape and len(points) >= 2 else "stops"
    if len(points) < 2:
        points = [[stop["lat"], stop["lon"]] for stop in stops if stop.get("lat") is not None and stop.get("lon") is not None]
        source = "stops"
    return {
        "shape_id": "+".join(str(item.get("shape_id") or "") for item in chain if item.get("shape_id")),
        "route_id": str(chain[0].get("route_id") or ""),
        "stops": stops,
        "segments": segments,
        "points": points,
        "source": source if len(points) >= 2 else "stops",
    }


def lookup_train(cache: dict | None, number: object) -> dict | None:
    """Train number 5311 matches LAN5311 and MED5311. The halves are one line."""
    trains = (cache or {}).get("trains") if isinstance(cache, dict) else None
    if not isinstance(trains, dict) or not number:
        return None
    want = _bare_number(number)
    exact = str(number).strip()
    records = []
    for key, info in trains.items():
        if key == exact or _bare_number(key) == want:
            records.append(info)
    if not records:
        return None
    return _join_records(records, (cache or {}).get("shapes") or {})


def _color_for(info: dict, routes: dict, next_stop: object, current: object) -> tuple:
    route_id = str(info.get("route_id") or "")
    here = _key_name(next_stop or current)
    if here:
        for stop in info.get("stops") or []:
            if _key_name(stop.get("name")) == here and stop.get("route_id"):
                route_id = str(stop["route_id"])
                break
    route = routes.get(route_id) or {}
    return route.get("color"), route.get("text_color")


def _ride_here(data: dict) -> tuple | None:
    lat = _num(data.get("latitude") if data.get("latitude") is not None else data.get("lat"))
    lon = _num(data.get("longitude") if data.get("longitude") is not None else data.get("lon"))
    if lat is None or lon is None:
        return None
    return (lat, lon)


def _geo_stop(name: object, geo: dict | None) -> tuple | None:
    if not isinstance(geo, dict):
        return None
    table = geo.get("by_key") if isinstance(geo.get("by_key"), dict) else {}
    want = _key_name(name)
    for key, value in table.items():
        if not isinstance(value, (list, tuple)) or len(value) < 3:
            continue
        if _key_name(key) == want or _key_name(value[0]) == want:
            lat, lon = _num(value[1]), _num(value[2])
            if lat is None or lon is None:
                continue
            return lat, lon
    return None


def _stops_from_ride(data: dict, geo: dict | None) -> list[dict]:
    rows = data.get("route_stops") or data.get("full_stops") or data.get("remaining_stops") or []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("station")
        lat = _num(row.get("lat"))
        lon = _num(row.get("lon"))
        if lat is None or lon is None:
            found = _geo_stop(name, geo)
            if found:
                lat, lon = found
        if lat is None or lon is None:
            continue
        out.append(
            {
                "name": name,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "sched": row.get("sched"),
                "est": row.get("est") or row.get("sched"),
            }
        )
    return out


def _reason_result(reason: str, source: str, payload: dict | None = None) -> dict:
    body = dict(payload or cleared_route())
    body["route_shape_source"] = source
    body["route_shape_reason"] = reason
    return body


def attach_route(data: dict | None, cache: dict | None, memo: dict | None = None, byte_limit: int = ATTR_BYTE_LIMIT, geo: dict | None = None) -> dict:
    """Route attributes for an active ride. A later update reuses the simplified line.

    An empty shape cache still draws the stops we know. `route_shape_source` is
    `none` only when fewer than two stops have coordinates.
    """
    if not isinstance(data, dict) or not data.get("riding"):
        return cleared_route()
    number = str(data.get("train") or "").strip()
    trains = (cache or {}).get("trains") if isinstance(cache, dict) else None
    reason = None
    info = None
    try:
        if not isinstance(trains, dict) or not trains:
            reason = "cache_empty"
        else:
            info = lookup_train(cache, number)
            if not info:
                reason = "train_not_in_cache"
            elif not (info.get("points") or []):
                segs = [str(item.get("shape_id") or "") for item in info.get("segments") or []]
                reason = "shape_id_missing" if not any(segs) else "too_few_points"
    except Exception:
        reason = "exception"
        info = None
    here = _ride_here(data)
    alight = data.get("alight_station") or data.get("final_destination") or None
    if isinstance(alight, str):
        alight = alight.strip() or None
    if not info:
        stops = _stops_from_ride(data, geo)
        if len(stops) < 2:
            note_missing_shape(number, reason or "too_few_points", date.today().isoformat())
            return _reason_result(reason or "too_few_points", "none")
        points = [[stop["lat"], stop["lon"]] for stop in stops]
        note_missing_shape(number, reason or "cache_empty", date.today().isoformat())
        fitted, _meta = fit_route(
            points,
            stops,
            color=None,
            text_color=None,
            alight=alight,
            next_stop=data.get("next_stop"),
            boarded=data.get("origin"),
            byte_limit=byte_limit,
            source="stops",
            here=here,
        )
        return _reason_result(reason or "cache_empty", "stops", fitted)
    points = list(info.get("points") or [])
    source = info.get("source") or "gtfs"
    stops = _overlay_times(info.get("stops") or [], data.get("remaining_stops"))
    if len(points) < 2:
        points = [[stop["lat"], stop["lon"]] for stop in stops if stop.get("lat") is not None and stop.get("lon") is not None]
        source = "stops"
        reason = reason or "too_few_points"
    if len(points) < 2:
        note_missing_shape(number, reason or "too_few_points", date.today().isoformat())
        return _reason_result(reason or "too_few_points", "none")
    if source == "stops":
        note_missing_shape(number, reason or "shape missing", date.today().isoformat())
    routes = (cache or {}).get("routes") or {}
    color, text_color = _color_for(info, routes, data.get("next_stop"), data.get("current_stop"))
    shape_id = str(info.get("shape_id") or number)
    key = _memo_key(shape_id, stops) + (int(byte_limit), source)
    store = memo if isinstance(memo, dict) else None
    if store is not None and isinstance(store.get(key), dict) and store[key].get("points"):
        fitted = _from_memo(store[key], stops, color, text_color, alight, data.get("next_stop"), data.get("origin"), here)
    else:
        fitted, meta = fit_route(
            points,
            stops,
            color=color,
            text_color=text_color,
            alight=alight,
            next_stop=data.get("next_stop"),
            boarded=data.get("origin"),
            byte_limit=byte_limit,
            source=source,
            here=here,
        )
        if store is not None:
            store[key] = meta
    fitted["route_shape_reason"] = None if source == "gtfs" else (reason or "shape missing")
    return fitted


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
    info = lookup_train(cache, number) if number else None
    if not info:
        return {"error": "not_found"}
    shape = info.get("points") or []
    if len(shape) < 2:
        return {"error": "not_found"}
    route = ((cache or {}).get("routes") or {}).get(info.get("route_id")) or {}
    detail = row if isinstance(row, dict) and (_bare_number(row.get("train")) == _bare_number(number)) else {}
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
        found[rid] = {
            "color": _color(row.get("route_color")),
            "text_color": _color(row.get("route_text_color")),
            "name": str(row.get("route_long_name") or row.get("route_short_name") or "").strip() or None,
        }
    return found


def _active_services(files: dict, today: date | None) -> set[str]:
    """Service ids that run on `today`. Empty means the feed has no calendar."""
    day = today or date.today()
    ymd = day.strftime("%Y%m%d")
    names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    today_name = names[day.weekday()]
    calendar = list(_csv(files.get("calendar") or ""))
    dates = list(_csv(files.get("calendar_dates") or ""))
    if not calendar and not dates:
        return set()
    active: set[str] = set()
    for row in calendar:
        sid = str(row.get("service_id") or "").strip()
        start = str(row.get("start_date") or "")
        end = str(row.get("end_date") or "")
        if not sid or (start and ymd < start) or (end and ymd > end):
            continue
        if str(row.get(today_name) or "0").strip() in {"1", "true", "yes"}:
            active.add(sid)
    for row in dates:
        sid = str(row.get("service_id") or "").strip()
        if str(row.get("date") or "") != ymd or not sid:
            continue
        kind = str(row.get("exception_type") or "").strip()
        if kind == "1":
            active.add(sid)
        elif kind == "2":
            active.discard(sid)
    return active


def build_shape_cache(zip_bytes: bytes, today: date | None = None) -> dict:
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
        clock = str(row.get("arrival_time") or row.get("departure_time") or "")
        parts = clock.split(":")
        minutes = 0
        if len(parts) >= 2:
            try:
                minutes = int(parts[0]) * 60 + int(parts[1])
            except ValueError:
                minutes = 0
        order.setdefault(trip_id, []).append((0 if seq is None else seq, minutes, dict(stop)))
    try:
        from .trips import bare_train, merge_through_runs
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location("septa_trips_shapes", Path(__file__).with_name("trips.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bare_train = module.bare_train
        merge_through_runs = module.merge_through_runs
    collected = []
    for trip_id, rows in order.items():
        trip = trips.get(trip_id) or {}
        rows.sort(key=lambda item: (item[0], item[1]))
        collected.append(
            {
                "id": trip_id,
                "route_id": str(trip.get("route_id") or ""),
                "service": str(trip.get("service_id") or ""),
                "headsign": str(trip.get("trip_headsign") or ""),
                "number": str(trip.get("trip_short_name") or trip_id).strip(),
                "direction": str(trip.get("direction_id") or "0"),
                "block": str(trip.get("block_id") or "").strip(),
                "shape": str(trip.get("shape_id") or "").strip(),
                "stops": [
                    {
                        "name": item[2]["name"],
                        "seq": item[0],
                        "minutes": item[1],
                        "lat": item[2]["lat"],
                        "lon": item[2]["lon"],
                        "sched": f"{(int(item[1]) // 60) % 24:02d}:{int(item[1]) % 60:02d}",
                    }
                    for item in rows
                ],
            }
        )
    trains: dict[str, dict] = {}
    chosen: dict[str, bool] = {}
    active = _active_services(files, today)
    for run in merge_through_runs(collected):
        served = [
            {
                "name": stop["name"],
                "lat": stop.get("lat"),
                "lon": stop.get("lon"),
                "sched": stop.get("sched"),
                "route_id": str(stop.get("line") or ""),
            }
            for stop in run.get("stops") or []
            if stop.get("lat") is not None
        ]
        if len(served) < 2 and not run.get("through"):
            if len(served) < 1:
                continue
        pieces = []
        shape_ids = []
        for segment in run.get("segments") or []:
            shape_id = str(segment.get("shape_id") or "")
            line = shapes.get(shape_id) if shape_id else None
            if line and len(line) >= 2:
                if pieces and line and pieces[-1] == line[0]:
                    line = line[1:]
                pieces.extend(line)
                shape_ids.append(shape_id)
        if len(pieces) < 2:
            pieces = [[stop["lat"], stop["lon"]] for stop in served]
            if len(pieces) == 1:
                pieces = [pieces[0], pieces[0]]
            shape_ids = []
        if len(pieces) < 2:
            continue
        shape_id = "+".join(shape_ids) if len(shape_ids) > 1 else (shape_ids[0] if shape_ids else "")
        if not shape_id:
            shape_id = "stops:" + str(run.get("number") or run.get("label") or "")
            shapes[shape_id] = pieces
        elif len(shape_ids) > 1:
            shapes[shape_id] = pieces
        info = {
            "shape_id": shape_id,
            "route_id": str((run.get("segments") or [{}])[0].get("route_id") or ""),
            "stops": served,
            "segments": list(run.get("segments") or []),
            "service": str(run.get("service") or ""),
        }
        keys = {str(run.get("label") or ""), str(run.get("number") or ""), bare_train(run.get("number"))}
        for source in run.get("sources") or []:
            keys.add(str(source))
            keys.add(bare_train(source))
        for key in keys:
            if not key:
                continue
            prefer = bool(active) and str(run.get("service") or "") in active
            if key in chosen and chosen[key] and not prefer:
                continue
            chosen[key] = prefer or not active
            trains[key] = info
    if not trains:
        raise ValueError("shapes")
    return {"format": SHAPES_FORMAT, "shapes": shapes, "trains": trains, "routes": _routes(files.get("routes") or "")}


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
    body = dict(payload or {})
    body["format"] = SHAPES_FORMAT
    write_schedule_file(path, body)
