"""Origin-to-destination trips. No Home Assistant imports."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

# NextToArrive rejects some names the rest of SEPTA uses.
_NTA_ALIASES = {
    "gray 30th street": "30th Street Station",
    "30th street gray": "30th Street Station",
    "30th street": "30th Street Station",
    "william h gray iii 30th street": "30th Street Station",
    "9th street": "9th St",
    "ninth street": "9th St",
    "fern rock": "Fern Rock Transportation Center",
    "fern rock tc": "Fern Rock Transportation Center",
    "norristown": "Norristown Transportation Center",
    "norristown tc": "Norristown Transportation Center",
    "jefferson": "Jefferson Station",
    "market east": "Jefferson Station",
    "suburban": "Suburban Station",
    "penn medicine": "Penn Medicine Station",
    "temple": "Temple University",
    "trenton": "Trenton Transit Center",
}


def station_key(name: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower())
    text = re.sub(r"\bstation\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def nta_station(name: object) -> str:
    """Name NextToArrive will accept. Unknown names are sent through unchanged."""
    raw = str(name or "").strip()
    key = station_key(raw)
    if key in _NTA_ALIASES:
        return _NTA_ALIASES[key]
    return raw


def clean_trips(raw: object) -> list[dict]:
    try:
        from .const import DEFAULT_TRIP_COUNT, MAX_TRIP_COUNT, MAX_TRIPS
    except ImportError:
        MAX_TRIPS = 20
        MAX_TRIP_COUNT = 20
        DEFAULT_TRIP_COUNT = 4
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.splitlines() if part.strip()]
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str) and ">" in item:
            origin, _, dest = item.partition(">")
            item = {"origin": origin.strip(), "destination": dest.strip()}
        if not isinstance(item, dict):
            continue
        origin = str(item.get("origin") or "").strip()[:80]
        dest = str(item.get("destination") or "").strip()[:80]
        if not origin or not dest or station_key(origin) == station_key(dest):
            continue
        tid = re.sub(r"[^a-z0-9]", "", str(item.get("id") or "").lower())[:12]
        if not tid:
            tid = re.sub(r"[^a-z0-9]", "", station_key(origin) + station_key(dest))[:12]
        if not tid or tid in seen:
            continue
        seen.add(tid)
        try:
            count = int(item.get("count") if item.get("count") not in (None, "") else DEFAULT_TRIP_COUNT)
        except (TypeError, ValueError):
            count = DEFAULT_TRIP_COUNT
        count = min(MAX_TRIP_COUNT, max(1, count))
        label = str(item.get("label") or "").strip()[:40]
        try:
            transfer = int(item.get("transfer_min") if item.get("transfer_min") not in (None, "") else 3)
        except (TypeError, ValueError):
            transfer = 3
        transfer = min(30, max(0, transfer))
        out.append(
            {
                "id": tid,
                "origin": origin,
                "destination": dest,
                "count": count,
                "label": label,
                "day": bool(item.get("day")),
                "transfer_min": transfer,
            }
        )
        if len(out) >= MAX_TRIPS:
            break
    return out


def trip_ids(entry_id: str, trip_id: str) -> tuple[str, str]:
    """Unique id and entity id. Neither includes the station names."""
    key = re.sub(r"[^a-z0-9]", "", str(trip_id or "").lower())[:12]
    return f"{entry_id}_trip_{key}", f"sensor.septa_trip_{key}"


def parse_delay_min(text: object) -> int | None:
    raw = str(text or "").strip().lower()
    if not raw:
        return None
    if "on time" in raw or raw in {"ontime", "0"}:
        return 0
    match = re.search(r"-?\d+", raw)
    if not match:
        return None
    return int(match.group(0))


def _clock(text: object, now: datetime) -> datetime | None:
    raw = str(text or "").strip().upper().replace(" ", "")
    match = re.match(r"^(\d{1,2}):(\d{2})(AM|PM)?$", raw)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    ap = match.group(3)
    if ap == "PM" and hour < 12:
        hour += 12
    if ap == "AM" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    base = now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)
    when = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if when < base - timedelta(hours=3):
        when += timedelta(days=1)
    return when


def _iso(when: datetime | None) -> str | None:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=NY)
    return when.astimezone(NY).isoformat()


def _direct(item: dict) -> bool:
    flag = str(item.get("isdirect") if item.get("isdirect") is not None else "").strip().lower()
    if flag in {"true", "y", "yes", "1"}:
        return True
    if flag in {"false", "n", "no", "0"}:
        return False
    term = str(item.get("term_train") or "").strip()
    orig = str(item.get("orig_train") or "").strip()
    return not term or term == orig


def _connection(item: dict, now: datetime, transfer_min: int = 3) -> dict | None:
    if _direct(item):
        return None
    origin_delay = parse_delay_min(item.get("orig_delay"))
    if origin_delay is None:
        origin_delay = 0
    term_delay = parse_delay_min(item.get("term_delay"))
    if term_delay is None:
        term_delay = 0
    arrive = _clock(item.get("orig_arrival_time"), now)
    arrive_est = None if arrive is None else arrive + timedelta(minutes=origin_delay)
    depart = _clock(item.get("term_depart_time") or item.get("term_departure_time"), now)
    depart_est = None if depart is None else depart + timedelta(minutes=term_delay)
    final = _clock(item.get("term_arrival_time"), now)
    final_est = None if final is None else final + timedelta(minutes=term_delay)
    wait = None
    if arrive_est is not None and depart_est is not None:
        wait = int(round((depart_est - arrive_est).total_seconds() / 60))
    station = str(item.get("Connection") or item.get("connection") or item.get("term_station") or "").strip()
    return {
        "station": station,
        "train": str(item.get("term_train") or "").strip(),
        "line": str(item.get("term_line") or "").strip(),
        "arrive_sched": _iso(arrive),
        "arrive_est": _iso(arrive_est),
        "depart_sched": _iso(depart),
        "depart_est": _iso(depart_est),
        "arrive_final_sched": _iso(final),
        "arrive_final_est": _iso(final_est),
        "delay_min": term_delay,
        "wait_min": wait,
        "at_risk": bool(wait is not None and wait < transfer_min),
        "depart": _iso(depart),
        "track": None,
        "platform": None,
        "track_changed": False,
    }


def _place() -> dict:
    return {"track": None, "platform": None, "track_changed": False}


def parse_next_to_arrive(
    raw: object, now: datetime, limit: int = 4, transfer_min: int = 3
) -> tuple[list[dict], str | None]:
    """Turn a NextToArrive payload into trip rows. A non-list is a rejection."""
    if isinstance(raw, list):
        rows = [item for item in raw if isinstance(item, dict)]
    else:
        message = ""
        if isinstance(raw, dict):
            message = str(raw.get("error") or raw.get("message") or raw.get("Error") or "").strip()
        elif isinstance(raw, str):
            message = raw.strip()
        return [], message or "NextToArrive rejected the station pair"
    out: list[dict] = []
    for item in rows:
        delay = parse_delay_min(item.get("orig_delay"))
        if delay is None:
            delay = 0
        term_delay = parse_delay_min(item.get("term_delay"))
        if term_delay is None:
            term_delay = 0
        direct = _direct(item)
        depart = _clock(item.get("orig_departure_time"), now)
        if direct:
            arrive = _clock(item.get("orig_arrival_time"), now)
            arrive_delay = delay
        else:
            arrive = _clock(item.get("term_arrival_time"), now)
            arrive_delay = term_delay
        depart_est = None if depart is None else depart + timedelta(minutes=delay)
        arrive_est = None if arrive is None else arrive + timedelta(minutes=arrive_delay)
        minutes = None
        if depart_est is not None:
            minutes = int(round((depart_est - now.astimezone(depart_est.tzinfo)).total_seconds() / 60))
        if minutes is not None and minutes < 0:
            continue
        out.append(
            {
                "train": str(item.get("orig_train") or "").strip(),
                "line": str(item.get("orig_line") or "").strip(),
                "depart_sched": _iso(depart),
                "depart_est": _iso(depart_est),
                "arrive_sched": _iso(arrive),
                "arrive_est": _iso(arrive_est),
                "delay_min": delay,
                "minutes": minutes,
                "direct": direct,
                "connection": _connection(item, now, transfer_min),
                **_place(),
            }
        )
        if len(out) >= max(1, limit):
            break
    return out, None


def _weekday_bit(day) -> int:
    return 1 << ((day.weekday() + 1) % 7)


def _hhmm(day, clock: str):
    try:
        hour, minute = str(clock).split(":")
        return datetime(day.year, day.month, day.day, int(hour), int(minute), tzinfo=NY)
    except (TypeError, ValueError):
        return None


def _station_rows(schedule: dict | None, name: str) -> list[tuple[str, dict]]:
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    if not isinstance(stations, dict):
        return []
    want = station_key(name)
    pack = None
    for key, value in stations.items():
        if station_key(key) == want:
            pack = value
            break
    if pack is None:
        for key, value in stations.items():
            got = station_key(key)
            if want and (want in got or got in want):
                pack = value
                break
    if not isinstance(pack, dict):
        return []
    found: list[tuple[str, dict]] = []
    for direction in ("N", "S"):
        rows = pack.get(direction) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                found.append((direction, row))
    return found


def timetable_trips(
    schedule: dict | None,
    origin: str,
    destination: str,
    now: datetime,
    limit: int = 4,
    line_names: dict | None = None,
) -> list[dict]:
    """Direct trains that stop at both stations after now. delay_min stays null."""
    names = line_names or {}
    by_origin: dict[tuple, datetime] = {}
    origin_line: dict[tuple, str] = {}
    origin_train: dict[tuple, str] = {}
    base = now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)
    for offset in (0, 1):
        day = (base + timedelta(days=offset)).date()
        bit = _weekday_bit(day)
        for _direction, row in _station_rows(schedule, origin):
            days = int(row.get("days") or 0)
            if days and not (days & bit):
                continue
            train = str(row.get("n") or "").strip()
            when = _hhmm(day, str(row.get("t") or ""))
            if not train or when is None or when <= base:
                continue
            key = (day.isoformat(), train)
            if key not in by_origin or when < by_origin[key]:
                by_origin[key] = when
                code = str(row.get("line") or "")
                origin_line[key] = str(names.get(code, code))
                origin_train[key] = train
    arrivals: dict[tuple, datetime] = {}
    for offset in (0, 1):
        day = (base + timedelta(days=offset)).date()
        bit = _weekday_bit(day)
        for _direction, row in _station_rows(schedule, destination):
            days = int(row.get("days") or 0)
            if days and not (days & bit):
                continue
            train = str(row.get("n") or "").strip()
            when = _hhmm(day, str(row.get("t") or ""))
            if not train or when is None:
                continue
            key = (day.isoformat(), train)
            if key in by_origin and when > by_origin[key]:
                if key not in arrivals or when < arrivals[key]:
                    arrivals[key] = when
    ordered = sorted((by_origin[key], key) for key in arrivals)
    out: list[dict] = []
    for depart, key in ordered:
        arrive = arrivals[key]
        minutes = int(round((depart - base).total_seconds() / 60))
        if minutes < 0:
            continue
        out.append(
            {
                "train": origin_train[key],
                "line": origin_line[key],
                "depart_sched": _iso(depart),
                "depart_est": _iso(depart),
                "arrive_sched": _iso(arrive),
                "arrive_est": _iso(arrive),
                "delay_min": None,
                "minutes": minutes,
                "direct": True,
                "connection": None,
            }
        )
        if len(out) >= max(1, limit):
            break
    return out


DEFAULT_TRANSFER_STATIONS = (
    "Temple University",
    "Jefferson Station",
    "Suburban Station",
    "Gray 30th Street",
    "30th Street Station",
)


def station_in_schedule(schedule: dict | None, name: str) -> bool:
    return bool(_station_rows(schedule, name))


def _parse_iso(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=NY)
    return when.astimezone(NY)


def train_paths(schedule: dict | None, day) -> dict[str, list[dict]]:
    stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
    if not isinstance(stations, dict):
        return {}
    bit = _weekday_bit(day)
    paths: dict[str, list[dict]] = {}
    for name, pack in stations.items():
        if not isinstance(pack, dict):
            continue
        for direction in ("N", "S"):
            rows = pack.get(direction) or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                days = int(row.get("days") or 0)
                if days and not (days & bit):
                    continue
                train = str(row.get("n") or "").strip()
                when = _hhmm(day, str(row.get("t") or ""))
                if not train or when is None:
                    continue
                paths.setdefault(train, []).append(
                    {
                        "station": str(name),
                        "when": when,
                        "line": str(row.get("line") or ""),
                        "dest": str(row.get("d") or ""),
                    }
                )
    for train, stops in list(paths.items()):
        stops.sort(key=lambda item: item["when"])
        seen: set[str] = set()
        unique: list[dict] = []
        for stop in stops:
            key = station_key(stop["station"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(stop)
        paths[train] = unique
    return paths


def _path_index(path: list[dict], name: str) -> int | None:
    want = station_key(name)
    if not want:
        return None
    for index, stop in enumerate(path):
        if station_key(stop["station"]) == want:
            return index
    return None


def _line_name(code: str, names: dict) -> str:
    return str(names.get(code, code) or code)


def _timetable_connection(station, train, line, arrive, depart, final, transfer_min) -> dict:
    wait = int(round((depart - arrive).total_seconds() / 60))
    return {
        "station": station,
        "train": train,
        "line": line,
        "arrive_sched": _iso(arrive),
        "arrive_est": _iso(arrive),
        "depart_sched": _iso(depart),
        "depart_est": _iso(depart),
        "arrive_final_sched": _iso(final),
        "arrive_final_est": _iso(final),
        "delay_min": None,
        "wait_min": wait,
        "at_risk": wait < transfer_min,
        "depart": _iso(depart),
        **_place(),
    }


def _first_link(calling, paths, station, arrive, destination, transfer_min, skip_train, line_names):
    earliest = arrive + timedelta(minutes=transfer_min)
    found = []
    for train, stop in calling.get(station_key(station), []):
        if train == skip_train or stop["when"] < earliest:
            continue
        path = paths.get(train) or []
        here = _path_index(path, stop["station"])
        there = _path_index(path, destination)
        if here is None or there is None or there <= here:
            continue
        found.append((stop["when"], train, path[there]["when"], _line_name(stop["line"], line_names)))
    if not found:
        return None
    found.sort()
    depart, train, final, line = found[0]
    return _timetable_connection(station, train, line, arrive, depart, final, transfer_min)


def timetable_day(schedule, origin, destination, day, transfer_min=3, transfer_stations=None, line_names=None):
    names = line_names or {}
    paths = train_paths(schedule, day)
    calling: dict[str, list] = {}
    for train, path in paths.items():
        for stop in path:
            calling.setdefault(station_key(stop["station"]), []).append((train, stop))
    preferred = {station_key(item) for item in (transfer_stations or DEFAULT_TRANSFER_STATIONS)}
    rows = []
    for train, path in paths.items():
        start = _path_index(path, origin)
        if start is None:
            continue
        finish = _path_index(path, destination)
        depart = path[start]["when"]
        line = _line_name(path[start]["line"], names)
        if finish is not None and finish > start:
            arrive = path[finish]["when"]
            rows.append(
                {
                    "train": train,
                    "line": line,
                    "depart_sched": _iso(depart),
                    "depart_est": _iso(depart),
                    "arrive_sched": _iso(arrive),
                    "arrive_est": _iso(arrive),
                    "delay_min": None,
                    "minutes": None,
                    "direct": True,
                    "connection": None,
                    "source": "timetable",
                    **_place(),
                }
            )
            continue
        if not station_in_schedule(schedule, destination):
            continue
        after = path[start + 1 :]
        ordered = [stop for stop in after if station_key(stop["station"]) in preferred]
        ordered += [stop for stop in after if station_key(stop["station"]) not in preferred]
        chosen = None
        for stop in ordered:
            link = _first_link(calling, paths, stop["station"], stop["when"], destination, transfer_min, train, names)
            if link:
                chosen = link
                break
        if not chosen:
            continue
        rows.append(
            {
                "train": train,
                "line": line,
                "depart_sched": _iso(depart),
                "depart_est": _iso(depart),
                "arrive_sched": chosen["arrive_final_sched"],
                "arrive_est": chosen["arrive_final_est"],
                "delay_min": None,
                "minutes": None,
                "direct": False,
                "connection": chosen,
                "source": "timetable",
                **_place(),
            }
        )
    rows.sort(key=lambda item: item.get("depart_sched") or "")
    return rows


def merge_day(skeleton: list[dict], live_rows: list[dict], now: datetime) -> list[dict]:
    base = now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)
    merged: dict[str, dict] = {}
    for row in skeleton:
        train = str(row.get("train") or "")
        if train:
            merged[train] = dict(row)
    for live in live_rows:
        train = str(live.get("train") or "")
        if not train:
            continue
        if train in merged:
            row = merged[train]
            row["delay_min"] = live.get("delay_min")
            if live.get("depart_est"):
                row["depart_est"] = live["depart_est"]
            if live.get("arrive_est"):
                row["arrive_est"] = live["arrive_est"]
            if live.get("connection"):
                row["connection"] = live["connection"]
                row["direct"] = False
            elif live.get("direct"):
                row["connection"] = None
                row["direct"] = True
            row["source"] = "live"
        else:
            extra = dict(live)
            extra["source"] = "live"
            extra.setdefault("direct", True)
            merged[train] = extra
    rows = list(merged.values())
    rows.sort(key=lambda item: item.get("depart_sched") or item.get("depart_est") or "")
    for row in rows:
        depart = _parse_iso(row.get("depart_est") or row.get("depart_sched"))
        row["departed"] = bool(depart is not None and depart < base)
    if len(rows) > 40:
        cutoff = base - timedelta(hours=3)
        kept = []
        for row in rows:
            depart = _parse_iso(row.get("depart_sched") or row.get("depart_est"))
            if row.get("departed") and (depart is None or depart < cutoff):
                continue
            kept.append(row)
        rows = kept
    return rows


def _blank(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "na"}:
        return None
    return text


def places_from_arrivals(raw: object) -> dict[str, dict]:
    rows: list[dict] = []
    if isinstance(raw, list):
        rows = [item for item in raw if isinstance(item, dict)]
    elif isinstance(raw, dict):
        header = next(iter(raw), None)
        groups = raw.get(header) if header else None
        if isinstance(groups, list):
            for group in groups:
                if not isinstance(group, dict):
                    continue
                for key in ("Northbound", "Southbound"):
                    for item in group.get(key) or []:
                        if isinstance(item, dict):
                            rows.append(item)
        elif any(key in raw for key in ("train_id", "train", "orig_train")):
            rows = [raw]
    out: dict[str, dict] = {}
    for row in rows:
        train = str(row.get("train_id") or row.get("train") or row.get("orig_train") or "").strip()
        if not train:
            continue
        changed = _blank(row.get("track_change")) is not None or _blank(row.get("platform_change")) is not None
        out[train] = {
            "track": _blank(row.get("track")),
            "platform": _blank(row.get("platform")),
            "track_changed": changed,
        }
    return out


def apply_places(rows: list[dict], origin_places: dict | None, connection_places: dict | None = None) -> list[dict]:
    origin_places = origin_places or {}
    connection_places = connection_places or {}
    for row in rows:
        place = origin_places.get(str(row.get("train") or "")) or {}
        row["track"] = place.get("track")
        row["platform"] = place.get("platform")
        row["track_changed"] = bool(place.get("track_changed"))
        connection = row.get("connection")
        if isinstance(connection, dict):
            station_places = connection_places.get(station_key(connection.get("station"))) or {}
            link = station_places.get(str(connection.get("train") or "")) or {}
            connection["track"] = link.get("track")
            connection["platform"] = link.get("platform")
            connection["track_changed"] = bool(link.get("track_changed"))
    return rows


def delay_deltas(previous: dict, current: dict) -> list[dict]:
    events = []
    for train, new in current.items():
        if train not in previous or previous[train] is None or new is None:
            continue
        old = int(previous[train])
        now = int(new)
        if abs(now - old) >= 1:
            events.append({"train": str(train), "old_delay": old, "new_delay": now})
    return events


def track_deltas(previous: dict, current: dict, station: str) -> list[dict]:
    events = []
    for train, place in current.items():
        old = previous.get(train)
        if not isinstance(place, dict):
            continue
        if not isinstance(old, dict):
            if place.get("track_changed"):
                events.append(
                    {
                        "train": str(train),
                        "station": station,
                        "old_track": None,
                        "new_track": place.get("track"),
                        "old_platform": None,
                        "new_platform": place.get("platform"),
                    }
                )
            continue
        same = place.get("track") == old.get("track") and place.get("platform") == old.get("platform")
        flagged = bool(place.get("track_changed")) and not old.get("track_changed")
        if same and not flagged:
            continue
        events.append(
            {
                "train": str(train),
                "station": station,
                "old_track": old.get("track"),
                "new_track": place.get("track"),
                "old_platform": old.get("platform"),
                "new_platform": place.get("platform"),
            }
        )
    return events


def risk_edges(previous: dict, rows: list[dict]) -> list[dict]:
    events = []
    for row in rows:
        connection = row.get("connection") if isinstance(row.get("connection"), dict) else {}
        risk = bool(connection.get("at_risk"))
        train = str(row.get("train") or "")
        if risk and not previous.get(train):
            events.append(
                {
                    "train": train,
                    "station": connection.get("station"),
                    "wait_min": connection.get("wait_min"),
                    "connection_train": connection.get("train"),
                }
            )
    return events


def parse_expected_state(state: object) -> dict | None:
    text = str(state or "").strip()
    if not text or text.lower() in {"unknown", "unavailable", "none", "null"}:
        return None
    if text.startswith("{"):
        try:
            import json

            data = json.loads(text)
        except ValueError:
            return None
        if isinstance(data, dict) and str(data.get("train") or "").strip():
            return data
        return None
    return {"train": text}


def resolve_hint(service_hint: dict | None, entity_state: object) -> dict | None:
    if service_hint is not None:
        train = str(service_hint.get("train") or "").strip()
        return service_hint if train else None
    return parse_expected_state(entity_state)

