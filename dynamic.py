"""Per-rider Going Home and day-train planning. No Home Assistant imports."""

from __future__ import annotations

import csv
import io
import math
import re
from datetime import date, datetime, timedelta

try:
    from .trips import (
        NY,
        _NTA_ALIASES,
        _iso,
        _parse_iso,
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
    """Prefer a current bundled file, then a refreshed GTFS cache, else the stale file."""
    if isinstance(bundled, dict) and bundled.get("stations") and not schedule_expired(bundled, today):
        return bundled, "bundled"
    if isinstance(cached, dict) and cached.get("stations") and not schedule_expired(cached, today):
        return cached, "gtfs"
    if isinstance(bundled, dict) and bundled.get("stations"):
        return bundled, "expired"
    if isinstance(cached, dict) and cached.get("stations"):
        return cached, "expired"
    return {"stations": {}}, "missing"


def timetable_allowed(source: str) -> bool:
    return source in {"bundled", "gtfs"}


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
) -> dict:
    """manual, then nearest, then the usual city station, then the last origin."""
    stops = stops or []
    source = None
    name = None
    distance = None
    inaccurate = accuracy is not None and accuracy > max_accuracy
    if str(manual or "").strip():
        source, name = "manual", str(manual).strip()
    elif at_home:
        source, name = "home", home_station or None
    elif lat is not None and lon is not None and not inaccurate:
        hit = nearest_station(lat, lon, stops, radius_m, current=current, hysteresis_m=hysteresis_m)
        if hit:
            source, name = "nearest", hit["name"]
            distance = hit["distance_m"]
    if name is None and str(city_station or "").strip():
        source, name = "default", str(city_station).strip()
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
    }


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


def match_station(text: object, names: list[str]) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    key = station_key(raw)
    alias = _NTA_ALIASES.get(key)
    wanted = station_key(alias) if alias else key
    for name in names:
        if station_key(name) == wanted:
            return name
    if alias:
        return alias
    for name in names:
        got = station_key(name)
        if key and (key in got or got in key):
            return name
    return None


def _event_start(event: dict | None) -> datetime | None:
    if not isinstance(event, dict):
        return None
    return _parse_iso(event.get("start") or event.get("start_time"))


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

    def pack(station: str | None, source: str | None) -> dict:
        return {"destination": station, "destination_source": source, "event": kept}

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


def build_itineraries(
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
    depart = _parse_iso(row.get("depart_est") or row.get("depart_sched"))
    minutes = row.get("minutes")
    if minutes is None and depart is not None and now is not None:
        base = now.astimezone(depart.tzinfo) if now.tzinfo else now
        minutes = int(round((depart - base).total_seconds() / 60))
    shaped = {key: None for key in _ROW_KEYS}
    shaped.update(
        {
            "train": str(row.get("train") or "") or None,
            "line": str(row.get("line") or "") or None,
            "destination": row.get("destination") or None,
            "depart_sched": row.get("depart_sched"),
            "depart_est": row.get("depart_est"),
            "arrive_sched": row.get("arrive_sched"),
            "arrive_est": row.get("arrive_est"),
            "late_min": delay,
            "delay_min": delay,
            "minutes": minutes,
            "track": row.get("track"),
            "platform": row.get("platform"),
            "track_changed": bool(row.get("track_changed")),
            "direct": bool(row.get("direct", transfer is None)),
            "transfer": transfer,
            "connection": transfer,
            "live": bool(row.get("live")),
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
                copy["connection"] = live["connection"]
                copy["direct"] = False
            copy["live"] = True
        else:
            copy["live"] = False
        out.append(present_row(copy, now))
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


def suggest_itinerary(rows: list[dict], event_start: datetime | None, buffer_min: int) -> dict | None:
    if event_start is None:
        return None
    deadline = event_start - timedelta(minutes=int(buffer_min or 0))
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
