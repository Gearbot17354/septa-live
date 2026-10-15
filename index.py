"""One timetable index per schedule and service day. No Home Assistant imports."""

from __future__ import annotations

import bisect
import time
from collections import OrderedDict
from datetime import datetime, timedelta

try:
    from .trips import NY, _iso, _parse_iso, _weekday_bit, bare_train, clock_on, station_key
except ImportError:
    import importlib.util
    from pathlib import Path

    _spec = importlib.util.spec_from_file_location("septa_trips_index", Path(__file__).with_name("trips.py"))
    _trips = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_trips)
    NY = _trips.NY
    _iso = _trips._iso
    _parse_iso = _trips._parse_iso
    _weekday_bit = _trips._weekday_bit
    bare_train = _trips.bare_train
    clock_on = _trips.clock_on
    station_key = _trips.station_key

_INDEXES: OrderedDict = OrderedDict()
_SKELETONS: OrderedDict = OrderedDict()
_MAX_INDEXES = 8
_MAX_SKELETONS = 64
STATS = {
    "index_builds": 0,
    "index_ms": 0.0,
    "last_index_ms": 0.0,
    "skeleton_builds": 0,
    "last_skeleton_ms": 0.0,
    "hits": 0,
    "misses": 0,
    "trains": 0,
    "stops": 0,
}
_LAST_WARN = 0.0


def perf_snapshot() -> dict:
    return dict(STATS)


def note_slow(label: str, elapsed_ms: float) -> None:
    global _LAST_WARN
    if elapsed_ms < 100:
        return
    now = time.time()
    if now - _LAST_WARN < 60:
        return
    _LAST_WARN = now
    import logging

    logging.getLogger(__name__).warning("SEPTA %s took %.0f ms", label, elapsed_ms)


def index_for(schedule: dict | None, day) -> "TimetableIndex":
    if hasattr(day, "date") and not hasattr(day, "year"):
        day = day
    feed = ""
    until = ""
    if isinstance(schedule, dict):
        feed = str(schedule.get("feed") or "")
        until = str(schedule.get("validUntil") or "")
    key = (id(schedule), feed, until, getattr(day, "isoformat", lambda: str(day))())
    found = _INDEXES.get(key)
    if found is not None:
        _INDEXES.move_to_end(key)
        STATS["hits"] += 1
        return found
    STATS["misses"] += 1
    started = time.perf_counter()
    built = TimetableIndex(schedule, day)
    elapsed = (time.perf_counter() - started) * 1000
    built.build_ms = elapsed
    STATS["index_builds"] += 1
    STATS["index_ms"] += elapsed
    STATS["last_index_ms"] = round(elapsed, 2)
    STATS["trains"] = len(built.trains)
    STATS["stops"] = built.stop_rows
    note_slow("timetable index", elapsed)
    _INDEXES[key] = built
    while len(_INDEXES) > _MAX_INDEXES:
        _INDEXES.popitem(last=False)
    return built


def peek_index(schedule: dict | None, day) -> TimetableIndex | None:
    feed = str((schedule or {}).get("feed") or "") if isinstance(schedule, dict) else ""
    until = str((schedule or {}).get("validUntil") or "") if isinstance(schedule, dict) else ""
    key = (id(schedule), feed, until, getattr(day, "isoformat", lambda: str(day))())
    return _INDEXES.get(key)


def service_label(schedule: dict | None, day, train: str) -> str:
    idx = peek_index(schedule, day)
    if idx is None:
        return ""
    return idx.trip_service(str(train))


class TimetableIndex:
    def __init__(self, schedule: dict | None, day) -> None:
        self.day = day
        self.trains: dict[str, list[dict]] = {}
        self.pos: dict[str, dict[str, int]] = {}
        self.calling: dict[str, list[tuple]] = {}
        self.lines_at: dict[str, set[str]] = {}
        self.by_number: dict[str, list[str]] = {}
        self.line_dir: dict[tuple[str, str], list[str]] = {}
        self.names: dict[str, str] = {}
        self._segment: dict[tuple, dict] = {}
        self.build_ms = 0.0
        self.stop_rows = 0
        stations = (schedule or {}).get("stations") if isinstance(schedule, dict) else None
        if not isinstance(stations, dict):
            return
        bit = _weekday_bit(day)
        for name, pack in stations.items():
            if not isinstance(pack, dict):
                continue
            key = station_key(name)
            if key and key not in self.names:
                self.names[key] = str(name)
            for direction in ("N", "S"):
                rows = pack.get(direction) or []
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    self.stop_rows += 1
                    line = str(row.get("line") or "")
                    if key:
                        self.lines_at.setdefault(key, set()).add(line)
                    days = int(row.get("days") or 0)
                    if days and not (days & bit):
                        continue
                    train = str(row.get("n") or "").strip()
                    when = clock_on(day, str(row.get("t") or ""))
                    if not train or when is None or not key:
                        continue
                    self.trains.setdefault(train, []).append(
                        {
                            "station": str(name),
                            "key": key,
                            "when": when,
                            "line": line,
                            "dest": str(row.get("d") or ""),
                            "direction": direction,
                            "clock": str(row.get("t") or "")[:5],
                        }
                    )
        for train, stops in list(self.trains.items()):
            stops.sort(key=lambda item: item["when"])
            seen: set[str] = set()
            unique: list[dict] = []
            for stop in stops:
                if stop["key"] in seen:
                    continue
                seen.add(stop["key"])
                unique.append(stop)
            self.trains[train] = unique
            self.pos[train] = {stop["key"]: index for index, stop in enumerate(unique)}
            self.by_number.setdefault(bare_train(train), []).append(train)
            if unique:
                group = (unique[0]["line"], unique[0]["direction"])
                self.line_dir.setdefault(group, []).append(train)
        self.full_skipped: dict[str, list[str]] = {}
        for train, stops in self.trains.items():
            for index, stop in enumerate(stops):
                self.calling.setdefault(stop["key"], []).append((stop["when"], train, index, stop))
            if len(stops) < 2:
                self.full_skipped[train] = []
                continue
            group = (stops[0]["line"], stops[0]["direction"])
            ours = {stop["key"] for stop in stops}
            board = stops[0]["key"]
            alight = stops[-1]["key"]
            missing: list[str] = []
            seen: set[str] = set()
            for other in self.line_dir.get(group, []):
                if other == train:
                    continue
                opos = self.pos[other]
                a = opos.get(board)
                b = opos.get(alight)
                if a is None or b is None or b <= a:
                    continue
                for stop in self.trains[other][a + 1 : b]:
                    if stop["key"] in ours or stop["key"] in seen:
                        continue
                    seen.add(stop["key"])
                    missing.append(stop["key"])
            self.full_skipped[train] = missing
        for rows in self.calling.values():
            rows.sort(key=lambda item: item[0])

    def itineraries(
        self,
        origin: str,
        destination: str,
        transfer_min: int = 3,
        line_names: dict | None = None,
        *,
        enforce_transfer: bool = True,
        through: bool = True,
        limit: int | None = None,
        after: datetime | None = None,
        by_depart: bool = False,
    ) -> list[dict]:
        names = line_names or {}
        origin_key = station_key(origin)
        dest_key = station_key(destination)
        if not origin_key or not dest_key or origin_key == dest_key:
            return []
        origin_lines = self.lines_at.get(origin_key, set())
        dest_lines = self.lines_at.get(dest_key, set())
        shared = {
            key
            for key, lines in self.lines_at.items()
            if key not in {origin_key, dest_key} and (lines & origin_lines) and (lines & dest_lines)
        }
        try:
            gap = max(0, int(transfer_min or 0))
        except (TypeError, ValueError):
            gap = 0
        base = None
        if after is not None:
            base = after.astimezone(NY) if after.tzinfo else after.replace(tzinfo=NY)
        directs: list[dict] = []
        pending: list[tuple] = []
        for train, path in self.trains.items():
            start = self.pos.get(train, {}).get(origin_key)
            if start is None:
                continue
            depart = path[start]["when"]
            if base is not None and depart < base:
                continue
            line = str(names.get(path[start]["line"], path[start]["line"]) or path[start]["line"])
            terminal = str(path[-1].get("dest") or path[-1]["station"])
            finish = self.pos.get(train, {}).get(dest_key)
            if finish is not None and finish > start:
                directs.append(self._direct_row(train, path, start, finish, line, terminal, through=False))
                continue
            merged = self._through_row(train, path, start, dest_key, line, terminal) if through else None
            if merged is not None:
                directs.append(merged)
                continue
            pending.append((depart, train, path, start, line, terminal))
        directs.sort(key=lambda item: item.get("depart_sched") or "")
        cap = None if not limit else max(1, int(limit))
        if by_depart:
            return self._by_departure(directs, pending, cap, dest_key, shared, gap, names, destination, enforce_transfer)
        if cap is not None and len(directs) >= cap:
            return directs[:cap]
        linked: list[dict] = []
        pending.sort(key=lambda item: item[0])
        need = None if cap is None else cap - len(directs)
        for _depart, train, path, start, line, terminal in pending:
            link = self._best_link(train, path, start, dest_key, shared, gap, names, destination, enforce_transfer)
            if link is None:
                continue
            linked.append(self._transfer_row(train, path, start, line, terminal, link, dest_key))
            if need is not None and len(linked) >= need:
                break
        return directs + linked

    def _by_departure(self, directs, pending, cap, dest_key, shared, gap, names, destination, enforce):
        """Earliest departures, direct or transfer, until ``cap`` rows exist."""
        merged = [(item.get("depart_sched") or "", "d", item) for item in directs]
        for item in pending:
            merged.append((_iso(item[0]) or "", "p", item))
        merged.sort(key=lambda item: item[0])
        out = []
        for _when, kind, item in merged:
            if kind == "d":
                out.append(item)
            else:
                _depart, train, path, start, line, terminal = item
                link = self._best_link(train, path, start, dest_key, shared, gap, names, destination, enforce)
                if link is None:
                    continue
                out.append(self._transfer_row(train, path, start, line, terminal, link, dest_key))
            if cap is not None and len(out) >= cap:
                break
        return out

    def _direct_row(self, train, path, start, finish, line, terminal, through: bool) -> dict:
        depart = path[start]["when"]
        arrive = path[finish]["when"]
        detail = self.segment(train, path[start]["key"], path[finish]["key"])
        row = {
            "train": train,
            "train_number": bare_train(train),
            "line": line,
            "destination": terminal,
            "depart_sched": _iso(depart),
            "depart_est": _iso(depart),
            "arrive_sched": _iso(arrive),
            "arrive_est": _iso(arrive),
            "delay_min": None,
            "direct": True,
            "through": through,
            "connection": None,
            "live": False,
            "source": "timetable",
            "service_type": detail["service_type"],
            "stops_count": detail["stops_count"],
            "stops": detail["stops"],
            "skipped": detail["skipped"],
        }
        return row

    def _through_row(self, train, path, start, dest_key, line, terminal):
        bare = bare_train(train)
        others = [item for item in self.by_number.get(bare, []) if item != train]
        if not others:
            return None
        best = None
        for stop in path[start + 1 :]:
            for other in others:
                opos = self.pos.get(other) or {}
                here = opos.get(stop["key"])
                there = opos.get(dest_key)
                if here is None or there is None or there <= here:
                    continue
                other_path = self.trains[other]
                depart_at = other_path[here]["when"]
                if depart_at < stop["when"]:
                    continue
                wait = (depart_at - stop["when"]).total_seconds() / 60
                if wait > 15:
                    continue
                final = other_path[there]["when"]
                if best is None or final < best[0]:
                    best = (final, other, here, there, stop)
        if best is None:
            return None
        _final, other, here, there, stop = best
        other_path = self.trains[other]
        first = self.segment(train, path[start]["key"], stop["key"])
        second = self.segment(other, other_path[here]["key"], other_path[there]["key"])
        stops = list(first["stops"])
        for item in second["stops"][1:]:
            stops.append(item)
        skipped = list(dict.fromkeys(list(first["skipped"]) + list(second["skipped"])))
        service = "Express" if skipped else (first["service_type"] or second["service_type"] or "Local")
        return {
            "train": train,
            "train_number": bare,
            "line": line,
            "destination": terminal,
            "depart_sched": _iso(path[start]["when"]),
            "depart_est": _iso(path[start]["when"]),
            "arrive_sched": _iso(other_path[there]["when"]),
            "arrive_est": _iso(other_path[there]["when"]),
            "delay_min": None,
            "direct": True,
            "through": True,
            "connection": None,
            "live": False,
            "source": "timetable",
            "service_type": service,
            "stops_count": len(stops),
            "stops": stops,
            "skipped": skipped,
        }

    def _best_link(self, train, path, start, dest_key, shared, gap, names, destination, enforce):
        best_valid = None
        best_risk = None
        for stop in path[start + 1 :]:
            if shared and stop["key"] not in shared:
                continue
            earliest = stop["when"] + timedelta(minutes=gap)
            callers = self.calling.get(stop["key"]) or []
            start_at = bisect.bisect_left(callers, (stop["when"],))
            for when, other, index, other_stop in callers[start_at:]:
                if other == train:
                    continue
                if best_valid is not None and when >= best_valid[0]:
                    break
                opos = self.pos.get(other) or {}
                here = opos.get(other_stop["key"])
                there = opos.get(dest_key)
                if here is None or there is None or there <= here:
                    continue
                final = self.trains[other][there]["when"]
                other_line = str(names.get(other_stop["line"], other_stop["line"]) or other_stop["line"])
                wait = int(round((when - stop["when"]).total_seconds() / 60))
                valid = when >= earliest
                pack = (final, when, other, other_line, stop, other_stop, wait, there, here)
                if valid:
                    if best_valid is None or final < best_valid[0]:
                        best_valid = pack
                elif best_risk is None or wait < best_risk[6] or (wait == best_risk[6] and final < best_risk[0]):
                    best_risk = pack
        chosen = best_valid or (best_risk if enforce else None)
        if not enforce:
            # Old rule: earliest final arrival, including a short wait.
            pool = [item for item in (best_valid, best_risk) if item is not None]
            # That only keeps the best of each bucket. Re-scan is required for the true earliest.
            chosen = self._earliest_link(train, path, start, dest_key, shared, names, destination)
            return chosen
        if chosen is None:
            return None
        return self._pack_link(chosen, gap, destination, at_risk=chosen is not best_valid)

    def _earliest_link(self, train, path, start, dest_key, shared, names, destination):
        best = None
        for stop in path[start + 1 :]:
            if shared and stop["key"] not in shared:
                continue
            callers = self.calling.get(stop["key"]) or []
            start_at = bisect.bisect_left(callers, (stop["when"],))
            for when, other, _index, other_stop in callers[start_at:]:
                if other == train:
                    continue
                if best is not None and when >= best[0]:
                    break
                opos = self.pos.get(other) or {}
                here = opos.get(other_stop["key"])
                there = opos.get(dest_key)
                if here is None or there is None or there <= here:
                    continue
                final = self.trains[other][there]["when"]
                if best is not None and final >= best[0]:
                    continue
                other_line = str(names.get(other_stop["line"], other_stop["line"]) or other_stop["line"])
                wait = int(round((when - stop["when"]).total_seconds() / 60))
                best = (final, when, other, other_line, stop, other_stop, wait, there, here)
        if best is None:
            return None
        return self._pack_link(best, 0, destination, at_risk=False, transfer_min_for_flag=None)

    def _pack_link(self, pack, gap, destination, at_risk: bool, transfer_min_for_flag=None):
        final, when, other, other_line, stop, other_stop, wait, there, here = pack
        other_path = self.trains[other]
        detail = self.segment(other, other_path[here]["key"], other_path[there]["key"])
        flag = at_risk if transfer_min_for_flag is None else wait < gap
        if transfer_min_for_flag is None and not at_risk:
            flag = False
        return {
            "station": other_stop["station"],
            "train": other,
            "train_number": bare_train(other),
            "line": other_line,
            "arrive_sched": _iso(stop["when"]),
            "arrive_est": _iso(stop["when"]),
            "depart_sched": _iso(when),
            "depart_est": _iso(when),
            "arrive_final_sched": _iso(final),
            "arrive_final_est": _iso(final),
            "wait_min": wait,
            "at_risk": bool(at_risk),
            "track": None,
            "platform": None,
            "delay_min": None,
            "destination": destination,
            "service_type": detail["service_type"],
            "stops_count": detail["stops_count"],
            "stops": detail["stops"],
            "skipped": detail["skipped"],
            "_board_key": stop["key"],
            "_here": here,
            "_there": there,
            "_other": other,
        }

    def _transfer_row(self, train, path, start, line, terminal, link, dest_key) -> dict:
        board = self.segment(train, path[start]["key"], link.get("_board_key") or "")
        leg2 = link.get("stops_count") or 0
        count = board["stops_count"] + max(0, leg2 - 1)
        stops = list(board["stops"])
        for item in link.get("stops") or []:
            if stops and item.get("station") == stops[-1].get("station"):
                continue
            stops.append(item)
        skipped = list(dict.fromkeys(list(board["skipped"]) + list(link.get("skipped") or [])))
        service = board["service_type"] or link.get("service_type") or ""
        clean = {key: value for key, value in link.items() if not str(key).startswith("_")}
        return {
            "train": train,
            "train_number": bare_train(train),
            "line": line,
            "destination": terminal,
            "depart_sched": _iso(path[start]["when"]),
            "depart_est": _iso(path[start]["when"]),
            "arrive_sched": link["arrive_final_sched"],
            "arrive_est": link["arrive_final_est"],
            "delay_min": None,
            "direct": False,
            "through": False,
            "connection": clean,
            "live": False,
            "source": "timetable",
            "service_type": service,
            "stops_count": count or len(stops),
            "stops": stops,
            "skipped": skipped,
        }

    def segment(self, train: str, board_key: str, alight_key: str) -> dict:
        cache_key = (train, board_key, alight_key)
        cached = self._segment.get(cache_key)
        if cached is not None:
            return cached
        path = self.trains.get(train) or []
        pos = self.pos.get(train) or {}
        start = pos.get(board_key)
        finish = pos.get(alight_key)
        empty = {"service_type": "", "stops_count": 0, "stops": [], "skipped": []}
        if start is None or finish is None or finish < start:
            self._segment[cache_key] = empty
            return empty
        piece = path[start : finish + 1]
        stops = [{"station": stop["station"], "depart": _iso(stop["when"]), "arrive": _iso(stop["when"])} for stop in piece]
        skipped = []
        for key in self.full_skipped.get(train) or []:
            if key in {board_key, alight_key}:
                continue
            name = self.names.get(key) or key
            group = (path[0]["line"], path[0]["direction"])
            for other in self.line_dir.get(group, []):
                if other == train:
                    continue
                opos = self.pos[other]
                a = opos.get(board_key)
                b = opos.get(alight_key)
                s = opos.get(key)
                if a is not None and b is not None and s is not None and a < s < b:
                    skipped.append(name)
                    break
        detail = {
            "service_type": "Express" if skipped else "Local",
            "stops_count": len(piece),
            "stops": stops,
            "skipped": skipped,
        }
        self._segment[cache_key] = detail
        return detail

    def trip_service(self, train: str) -> str:
        path = self.trains.get(train) or []
        if len(path) < 2:
            return "Local" if path else ""
        return self.segment(train, path[0]["key"], path[-1]["key"])["service_type"]

    def stops_for_number(self, trainno: str) -> list[dict]:
        want = bare_train(trainno)
        trains = self.by_number.get(want) or ([trainno] if trainno in self.trains else [])
        path = self.trains.get(trains[0]) if trains else None
        if not path:
            return []
        return [{"station": stop["station"], "when": stop["when"], "key": stop["key"], "clock": stop.get("clock")} for stop in path]


def cached_itineraries(
    schedule,
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
    started = time.perf_counter()
    idx = index_for(schedule, day)
    feed = str((schedule or {}).get("feed") or "") if isinstance(schedule, dict) else ""
    until = str((schedule or {}).get("validUntil") or "") if isinstance(schedule, dict) else ""
    names_key = tuple(sorted((line_names or {}).items()))
    search_after = None
    minute = ""
    if window == "rest_of_day" and now is not None:
        search_after = now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)
        minute = search_after.replace(second=0, microsecond=0).isoformat()
    key = (
        id(schedule),
        feed,
        until,
        getattr(day, "isoformat", lambda: str(day))(),
        station_key(origin),
        station_key(destination),
        int(transfer_min or 0),
        names_key,
        bool(enforce_transfer),
        bool(through),
        window,
        minute,
        int(limit or 0),
        bool(by_depart),
    )
    skeleton = _SKELETONS.get(key)
    full_key = key[:-1] + (False,)
    if skeleton is None and limit and not minute and not by_depart:
        full_key = key[:-2] + (0, False)
        skeleton = _SKELETONS.get(full_key)
        if skeleton is not None:
            skeleton = skeleton[: max(1, int(limit))]
    if skeleton is None:
        STATS["misses"] += 1
        skeleton = idx.itineraries(
            origin,
            destination,
            transfer_min,
            line_names,
            enforce_transfer=enforce_transfer,
            through=through,
            limit=limit,
            after=search_after,
            by_depart=by_depart,
        )
        _SKELETONS[key] = skeleton
        while len(_SKELETONS) > _MAX_SKELETONS:
            _SKELETONS.popitem(last=False)
        STATS["skeleton_builds"] += 1
    else:
        _SKELETONS.move_to_end(key if key in _SKELETONS else full_key)
        STATS["hits"] += 1
    rows = skeleton
    if limit and len(rows) > int(limit):
        rows = rows[: max(1, int(limit))]
    elapsed = (time.perf_counter() - started) * 1000
    STATS["last_skeleton_ms"] = round(elapsed, 2)
    note_slow("itinerary search", elapsed)
    return rows
