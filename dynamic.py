"""Per-rider Going Home and day-train planning. No Home Assistant imports."""

from __future__ import annotations

import csv
import io
import math
import re
from collections import OrderedDict
from datetime import date, datetime, timedelta

try:
    from .trips import (
        NY,
        _NTA_ALIASES,
        _iso,
        _parse_iso,
        bare_train,
        loose_key,
        station_key,
        train_paths,
    )
except ImportError:
    import importlib.util
    from pathlib import Path

    _spec = importlib.util.spec_from_file_location("septa_trips_dyn", Path(__file__).with_name("trips.py"))
    _trips = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_trips)
    NY = _trips.NY
    _NTA_ALIASES = _trips._NTA_ALIASES
    _iso = _trips._iso
    _parse_iso = _trips._parse_iso
    bare_train = _trips.bare_train
    loose_key = _trips.loose_key
    station_key = _trips.station_key
    train_paths = _trips.train_paths

HYSTERESIS_M = 200
LIVE_WINDOW_MIN = 90

# Public landmarks and ZIP codes. A street address can name a station
# without calling a geocoder. Phrases are matched on word boundaries.
_PLACE_ROWS = (
    ("university of pennsylvania", "Penn Medicine Station", 39.9522, -75.1934),
    ("university city", "Penn Medicine Station", 39.94806, -75.19028),
    ("penn medicine", "Penn Medicine Station", 39.94806, -75.19028),
    ("upenn", "Penn Medicine Station", 39.9522, -75.1934),
    ("temple university", "Temple University", 39.98139, -75.14944),
)
_ZIP_ROWS = {
    "19104": ("Penn Medicine Station", 39.9522, -75.1934),
    "19122": ("Temple University", 39.98139, -75.14944),
}
# Only when the text also says Philadelphia or that ZIP. "36th St" alone is not enough.
_STREET_ROWS = (
    (r"\b36th\b", ("philadelphia", "19104"), 39.9524, -75.1965),
)

_ROW_KEYS = (
    "train",
    "line",
    "destination",
    "depart_sched",
    "depart_est",
    "arrive_sched",
    "arrive_est",
    "late_min",
    "delay_min",
    "minutes",
    "track",
    "platform",
    "track_changed",
    "direct",
    "transfer",
    "connection",
    "live",
    "train_number",
    "service_type",
    "stops_count",
    "stops",
    "skipped",
    "through",
)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def _num(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_valid_until(schedule: dict | None) -> date | None:
    raw = str((schedule or {}).get("validUntil") or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def schedule_expired(schedule: dict | None, today: date) -> bool:
    until = parse_valid_until(schedule)
    if until is None:
        return True
    return until < today


def select_schedule(bundled: dict | None, cached: dict | None, today: date) -> tuple[dict, str]:
    """Fresh downloaded cache, else a current bundled file, else whichever is newer."""
    def usable(item: dict | None) -> bool:
        return isinstance(item, dict) and bool(item.get("stations")) and not schedule_expired(item, today)

    if usable(cached):
        return cached, "downloaded"
    if usable(bundled):
        return bundled, "bundled"
    ranked: list[tuple[date, dict]] = []
    for item in (cached, bundled):
        if isinstance(item, dict) and item.get("stations"):
            ranked.append((parse_valid_until(item) or date.min, item))
    if not ranked:
        return {"stations": {}}, "missing"
    ranked.sort(key=lambda pair: pair[0])
    return ranked[-1][1], "expired"


def timetable_allowed(source: str) -> bool:
    return source in {"bundled", "gtfs", "downloaded"}


def rail_station_names(schedule: dict | None) -> list[str]:
    """Unique station names from the active timetable, sorted A–Z."""
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    if not isinstance(stations, dict):
        return []
    seen: dict[str, str] = {}
    for name in stations:
        text = str(name).strip()
        key = text.casefold()
        if text and key not in seen:
            seen[key] = text
    return sorted(seen.values(), key=str.casefold)


def rail_picker_options(schedule: dict | None, fallback: list[str] | None = None, line: str | None = None) -> list[str]:
    """Regional Rail stations only. A line's stops come first when one is set."""
    names = rail_station_names(schedule)
    if not names:
        seen: dict[str, str] = {}
        for name in fallback or []:
            text = str(name).strip()
            key = text.casefold()
            if text and key not in seen:
                seen[key] = text
        return sorted(seen.values(), key=str.casefold)
    code = str(line or "").strip()
    if not code:
        return names
    index = line_index(schedule)
    first: list[str] = []
    rest: list[str] = []
    for name in names:
        lines = {str(item).upper() for item in index.get(station_key(name), set())}
        if code.upper() in lines:
            first.append(name)
        else:
            rest.append(name)
    return first + rest if first else names


def canonical_rail_station(text: object, names: list[str]) -> str | None:
    return match_station(text, list(names or []))


def legacy_non_rail(values: list, schedule: dict | None, metro: list | None, trolley: list | None) -> list[str]:
    """Saved Metro/trolley names that are not in the rail timetable. Rail names are kept."""
    rail_names = rail_station_names(schedule)
    rail = {name.casefold() for name in rail_names}
    if not rail:
        return []
    other: list[str] = []
    for name in list(metro or []) + list(trolley or []):
        if str(name).casefold() not in rail:
            other.append(str(name))
    other_keys = {station_key(name) for name in other}
    bad: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text.casefold() in rail or match_station(text, rail_names):
            continue
        if station_key(text) in other_keys or match_station(text, other):
            bad.append(text)
    return bad


def indexed_stops(schedule: dict | None, geo: dict | None) -> list[dict]:
    """Regional Rail stops that exist in the timetable. Geo-only names are dropped."""
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    stops = (geo or {}).get("stops") if isinstance(geo, dict) else None
    if not isinstance(stations, dict) or not isinstance(stops, dict):
        return []
    geo_by = {}
    for name, coords in stops.items():
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            geo_by[station_key(name)] = (str(name), coords)
    found: list[dict] = []
    for name in stations:
        key = station_key(name)
        hit = geo_by.get(key)
        if hit is None:
            for gkey, item in geo_by.items():
                if key and (key in gkey or gkey in key):
                    hit = item
                    break
        if hit is None:
            continue
        lat, lon = _num(hit[1][0]), _num(hit[1][1])
        if lat is None or lon is None:
            continue
        found.append({"name": str(name), "lat": lat, "lon": lon})
    return found


def station_names(schedule: dict | None, geo: dict | None = None) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    if isinstance(stations, dict):
        for name in stations:
            key = station_key(name)
            if key and key not in seen:
                seen.add(key)
                names.append(str(name))
    stops = (geo or {}).get("stops") if isinstance(geo, dict) else None
    if isinstance(stops, dict):
        for name in stops:
            key = station_key(name)
            if key and key not in seen:
                seen.add(key)
                names.append(str(name))
    return names


def line_index(schedule: dict | None) -> dict[str, set[str]]:
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    out: dict[str, set[str]] = {}
    if not isinstance(stations, dict):
        return out
    for name, pack in stations.items():
        lines: set[str] = set()
        if isinstance(pack, dict):
            for direction in ("N", "S"):
                for row in pack.get(direction) or []:
                    if isinstance(row, dict) and row.get("line"):
                        lines.add(str(row["line"]))
        out[station_key(name)] = lines
    return out


def nearest_station(
    lat: float,
    lon: float,
    stops: list[dict],
    radius_m: float,
    current: str | None = None,
    hysteresis_m: float = HYSTERESIS_M,
) -> dict | None:
    best = None
    best_d = None
    current_hit = None
    current_d = None
    for stop in stops:
        dist = haversine_m(lat, lon, stop["lat"], stop["lon"])
        if current and station_key(stop["name"]) == station_key(current):
            current_hit = stop
            current_d = dist
        if dist <= radius_m and (best_d is None or dist < best_d):
            best, best_d = stop, dist
    if best is None or best_d is None:
        return None
    if (
        current_hit is not None
        and current_d is not None
        and current_d <= radius_m
        and station_key(best["name"]) != station_key(current_hit["name"])
        and current_d - best_d < hysteresis_m
    ):
        best, best_d = current_hit, current_d
    return {
        "name": best["name"],
        "distance_m": int(round(best_d)),
        "lat": best["lat"],
        "lon": best["lon"],
    }


def _coords_for(name: str | None, stops: list[dict]) -> tuple[float | None, float | None]:
    if not name:
        return None, None
    for stop in stops:
        if station_key(stop["name"]) == station_key(name):
            return stop["lat"], stop["lon"]
    return None, None


def resolve_origin(
    *,
    manual: str | None = None,
    at_home: bool = False,
    lat: float | None = None,
    lon: float | None = None,
    accuracy: float | None = None,
    max_accuracy: float = 100,
    stops: list[dict] | None = None,
    radius_m: float = 1500,
    current: str | None = None,
    city_station: str | None = None,
    home_station: str | None = None,
    last: str | None = None,
    hysteresis_m: float = HYSTERESIS_M,
    zone: str | None = None,
    stale: bool = False,
    origin_entity: str | None = None,
    fix_age_s: float | None = None,
    ride_origin: str | None = None,
    last_recent: bool = False,
) -> dict:
    """manual, then home, then a ride or a zone or the nearest station."""
    stops = stops or []
    source = None
    name = None
    distance = None
    skip = None
    inaccurate = accuracy is not None and accuracy > max_accuracy
    if str(manual or "").strip():
        source, name = "manual", str(manual).strip()
    elif at_home:
        source, name = "home", home_station or None
    elif stale and str(ride_origin or "").strip():
        source, name = "ride", str(ride_origin).strip()
    elif not stale and str(zone or "").strip():
        source, name, distance = "zone", str(zone).strip(), 0
    elif not stale and lat is not None and lon is not None and not inaccurate and stops:
        hit = nearest_station(lat, lon, stops, radius_m, current=current, hysteresis_m=hysteresis_m)
        if hit:
            source, name = "nearest", hit["name"]
            distance = hit["distance_m"]
        else:
            skip = "out_of_radius"
    elif stale and str(last or "").strip() and last_recent:
        source, name = "last", str(last).strip()
    elif lat is None or lon is None:
        skip = "no_coords"
    elif not stops:
        skip = "no_stops"
    elif stale:
        skip = "stale"
    elif inaccurate:
        skip = "inaccurate"
    else:
        skip = "out_of_radius"
    if name is None and str(city_station or "").strip():
        source, name = "default", str(city_station).strip()
        if not skip:
            skip = "stale" if stale else "no_coords"
    if name is None and str(last or "").strip():
        source, name = "last", str(last).strip()
    reason = None
    if at_home or (name and home_station and station_key(name) == station_key(home_station)):
        reason = "at_home_station"
        if at_home:
            name = home_station or name
            source = "home" if source != "manual" else source
    olat, olon = _coords_for(name, stops)
    return {
        "origin": name,
        "origin_source": source,
        "origin_distance_m": distance,
        "origin_lat": olat,
        "origin_lon": olon,
        "reason": reason,
        "origin_entity": origin_entity,
        "origin_fix_lat": lat,
        "origin_fix_lon": lon,
        "origin_fix_accuracy": accuracy,
        "origin_fix_age_s": fix_age_s,
        "origin_skip_reason": skip,
    }


_ZONE_SKIP = {"home", "not_home", "unknown", "unavailable", "none"}
ORIGIN_MAX_AGE_S = 6 * 3600


def pick_fix(rows: list[dict]) -> dict:
    """First usable location. Prefer the freshest row that has coordinates."""
    usable = [row for row in rows if row.get("lat") is not None and row.get("lon") is not None]

    def rank(row: dict) -> tuple:
        updated = row.get("updated")
        stamp = float(updated) if isinstance(updated, (int, float)) else -1.0
        return (stamp, -rows.index(row))

    if usable:
        return max(usable, key=rank)
    return rows[0] if rows else {}


def zone_station(state: object, names: list[str]) -> str | None:
    """A tracker state that is a station name. Home and not_home are not stations."""
    text = str(state or "").strip()
    if not text or text.lower() in _ZONE_SKIP:
        return None
    return match_station(text, names)


def watch_entities(specs: list[dict]) -> list[str]:
    """Entities whose state should refresh Going Home. Includes the person and its tracker."""
    entities: list[str] = []
    for spec in specs:
        for key in ("configured", "tracker", "person"):
            entity = str(spec.get(key) or "")
            if "." in entity:
                entities.append(entity)
    return list(dict.fromkeys(entities))


def _words(text: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(text or "").lower())).strip()


def builtin_place(text: object) -> dict | None:
    """Station or coordinates for a known campus, ZIP, or street. None if unknown."""
    raw = str(text or "").strip()
    if not raw:
        return None
    folded = _words(raw)
    padded = f" {folded} "
    for phrase, station, lat, lon in _PLACE_ROWS:
        if f" {phrase} " in padded:
            return {"station": station, "lat": lat, "lon": lon, "via": "phrase"}
    for code in re.findall(r"\b(\d{5})(?:-\d{4})?\b", raw):
        row = _ZIP_ROWS.get(code)
        if row:
            station, lat, lon = row
            return {"station": station, "lat": lat, "lon": lon, "via": "zip"}
    low = raw.lower()
    for pattern, context, lat, lon in _STREET_ROWS:
        if re.search(pattern, low) and any(token in low or token in folded for token in context):
            return {"station": None, "lat": lat, "lon": lon, "via": "street"}
    return None


def cap_trains(rows: list | None, limit: int = 60) -> tuple[list, int]:
    """Keep the first `limit` rows. The second value is the count before the cap."""
    items = list(rows or [])
    total = len(items)
    try:
        kept = int(limit)
    except (TypeError, ValueError):
        kept = 60
    if kept < 1:
        return items, total
    return items[:kept], total


_MATCH_CACHE: OrderedDict = OrderedDict()
_MATCH_CACHE_MAX = 256


def _match_quality(query_key: str, query_loose: str, query_tokens: list[str], name: str) -> int | None:
    got = station_key(name)
    loose = loose_key(name)
    if query_key and got == query_key:
        return 0
    if query_loose and loose == query_loose:
        return 1
    tokens = loose.split() if loose else []
    if query_tokens and tokens and all(token in tokens for token in query_tokens):
        return 2
    if query_tokens and len(tokens) >= 2 and all(token in query_tokens for token in tokens):
        return 3
    if query_loose and loose and (query_loose in loose or loose in query_loose):
        return 3
    if query_key and got and (query_key in got or got in query_key):
        return 3
    return None


def match_station(text: object, names: list[str], prefer: list[str] | None = None) -> str | None:
    """Return a name from ``names``. An alias that is not in the list is never returned."""
    raw = str(text or "").strip()
    pool = [str(name).strip() for name in names or [] if str(name or "").strip()]
    if not raw or not pool:
        return None
    prefer_keys = tuple(sorted({station_key(name) for name in prefer or [] if station_key(name)}))
    cache_key = (loose_key(raw), tuple(pool), prefer_keys)
    if cache_key in _MATCH_CACHE:
        _MATCH_CACHE.move_to_end(cache_key)
        return _MATCH_CACHE[cache_key]
    query_key = station_key(raw)
    query_loose = loose_key(raw)
    query_tokens = query_loose.split() if query_loose else []
    ranked: list[tuple] = []
    for name in pool:
        quality = _match_quality(query_key, query_loose, query_tokens, name)
        if quality is None:
            continue
        preferred = 0 if station_key(name) in prefer_keys else 1
        ranked.append((preferred, quality, len(name), name.casefold(), name))
    found = None
    if ranked:
        ranked.sort()
        best = ranked[0]
        tied = [item for item in ranked if item[:3] == best[:3]]
        if len(tied) == 1:
            found = tied[0][4]
    _MATCH_CACHE[cache_key] = found
    while len(_MATCH_CACHE) > _MATCH_CACHE_MAX:
        _MATCH_CACHE.popitem(last=False)
    return found


_SHORT_WORD = {
    "st": "Street",
    "ave": "Avenue",
    "ln": "Lane",
    "rd": "Road",
    "blvd": "Boulevard",
    "dr": "Drive",
    "tc": "Transit Center",
}


def short_station(name: object) -> str:
    """Display name. A trailing Station is dropped and abbreviations are expanded."""
    text = re.sub(r"\s+station$", "", str(name or "").strip(), flags=re.IGNORECASE)
    parts = []
    for token in text.split():
        bare = re.sub(r"[^A-Za-z0-9]", "", token).lower()
        parts.append(_SHORT_WORD.get(bare, token))
    return " ".join(parts).strip()


def station_catalog(schedule: dict | None) -> list[dict]:
    """Schedule stations for a picker. Names are the timetable's, not a guess."""
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    if not isinstance(stations, dict):
        return []
    lines = line_index(schedule)
    rows = []
    for name in sorted((str(item) for item in stations), key=str.casefold):
        rows.append(
            {
                "name": name,
                "key": station_key(name),
                "short": short_station(name),
                "lines": sorted(lines.get(station_key(name)) or []),
            }
        )
    return rows


def _event_start(event: dict | None) -> datetime | None:
    if not isinstance(event, dict):
        return None
    return _parse_iso(event.get("start") or event.get("start_time"))


def walk_minutes_for(distance_m: object, speed_m_per_min: float = 80, detour: float = 1.3) -> int:
    """Minutes to walk from the station to the event. Unknown distance is zero."""
    number = _num(distance_m)
    if number is None or number < 0:
        return 0
    speed = _num(speed_m_per_min) or 80
    if speed <= 0:
        speed = 80
    factor = _num(detour) or 1.3
    if factor <= 0:
        factor = 1.3
    return int(math.ceil((number * factor) / speed))


def _stop_coords(name: object, stops: list[dict] | None) -> tuple[float, float] | None:
    want = station_key(name)
    if not want:
        return None
    for stop in stops or []:
        if station_key(stop.get("name")) != want:
            continue
        lat = _num(stop.get("lat"))
        lon = _num(stop.get("lon"))
        if lat is None or lon is None:
            return None
        return lat, lon
    return None


def _event_point(event: dict | None, zones: list[dict] | None, geocoded: tuple[float, float] | None) -> tuple[float, float] | None:
    if not isinstance(event, dict):
        return None
    lat = _num(event.get("latitude"))
    lon = _num(event.get("longitude"))
    if (lat is None or lon is None) and zones and event.get("location"):
        want = station_key(event.get("location"))
        for zone in zones:
            if station_key(zone.get("name")) == want:
                lat = _num(zone.get("latitude"))
                lon = _num(zone.get("longitude"))
                break
    if (lat is None or lon is None) and geocoded:
        lat, lon = geocoded
    if lat is None or lon is None:
        place = builtin_place(event.get("location"))
        if place and place.get("lat") is not None:
            lat, lon = place["lat"], place["lon"]
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def _has_location(event: dict | None) -> bool:
    if not isinstance(event, dict):
        return False
    if str(event.get("location") or "").strip():
        return True
    return _num(event.get("latitude")) is not None and _num(event.get("longitude")) is not None


def _date_only(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and "T" not in text and len(text) <= 10


def event_is_usable(event: dict | None, now: datetime) -> bool:
    """A timed event with a place, not already more than 30 minutes underway."""
    if not isinstance(event, dict) or event.get("all_day") or _date_only(event.get("start") or event.get("start_time")):
        return False
    start = _event_start(event)
    if start is None or not _has_location(event):
        return False
    base = now.astimezone(start.tzinfo) if now.tzinfo else now.replace(tzinfo=start.tzinfo)
    return start >= base - timedelta(minutes=30)


def pick_calendar_event(state_event: dict | None, fetched: list | None, now: datetime) -> tuple[dict | None, str | None]:
    """First timed event that still has a location. All-day events are skipped."""
    if event_is_usable(state_event, now):
        return state_event, None
    saw_locationless = _has_start(state_event) and not _has_location(state_event) and not _is_all_day(state_event)
    ranked = []
    for item in fetched or []:
        if not isinstance(item, dict) or _is_all_day(item):
            continue
        start = _event_start(item)
        if start is None:
            continue
        base = now.astimezone(start.tzinfo) if now.tzinfo else now.replace(tzinfo=start.tzinfo)
        if start < base - timedelta(minutes=30):
            continue
        ranked.append((start, item))
    ranked.sort(key=lambda pair: pair[0])
    for _start, item in ranked:
        if _has_location(item):
            return item, None
        saw_locationless = True
    if saw_locationless:
        return state_event if isinstance(state_event, dict) else None, "no_location"
    return None, "no_event"


def _has_start(event: dict | None) -> bool:
    return isinstance(event, dict) and _event_start(event) is not None and not _is_all_day(event)


def _is_all_day(event: dict | None) -> bool:
    if not isinstance(event, dict):
        return False
    if event.get("all_day"):
        return True
    return _date_only(event.get("start") or event.get("start_time"))


def resolve_destination(
    *,
    manual: str | None = None,
    entity_state: str | None = None,
    event: dict | None = None,
    default_station: str | None = None,
    names: list[str] | None = None,
    stops: list[dict] | None = None,
    zones: list[dict] | None = None,
    near_radius_m: float = 1500,
    geocoded: tuple[float, float] | None = None,
) -> dict:
    """manual, then entity, then calendar alias, then coordinates, then the default."""
    names = names or []
    stops = stops or []
    kept = event if isinstance(event, dict) else None
    point = _event_point(kept, zones, geocoded)

    def pack(station: str | None, source: str | None) -> dict:
        distance = None
        coords = _stop_coords(station, stops)
        if point and coords:
            distance = int(round(haversine_m(point[0], point[1], coords[0], coords[1])))
        return {
            "destination": station,
            "destination_source": source,
            "event": kept,
            "destination_distance_m": distance,
        }

    if str(manual or "").strip():
        return pack(match_station(manual, names) or str(manual).strip(), "manual")
    if str(entity_state or "").strip():
        hit = match_station(entity_state, names)
        if hit:
            return pack(hit, "entity")
    if kept:
        hit = match_station(kept.get("location"), names)
        if hit:
            return pack(hit, "calendar")
        place = builtin_place(kept.get("location"))
        if place and place.get("station"):
            named = match_station(place["station"], names)
            if named:
                return pack(named, "calendar")
        lat = _num(kept.get("latitude"))
        lon = _num(kept.get("longitude"))
        if (lat is None or lon is None) and zones and kept.get("location"):
            want = station_key(kept.get("location"))
            for zone in zones:
                if station_key(zone.get("name")) == want:
                    lat = _num(zone.get("latitude"))
                    lon = _num(zone.get("longitude"))
                    break
        if (lat is None or lon is None) and geocoded:
            lat, lon = geocoded
        if (lat is None or lon is None) and place and place.get("lat") is not None:
            lat, lon = place["lat"], place["lon"]
        if lat is not None and lon is not None:
            near = nearest_station(lat, lon, stops, near_radius_m, hysteresis_m=0)
            if near:
                return pack(near["name"], "calendar")
    if str(default_station or "").strip():
        return pack(str(default_station).strip(), "default")
    return pack(None, None)


def _path_index(path: list[dict], name: str) -> int | None:
    want = station_key(name)
    for index, stop in enumerate(path):
        if station_key(stop["station"]) == want:
            return index
    return None


def _blank_connection() -> dict:
    return {
        "station": None,
        "train": None,
        "line": None,
        "arrive_sched": None,
        "arrive_est": None,
        "depart_sched": None,
        "depart_est": None,
        "arrive_final_sched": None,
        "arrive_final_est": None,
        "wait_min": None,
        "at_risk": False,
        "track": None,
        "platform": None,
        "delay_min": None,
    }


def _link(station, train, line, arrive, depart, final, transfer_min, dest_name) -> dict:
    wait = int(round((depart - arrive).total_seconds() / 60))
    link = _blank_connection()
    link.update(
        {
            "station": station,
            "train": train,
            "line": line,
            "arrive_sched": _iso(arrive),
            "arrive_est": _iso(arrive),
            "depart_sched": _iso(depart),
            "depart_est": _iso(depart),
            "arrive_final_sched": _iso(final),
            "arrive_final_est": _iso(final),
            "wait_min": wait,
            "at_risk": wait < transfer_min,
        }
    )
    link["destination"] = dest_name
    return link


def shared_transfer_stations(schedule: dict | None, origin: str, destination: str) -> list[str]:
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    if not isinstance(stations, dict):
        return []
    index = line_index(schedule)
    origin_lines = index.get(station_key(origin), set())
    dest_lines = index.get(station_key(destination), set())
    found = []
    for name in stations:
        key = station_key(name)
        if key in {station_key(origin), station_key(destination)}:
            continue
        lines = index.get(key, set())
        if lines & origin_lines and lines & dest_lines:
            found.append(str(name))
    return found


_ITINERARIES = None


def _itinerary_fn():
    """Load the index once. Reloading it would throw away the timetable cache."""
    global _ITINERARIES
    if _ITINERARIES is not None:
        return _ITINERARIES
    try:
        from .index import cached_itineraries
    except ImportError:
        import importlib.util
        from pathlib import Path

        _spec = importlib.util.spec_from_file_location("septa_index_dyn", Path(__file__).with_name("index.py"))
        _index = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_index)
        cached_itineraries = _index.cached_itineraries
    _ITINERARIES = cached_itineraries
    return _ITINERARIES


def build_itineraries(
    schedule: dict | None,
    origin: str,
    destination: str,
    day,
    transfer_min: int = 3,
    now: datetime | None = None,
    window: str = "rest_of_day",
    line_names: dict | None = None,
    limit: int | None = None,
    enforce_transfer: bool = True,
    through: bool = True,
    by_depart: bool = False,
) -> list[dict]:
    """Direct trains, then one legal transfer. Uses the precomputed timetable index."""
    return _itinerary_fn()(
        schedule,
        origin,
        destination,
        day,
        transfer_min,
        now,
        window,
        line_names,
        limit,
        enforce_transfer,
        through,
        by_depart,
    )


def build_itineraries_scan(
    schedule: dict | None,
    origin: str,
    destination: str,
    day,
    transfer_min: int = 3,
    now: datetime | None = None,
    window: str = "rest_of_day",
    line_names: dict | None = None,
) -> list[dict]:
    """Direct trains first. Otherwise one transfer at a station both lines serve."""
    names = line_names or {}
    paths = train_paths(schedule, day)
    calling: dict[str, list] = {}
    for train, path in paths.items():
        for stop in path:
            calling.setdefault(station_key(stop["station"]), []).append((train, stop))
    shared = {station_key(name) for name in shared_transfer_stations(schedule, origin, destination)}
    rows: list[dict] = []
    for train, path in paths.items():
        start = _path_index(path, origin)
        if start is None:
            continue
        finish = _path_index(path, destination)
        depart = path[start]["when"]
        line = str(names.get(path[start]["line"], path[start]["line"]) or path[start]["line"])
        terminal = str(path[-1].get("dest") or path[-1]["station"])
        if finish is not None and finish > start:
            arrive = path[finish]["when"]
            rows.append(
                {
                    "train": train,
                    "line": line,
                    "destination": terminal,
                    "depart_sched": _iso(depart),
                    "depart_est": _iso(depart),
                    "arrive_sched": _iso(arrive),
                    "arrive_est": _iso(arrive),
                    "delay_min": None,
                    "direct": True,
                    "connection": None,
                    "live": False,
                    "source": "timetable",
                }
            )
            continue
        best = None
        for stop in path[start + 1 :]:
            if shared and station_key(stop["station"]) not in shared:
                continue
            for other, other_stop in calling.get(station_key(stop["station"]), []):
                if other == train or other_stop["when"] < stop["when"]:
                    continue
                other_path = paths.get(other) or []
                here = _path_index(other_path, other_stop["station"])
                there = _path_index(other_path, destination)
                if here is None or there is None or there <= here:
                    continue
                final = other_path[there]["when"]
                other_line = str(names.get(other_stop["line"], other_stop["line"]) or other_stop["line"])
                link = _link(
                    other_stop["station"],
                    other,
                    other_line,
                    stop["when"],
                    other_stop["when"],
                    final,
                    transfer_min,
                    destination,
                )
                if best is None or final < best[0]:
                    best = (final, depart, line, terminal, link)
        if best:
            final, depart, line, terminal, link = best
            rows.append(
                {
                    "train": train,
                    "line": line,
                    "destination": terminal,
                    "depart_sched": _iso(depart),
                    "depart_est": _iso(depart),
                    "arrive_sched": link["arrive_final_sched"],
                    "arrive_est": link["arrive_final_est"],
                    "delay_min": None,
                    "direct": False,
                    "connection": link,
                    "live": False,
                    "source": "timetable",
                }
            )
    rows.sort(key=lambda item: (0 if item.get("direct") else 1, item.get("depart_sched") or ""))
    if window == "rest_of_day" and now is not None:
        base = now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)
        kept = []
        for row in rows:
            depart = _parse_iso(row.get("depart_sched"))
            if depart is not None and depart >= base:
                kept.append(row)
        rows = kept
    return rows


def present_row(row: dict, now: datetime | None = None) -> dict:
    delay = row.get("delay_min")
    if delay is None and row.get("late_min") is not None:
        delay = row.get("late_min")
    link = row.get("connection") if isinstance(row.get("connection"), dict) else None
    if link is None and isinstance(row.get("transfer"), dict):
        link = row.get("transfer")
    transfer = None
    if link and not row.get("direct", True):
        transfer = _blank_connection()
        transfer.update({key: link.get(key) for key in transfer})
        for key in ("arrive_sched", "arrive_est", "depart_sched", "depart_est", "arrive_final_sched", "arrive_final_est"):
            transfer[key] = link.get(key)
        transfer["station"] = link.get("station")
        transfer["train"] = link.get("train")
        transfer["line"] = link.get("line")
        transfer["wait_min"] = link.get("wait_min")
        transfer["at_risk"] = bool(link.get("at_risk"))
        transfer["track"] = link.get("track")
        transfer["platform"] = link.get("platform")
        transfer["delay_min"] = link.get("delay_min")
        for extra in ("service_type", "stops", "stops_count", "skipped", "train_number"):
            if link.get(extra) not in (None, "", []):
                transfer[extra] = link.get(extra)
    direct = bool(row.get("direct", transfer is None)) or bool(row.get("through"))
    if direct:
        transfer = None
    lean = None
    if transfer is not None:
        lean = {
            "station": transfer.get("station"),
            "train": transfer.get("train"),
            "wait_min": transfer.get("wait_min"),
            "at_risk": bool(transfer.get("at_risk")),
        }
    depart_sched = row.get("depart_sched")
    arrive_sched = row.get("arrive_sched")
    depart_est = row.get("depart_est")
    arrive_est = row.get("arrive_est")
    if depart_est in (None, "", depart_sched):
        depart_est = None
    if arrive_est in (None, "", arrive_sched):
        arrive_est = None
    depart = _parse_iso(depart_est or depart_sched)
    minutes = row.get("minutes")
    if minutes is None and depart is not None and now is not None:
        base = now.astimezone(depart.tzinfo) if now.tzinfo else now
        minutes = int(round((depart - base).total_seconds() / 60))

    def _empty(value):
        return None if value in ("",) else value

    shaped = {key: None for key in _ROW_KEYS}
    shaped.update(
        {
            "train": str(row.get("train") or "") or None,
            "train_number": row.get("train_number") or bare_train(row.get("train")) or None,
            "line": str(row.get("line") or "") or None,
            "destination": row.get("destination") or None,
            "depart_sched": depart_sched,
            "depart_est": depart_est,
            "arrive_sched": arrive_sched,
            "arrive_est": arrive_est,
            "late_min": delay,
            "delay_min": delay,
            "minutes": minutes,
            "track": _empty(row.get("track")),
            "platform": _empty(row.get("platform")),
            "track_changed": bool(row.get("track_changed")),
            "direct": direct,
            "through": bool(row.get("through")),
            "transfer": transfer,
            "connection": lean,
            "live": bool(row.get("live")),
            "service_type": row.get("service_type") or "",
            "stops_count": row.get("stops_count"),
            "stops": row.get("stops") or [],
            "skipped": row.get("skipped") or [],
        }
    )
    return shaped


def overlay_live(rows: list[dict], live_rows: list[dict], now: datetime, window_min: int = LIVE_WINDOW_MIN) -> list[dict]:
    live_by = {str(item.get("train")): item for item in live_rows if item.get("train")}
    base = now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)
    out = []
    for row in rows:
        copy = dict(row)
        depart = _parse_iso(copy.get("depart_sched") or copy.get("depart_est"))
        within = depart is not None and 0 <= (depart - base).total_seconds() / 60 <= window_min
        live = live_by.get(str(copy.get("train"))) if within else None
        if live:
            if live.get("delay_min") is not None:
                copy["delay_min"] = live.get("delay_min")
            for key in ("depart_est", "arrive_est", "track", "platform"):
                if live.get(key) is not None:
                    copy[key] = live[key]
            if live.get("track_changed") is not None:
                copy["track_changed"] = live.get("track_changed")
            if isinstance(live.get("connection"), dict):
                merged = dict(copy.get("connection") or {})
                for key, value in live["connection"].items():
                    if value not in (None, ""):
                        merged[key] = value
                copy["connection"] = merged
                copy["direct"] = False
            copy["live"] = True
        else:
            copy["live"] = False
        out.append(present_row(copy, now))
    return out


def trim_published(rows: list[dict] | None, keep_stops: int = 4) -> list[dict]:
    """State attributes keep stops on the first few rows only. The websocket has the rest."""
    out = []
    for index, row in enumerate(rows or []):
        item = dict(row)
        if index >= keep_stops:
            item["stops"] = []
            link = item.get("transfer")
            if isinstance(link, dict):
                link = dict(link)
                link["stops"] = []
                item["transfer"] = link
        out.append(item)
    return out


def merge_nta(live_rows: list[dict], schedule_rows: list[dict], count: int, now: datetime) -> list[dict]:
    out = [present_row(dict(row, live=True, source="nta"), now) for row in live_rows]
    seen = {str(row.get("train")) for row in out}
    for row in schedule_rows:
        if len(out) >= count:
            break
        if str(row.get("train")) in seen:
            continue
        seen.add(str(row.get("train")))
        out.append(present_row(row, now))
    return out[: max(1, count)] if count else out


def suggest_itinerary(
    rows: list[dict],
    event_start: datetime | None,
    buffer_min: int,
    egress_walk_min: int = 0,
) -> dict | None:
    """Latest train that still arrives before the event, after buffer and the walk."""
    if event_start is None:
        return None
    try:
        extra = int(egress_walk_min or 0)
    except (TypeError, ValueError):
        extra = 0
    if extra < 0:
        extra = 0
    deadline = event_start - timedelta(minutes=int(buffer_min or 0) + extra)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=NY)
    best = None
    best_arrive = None
    for row in rows:
        arrive = _parse_iso(row.get("arrive_est") or row.get("arrive_sched"))
        if arrive is None or arrive > deadline:
            continue
        if best_arrive is None or arrive > best_arrive:
            best, best_arrive = row, arrive
    return best


def suggestion_fields(
    rows: list[dict] | None,
    event: dict | None,
    *,
    buffer_min: int = 0,
    egress_walk_min: int = 0,
    walk_minutes: int = 0,
    destination: str | None = None,
    destination_source: str | None = None,
    distance_m: object = None,
    empty_service: bool = False,
) -> dict:
    """Arrive-by details for day trains. Existing train rows are left to the caller."""
    start = _event_start(event) if isinstance(event, dict) else None
    try:
        egress = max(0, int(egress_walk_min or 0))
    except (TypeError, ValueError):
        egress = 0
    deadline = None
    if start is not None:
        deadline = start - timedelta(minutes=int(buffer_min or 0) + egress)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=NY)
    located = destination_source in {"manual", "entity", "calendar"}
    reason = "ok"
    suggested = None
    if not isinstance(event, dict) or start is None:
        reason = "no_event"
    elif not _has_location(event):
        reason = "no_location"
    elif not destination or not located:
        reason = "no_station"
    elif empty_service or not rows:
        reason = "no_service"
    else:
        suggested = suggest_itinerary(rows, start, buffer_min, egress)
        if suggested is None:
            reason = "none_in_time"
    leave_by = None
    spare = None
    if suggested is not None and deadline is not None:
        depart = _parse_iso(suggested.get("depart_est") or suggested.get("depart_sched"))
        arrive = _parse_iso(suggested.get("arrive_est") or suggested.get("arrive_sched"))
        if depart is not None:
            try:
                home_walk = max(0, int(walk_minutes or 0))
            except (TypeError, ValueError):
                home_walk = 0
            leave_by = depart - timedelta(minutes=home_walk)
        if arrive is not None:
            spare = int(round((deadline - arrive).total_seconds() / 60))
    return {
        "suggested": suggested,
        "suggested_train": None if not suggested else suggested.get("train"),
        "egress_walk_min": egress,
        "destination_distance_m": None if distance_m is None else distance_m,
        "arrive_deadline": None if deadline is None else deadline.isoformat(),
        "leave_by": None if leave_by is None else leave_by.isoformat(),
        "spare_min": spare,
        "suggest_reason": reason,
    }


def parse_plan_time(value: object, now: datetime | None = None) -> datetime | None:
    """ISO datetime, or HH:MM on today's New York date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=NY)
    text = str(value).strip()
    if not text:
        return None
    clock = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if clock:
        hour, minute = int(clock.group(1)), int(clock.group(2))
        if hour > 23 or minute > 59:
            return None
        base = now.astimezone(NY) if isinstance(now, datetime) and now.tzinfo else datetime.now(NY)
        if isinstance(now, datetime) and now.tzinfo is None:
            base = now.replace(tzinfo=NY)
        return base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return _parse_iso(text)


def _compact_plan_row(row: dict, now: datetime | None) -> dict:
    link = row.get("transfer") if isinstance(row.get("transfer"), dict) else None
    if link is None and isinstance(row.get("connection"), dict):
        link = row["connection"]
    direct = bool(row.get("direct", link is None))
    depart = row.get("depart_est") or row.get("depart_sched")
    arrive = row.get("arrive_est") or row.get("arrive_sched")
    legs = [
        {
            "train": row.get("train"),
            "line": row.get("line"),
            "depart": depart,
            "arrive": (link or {}).get("arrive_sched") if link and not direct else arrive,
        }
    ]
    if link and not direct:
        legs.append(
            {
                "train": link.get("train"),
                "line": link.get("line"),
                "depart": link.get("depart_est") or link.get("depart_sched"),
                "arrive": link.get("arrive_final_est") or link.get("arrive_final_sched") or arrive,
            }
        )
    depart_at = _parse_iso(depart)
    minutes = row.get("minutes")
    if minutes is None and depart_at is not None and now is not None:
        base = now.astimezone(depart_at.tzinfo) if now.tzinfo else now.replace(tzinfo=depart_at.tzinfo)
        minutes = int(round((depart_at - base).total_seconds() / 60))
    delay = row.get("delay_min")
    if delay is None:
        delay = row.get("late_min")
    return {
        "train": None if not row.get("train") else str(row.get("train")),
        "depart": depart,
        "arrive": arrive,
        "line": row.get("line"),
        "transfer": None if direct else link,
        "legs": legs,
        "minutes": minutes,
        "live": bool(row.get("live")),
        "delay": delay,
        "suggested": bool(row.get("suggested")),
        "train_number": row.get("train_number") or bare_train(row.get("train")) or None,
        "service_type": row.get("service_type") or "",
        "stops_count": row.get("stops_count"),
        "stops": row.get("stops") or [],
        "skipped": row.get("skipped") or [],
        "through": bool(row.get("through")),
        "direct": bool(row.get("direct", link is None)),
    }


def _index_for(schedule, day):
    return _itinerary_fn().__globals__["index_for"](schedule, day)


def _leg2_calls_at_origin(idx, origin_key: str, link: dict, after: datetime | None) -> bool:
    train = str(link.get("train") or "")
    if not train or not origin_key:
        return False
    names = []
    if train in getattr(idx, "trains", {}):
        names.append(train)
    for other in idx.by_number.get(bare_train(train), []):
        if other not in names:
            names.append(other)
    for name in names:
        pos = (idx.pos.get(name) or {}).get(origin_key)
        if pos is None:
            continue
        when = idx.trains[name][pos]["when"]
        if after is None or when >= after:
            return True
    return False


def _via_is_behind(idx, origin_key: str, dest_key: str, via_key: str) -> bool:
    if not via_key or via_key in {origin_key, dest_key}:
        return False
    ahead = False
    behind = False
    for pos in idx.pos.values():
        origin = pos.get(origin_key)
        dest = pos.get(dest_key)
        via = pos.get(via_key)
        if origin is None or dest is None or via is None or dest <= origin:
            continue
        if origin < via < dest:
            ahead = True
        elif via < origin:
            behind = True
    return behind and not ahead


def _drop_dominated(rows: list[dict]) -> list[dict]:
    parsed = []
    for row in rows:
        depart = _parse_iso(row.get("depart_sched") or row.get("depart_est"))
        arrive = _parse_iso(row.get("arrive_sched") or row.get("arrive_est"))
        parsed.append((depart, arrive, row))
    drop: set[int] = set()
    for index, (depart, arrive, row) in enumerate(parsed):
        if depart is None or arrive is None:
            continue
        for other_index, (other_depart, other_arrive, other) in enumerate(parsed):
            if index == other_index or other_depart is None or other_arrive is None:
                continue
            if other_depart < depart or other_arrive > arrive:
                continue
            same = other_depart == depart and other_arrive == arrive
            if same:
                if other.get("direct") and not row.get("direct"):
                    drop.add(index)
                elif row.get("direct") and not other.get("direct"):
                    drop.add(other_index)
                elif index > other_index:
                    drop.add(index)
                continue
            if other_arrive == arrive:
                continue
            drop.add(index)
            break
    return [row for index, row in enumerate(rows) if index not in drop]


def prune_itineraries(
    rows: list[dict],
    schedule: dict | None,
    origin: str,
    destination: str,
    day,
    after: datetime | None = None,
) -> list[dict]:
    """Drop transfers a rider would not take, before the result is cut to count."""
    if not rows:
        return []
    idx = None
    if isinstance(schedule, dict) and schedule.get("stations") and day is not None:
        try:
            idx = _index_for(schedule, day)
        except Exception:
            idx = None
    origin_key = station_key(origin)
    dest_key = station_key(destination)
    kept = []
    for row in rows:
        link = row.get("connection") if isinstance(row.get("connection"), dict) else None
        if link is None and isinstance(row.get("transfer"), dict):
            link = row.get("transfer")
        direct = bool(row.get("direct")) or bool(row.get("through")) or not isinstance(link, dict)
        if not direct and idx is not None and after is not None:
            if _leg2_calls_at_origin(idx, origin_key, link, after):
                continue
            if _via_is_behind(idx, origin_key, dest_key, station_key(link.get("station"))):
                continue
        kept.append(row)
    kept = _drop_dominated(kept)
    kept.sort(key=lambda item: (item.get("depart_sched") or "", 0 if item.get("direct") else 1))
    return kept


def plan_trips(
    schedule: dict | None,
    origin: str,
    destination: str,
    *,
    after: datetime | None = None,
    arrive_by: datetime | None = None,
    count: int = 8,
    transfer_min: int = 3,
    day: date | None = None,
    now: datetime | None = None,
    live_rows: list[dict] | None = None,
) -> dict:
    """Read-only itineraries. `after` rolls to the next day that actually has trains."""
    try:
        limit = int(count or 8)
    except (TypeError, ValueError):
        limit = 8
    limit = min(20, max(1, limit))
    if day is None:
        if isinstance(after, datetime):
            day = (after.astimezone(NY) if after.tzinfo else after.replace(tzinfo=NY)).date()
        elif isinstance(arrive_by, datetime):
            day = (arrive_by.astimezone(NY) if arrive_by.tzinfo else arrive_by.replace(tzinfo=NY)).date()
        elif isinstance(now, datetime):
            day = (now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)).date()
        else:
            day = datetime.now(NY).date()

    def on(one_day: date, depart_after: datetime | None = None, capped: bool = False) -> list[dict]:
        wide = None if not capped else max(limit * 4, 16)
        return build_itineraries(
            schedule,
            origin,
            destination,
            one_day,
            transfer_min=transfer_min,
            now=depart_after,
            window="rest_of_day" if depart_after is not None else "today",
            limit=wide,
            by_depart=capped,
        )

    def useful(rows: list[dict], one_day: date, depart_after: datetime | None) -> list[dict]:
        return prune_itineraries(rows, schedule, origin, destination, one_day, depart_after)

    chosen = day
    rows: list[dict] = []
    if after is not None:
        base = after.astimezone(NY) if after.tzinfo else after.replace(tzinfo=NY)
        rows = useful(on(chosen, base, True), chosen, base)
        if not rows:
            for offset in range(1, 8):
                trial_day = day + timedelta(days=offset)
                trial = useful(on(trial_day, capped=True), trial_day, None)
                if trial:
                    chosen = trial_day
                    rows = trial
                    break
        rows = rows[:limit]
    elif arrive_by is not None:
        base = arrive_by.astimezone(NY) if arrive_by.tzinfo else arrive_by.replace(tzinfo=NY)
        rows = useful(on(chosen), chosen, None)
        kept = []
        for row in rows:
            arrive = _parse_iso(row.get("arrive_est") or row.get("arrive_sched"))
            if arrive is not None and arrive <= base:
                kept.append(row)
        kept.sort(key=lambda item: item.get("arrive_sched") or "", reverse=True)
        rows = kept[:limit]
        if rows:
            rows[0] = dict(rows[0], suggested=True)
    else:
        rows = useful(on(chosen, capped=True), chosen, None)[:limit]
    if live_rows is not None and now is not None:
        marked = {str(row.get("train")): bool(row.get("suggested")) for row in rows}
        overlaid = overlay_live(rows, live_rows, now, LIVE_WINDOW_MIN)
        rows = []
        for row in overlaid:
            row = dict(row)
            if marked.get(str(row.get("train"))):
                row["suggested"] = True
            rows.append(row)
    compact = [_compact_plan_row(row, now) for row in rows]
    suggested = next((row.get("train") for row in compact if row.get("suggested")), None)
    return {
        "origin": origin,
        "destination": destination,
        "day": chosen.isoformat(),
        "rows": compact,
        "suggested_train": suggested,
    }


def _planning_names(schedule: dict | None, names: list[str] | None) -> tuple[list[str], list[str]]:
    stations: list[str] = []
    pack = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    if isinstance(pack, dict):
        stations = [str(name) for name in pack if str(name or "").strip()]
    pool: list[str] = []
    seen: set[str] = set()
    for name in stations + list(names or []):
        text = str(name or "").strip()
        key = station_key(text)
        if text and key and key not in seen:
            seen.add(key)
            pool.append(text)
    return pool, stations


def plan_query(
    schedule: dict | None,
    names: list[str],
    *,
    origin: object,
    destination: object = None,
    home: str | None = None,
    after: object = None,
    arrive_by: object = None,
    count: int = 8,
    transfer_min: int = 3,
    now: datetime | None = None,
    live_rows: list[dict] | None = None,
) -> dict:
    """Match station names and plan. Does not write rider state."""
    pool, schedule_names = _planning_names(schedule, names)
    matched = match_station(origin, pool, schedule_names)
    if not matched:
        return {"error": "not_found"}
    dest_name = None
    if str(destination or "").strip():
        dest_name = match_station(destination, pool, schedule_names)
        if not dest_name:
            return {"error": "not_found"}
    else:
        dest_name = match_station(home, pool, schedule_names) or (
            str(home).strip() if str(home or "").strip() else None
        )
    if not dest_name:
        return {"error": "not_found"}
    after_at = parse_plan_time(after, now)
    arrive_at = parse_plan_time(arrive_by, now)
    planned = plan_trips(
        schedule,
        matched,
        dest_name,
        after=after_at,
        arrive_by=arrive_at,
        count=count,
        transfer_min=transfer_min,
        now=now,
        live_rows=live_rows,
    )
    planned["after"] = None if after_at is None else after_at.isoformat()
    planned["arrive_by"] = None if arrive_at is None else arrive_at.isoformat()
    planned["matched_origin"] = matched
    planned["matched_destination"] = dest_name
    planned["origin"] = matched
    planned["destination"] = dest_name
    return planned


def migrate_options(data: dict | None, options: dict | None) -> dict:
    """Seed home and city stations. Leave configured trips and their ids alone."""
    data = dict(data or {})
    out = dict(options or {})
    if not str(out.get("home_station") or "").strip():
        station = str(data.get("station") or out.get("station") or "").strip()
        if station:
            out["home_station"] = station
    if not str(out.get("default_city_station") or "").strip():
        city = str(out.get("destination") or data.get("destination") or "").strip()
        if city:
            out["default_city_station"] = city
    if "trips" in (options or {}):
        out["trips"] = options["trips"]
    return out


def round_coord(value: object) -> float | None:
    number = _num(value)
    if number is None:
        return None
    return round(number, 2)


def _csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _calendar_mask(row: dict) -> int:
    bits = {
        "sunday": 1,
        "monday": 2,
        "tuesday": 4,
        "wednesday": 8,
        "thursday": 16,
        "friday": 32,
        "saturday": 64,
    }
    mask = 0
    for name, bit in bits.items():
        if str(row.get(name) or "0").strip() in {"1", "true", "yes"}:
            mask |= bit
    return mask or 127


def gtfs_tables_to_schedule(files: dict[str, str]) -> dict:
    """Turn the rail GTFS text files into the bundled timetable shape."""
    stops = {row.get("stop_id"): row.get("stop_name") or row.get("stop_id") for row in _csv(files.get("stops") or "")}
    services = {row.get("service_id"): _calendar_mask(row) for row in _csv(files.get("calendar") or "")}
    trips = {row.get("trip_id"): row for row in _csv(files.get("trips") or "")}
    stations: dict[str, dict] = {}
    for row in _csv(files.get("stop_times") or ""):
        trip = trips.get(row.get("trip_id") or "")
        if not trip:
            continue
        name = stops.get(row.get("stop_id") or "")
        clock = str(row.get("arrival_time") or row.get("departure_time") or "")
        parts = clock.split(":")
        if not name or len(parts) < 2:
            continue
        try:
            hour, minute = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        extra = hour // 24
        hour %= 24
        stamp = f"{hour:02d}:{minute:02d}"
        train = str(trip.get("trip_short_name") or trip.get("trip_id") or "").strip()
        pack = stations.setdefault(str(name), {"N": [], "S": []})
        pack["S"].append(
            {
                "t": stamp,
                "d": str(trip.get("trip_headsign") or ""),
                "n": train,
                "line": str(trip.get("route_id") or ""),
                "days": services.get(trip.get("service_id") or "", 127),
                "seq": int(row.get("stop_sequence") or 0) + extra * 10000,
            }
        )
    until = ""
    info = _csv(files.get("feed_info") or "")
    if info:
        until = re.sub(r"\D", "", str(info[0].get("feed_end_date") or ""))[:8]
    return {"feed": "gtfs", "validUntil": until, "stations": stations}
