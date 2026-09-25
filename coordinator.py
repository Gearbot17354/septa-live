"""Data update coordinator for SEPTA Transit."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import json
import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ALERTS_URL,
    ARRIVALS_URL,
    BUS_SCHEDULES_URL,
    CONF_BUS_DEST,
    CONF_BUS_LINE,
    CONF_DESTINATION,
    CONF_METRO_DEST,
    CONF_METRO_LINE,
    CONF_METRO_STATION,
    CONF_SCAN,
    CONF_SHOW_BUS,
    CONF_SHOW_METRO,
    CONF_SHOW_RAIL,
    CONF_SHOW_TROLLEY,
    CONF_RAIL_LINE,
    CONF_STATION,
    CONF_TROLLEY_DEST,
    CONF_TROLLEY_LINE,
    CONF_TROLLEY_STATION,
    CONF_WALK,
    CONF_WATCHES,
    DEFAULT_DESTINATION,
    DEFAULT_SCAN,
    DEFAULT_SHOW_BUS,
    DEFAULT_SHOW_METRO,
    DEFAULT_SHOW_RAIL,
    DEFAULT_SHOW_TROLLEY,
    DEFAULT_WALK,
    DOMAIN,
    LOCATIONS_URL,
    METRO_ROUTE_IDS,
    NTA_URL,
    RAIL_LINES,
    STOPS_URL,
    TRAINVIEW_URL,
    TRANSITVIEW_URL,
    TROLLEY_ROUTE_IDS,
    V2_TRIPS_URL,
)

_LOGGER = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")
DELAY_RE = re.compile(r"(-?\d+)\s*min", re.I)


def parse_delay(status: str) -> tuple[int, bool]:
    text = (status or "").strip()
    if re.search(r"cancel", text, re.I):
        return 0, True
    if re.search(r"on\s*time", text, re.I):
        return 0, False
    match = DELAY_RE.search(text)
    if match:
        return int(match.group(1)), False
    return 0, False


def parse_naive(raw: str | None) -> datetime | None:
    if not raw:
        return None
    cleaned = raw.replace(".000", "").strip().replace(" ", "T")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    return dt.replace(tzinfo=NY)


def parse_clock(label: str | None, now: datetime) -> datetime | None:
    if not label:
        return None
    match = re.match(r"^\s*(\d{1,2}):(\d{2})\s*(AM|PM)\s*$", label, re.I)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    ap = match.group(3).upper()
    if ap == "PM" and hour != 12:
        hour += 12
    if ap == "AM" and hour == 12:
        hour = 0
    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if (now - dt) > timedelta(hours=18):
        dt += timedelta(days=1)
    if (dt - now) > timedelta(hours=18):
        dt -= timedelta(days=1)
    return dt


def minutes_until(dt: datetime | None, now: datetime) -> int | None:
    if dt is None:
        return None
    return int(round((dt - now).total_seconds() / 60))


def format_clock(dt: datetime | None) -> str:
    if dt is None:
        return ""
    hour = dt.hour % 12 or 12
    ap = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.minute:02d} {ap}"


BOARD_LIMIT = 8
_LINE_NAMES = {
    "AIR": "Airport",
    "CHE": "Chestnut Hill East",
    "CHW": "Chestnut Hill West",
    "CYN": "Cynwyd",
    "FOX": "Fox Chase",
    "LAN": "Lansdale/Doylestown",
    "MED": "Media/Wawa",
    "NOR": "Manayunk/Norristown",
    "PAO": "Paoli/Thorndale",
    "TRE": "Trenton",
    "WAR": "Warminster",
    "WTR": "West Trenton",
    "WIL": "Wilmington/Newark",
}
_SCHEDULE: dict[str, Any] | None = None


def _load_schedule() -> dict[str, Any]:
    global _SCHEDULE
    if _SCHEDULE is None:
        path = Path(__file__).with_name("rail-schedule.json")
        try:
            _SCHEDULE = json.loads(path.read_text())
        except OSError:
            _SCHEDULE = {"stations": {}}
    return _SCHEDULE


def _station_schedule(station: str) -> dict[str, Any] | None:
    stations = (_load_schedule().get("stations") or {}) if isinstance(_load_schedule(), dict) else {}
    if not isinstance(stations, dict):
        return None
    want = station.strip().lower()
    for key, pack in stations.items():
        if str(key).lower() == want:
            return pack if isinstance(pack, dict) else None
    for key, pack in stations.items():
        k = str(key).lower()
        if want in k or k in want:
            return pack if isinstance(pack, dict) else None
    return None


def _trip_dt(service_day: date, hhmm: str) -> datetime | None:
    parts = hhmm.split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    extra = 0
    if hour >= 24:
        extra = hour // 24
        hour %= 24
    dt = datetime(service_day.year, service_day.month, service_day.day, hour, minute, tzinfo=NY)
    if extra:
        dt += timedelta(days=extra)
    return dt


def _scheduled_fill(station: str, direction: str, now: datetime) -> list[dict[str, Any]]:
    pack = _station_schedule(station)
    if not pack:
        return []
    trips = pack.get(direction) or []
    if not isinstance(trips, list):
        return []
    today = now.date()
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for offset in (-1, 0, 1):
        day = today + timedelta(days=offset)
        js_dow = (day.weekday() + 1) % 7
        for trip in trips:
            if not isinstance(trip, dict):
                continue
            days = int(trip.get("days") or 0)
            if not days & (1 << js_dow):
                continue
            dt = _trip_dt(day, str(trip.get("t") or ""))
            if dt is None or dt <= now:
                continue
            key = f"{dt.isoformat()}-{trip.get('n')}-{trip.get('d')}"
            if key in seen:
                continue
            seen.add(key)
            line_id = str(trip.get("line") or "")
            found.append(
                {
                    "train_id": str(trip.get("n") or ""),
                    "destination": str(trip.get("d") or ""),
                    "origin": "",
                    "line": _LINE_NAMES.get(line_id, line_id),
                    "status": "Scheduled",
                    "delay_min": 0,
                    "cancelled": False,
                    "track": "",
                    "clock": format_clock(dt),
                    "sched_dt": dt,
                    "minutes": minutes_until(dt, now),
                    "scheduled": True,
                    "service_type": "LOCAL",
                }
            )
    found.sort(key=lambda row: row.get("sched_dt") or now)
    return found[:BOARD_LIMIT]


def _pad_schedule(
    station: str, direction: str, live: list[dict[str, Any]], now: datetime
) -> list[dict[str, Any]]:
    for row in live:
        if row.get("minutes") is None:
            row["minutes"] = minutes_until(row.get("sched_dt"), now)
    if len(live) >= BOARD_LIMIT:
        return live[:BOARD_LIMIT]
    extra = _scheduled_fill(station, direction, now)
    last = live[-1].get("sched_dt") if live else None
    seen = {str(row.get("train_id") or "") for row in live}
    for row in extra:
        tid = str(row.get("train_id") or "")
        when = row.get("sched_dt")
        if tid in seen:
            continue
        if last is not None and when is not None and when <= last:
            continue
        live.append(row)
        if len(live) >= BOARD_LIMIT:
            break
    return live[:BOARD_LIMIT]


def _ll(item: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lat = float(item.get("lat"))
        lon = float(item.get("lng") or item.get("lon") or item.get("longitude"))
    except (TypeError, ValueError):
        return None
    if lat == 0 and lon == 0:
        return None
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None
    return lat, lon


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _norm_name(name: str) -> str:
    text = name.lower()
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"\b(station|transportation center|t\.?c\.?)\b", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _parse_bus_calendar(raw: str) -> datetime | None:
    match = re.match(
        r"^\s*(\d{1,2})/(\d{1,2})/(\d{2})\s+(\d{1,2}):(\d{2})\s*(am|pm)",
        raw,
        re.I,
    )
    if not match:
        return None
    year = 2000 + int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5))
    ap = match.group(6).upper()
    if ap == "PM" and hour != 12:
        hour += 12
    if ap == "AM" and hour == 12:
        hour = 0
    try:
        return datetime(year, int(match.group(1)), int(match.group(2)), hour, minute, tzinfo=NY)
    except ValueError:
        return None


class SeptaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and normalize SEPTA arrivals."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        interval = int(entry.options.get(CONF_SCAN, entry.data.get(CONF_SCAN, DEFAULT_SCAN)))
        super().__init__(
            hass,
            _LOGGER,
            name=f"SEPTA {entry.data.get(CONF_STATION, 'Live')}",
            update_interval=timedelta(seconds=max(30, interval)),
        )
        self.session = async_get_clientsession(hass)
        self._board_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    async def async_board_for_station(self, station: str) -> dict[str, Any]:
        """Live + timetable board for any Regional Rail station."""
        name = (station or "").strip() or self.station
        now = datetime.now(NY)
        cached = self._board_cache.get(name.lower())
        if cached and now.timestamp() - cached[0] < 20:
            return cached[1]
        try:
            raw = await self._get(ARRIVALS_URL, {"station": name, "results": BOARD_LIMIT})
            north, south = _parse_arrivals(raw)
        except Exception:  # noqa: BLE001
            north, south = [], []
        north = _pad_schedule(name, "N", north, now)
        south = _pad_schedule(name, "S", south, now)
        pack = {
            "station": name,
            "southbound": _board_pack(south),
            "northbound": _board_pack(north),
        }
        self._board_cache[name.lower()] = (now.timestamp(), pack)
        return pack

    async def _load_buses(self, now: datetime) -> list[dict[str, Any]]:
        try:
            coords = await self._station_coords()
            if not coords:
                return []
            locations = await self._get(
                LOCATIONS_URL,
                {"lat": coords[0], "lon": coords[1], "radius": 1},
            )
            stops: list[dict[str, Any]] = []
            if isinstance(locations, list):
                for item in locations:
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("location_type") or "") != "bus_stops":
                        continue
                    sid = str(item.get("location_id") or "")
                    if sid:
                        stops.append(item)
            trips: list[dict[str, Any]] = []
            used_stops: list[str] = []
            for item in stops[:8]:
                sid = str(item.get("location_id") or "")
                try:
                    raw = await self._get(BUS_SCHEDULES_URL, {"stop_id": sid})
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(raw, dict) or raw.get("error"):
                    continue
                name = str(item.get("location_name") or "")
                before = len(trips)
                for route, rows in raw.items():
                    if not isinstance(rows, list):
                        continue
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        when = _parse_bus_calendar(str(row.get("DateCalender") or ""))
                        if when and when < now - timedelta(minutes=2):
                            continue
                        trips.append(
                            {
                                "route": str(row.get("Route") or route),
                                "destination": str(row.get("DirectionDesc") or ""),
                                "stop_id": sid,
                                "stop_name": str(row.get("StopName") or name),
                                "clock": str(row.get("date") or ""),
                                "sched_dt": when,
                                "minutes": minutes_until(when, now),
                                "delay_min": 0,
                                "live": False,
                            }
                        )
                if len(trips) > before:
                    used_stops.append(sid)
                    if len(used_stops) >= 3:
                        break
            trips = _overlay_live_buses(trips, await self._live_buses(trips), used_stops)
            seen: set[tuple[Any, ...]] = set()
            unique: list[dict[str, Any]] = []
            for trip in trips:
                key = (trip.get("route"), trip.get("destination"), trip.get("stop_id"), trip.get("clock"))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(trip)
            unique.sort(key=lambda t: t.get("sched_dt") or now + timedelta(days=30))
            if self.bus_dest:
                want = _norm_name(self.bus_dest)
                unique = [
                    t
                    for t in unique
                    if want
                    and (
                        want in _norm_name(str(t.get("destination") or ""))
                        or _norm_name(str(t.get("destination") or "")) in want
                    )
                ]
            return unique[:12]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Bus lookup failed: %s", err)
            return []

    async def _live_buses(self, trips: list[dict[str, Any]]) -> list[dict[str, Any]]:
        routes: list[str] = []
        seen: set[str] = set()
        for trip in trips:
            route = str(trip.get("route") or "")
            if route and route not in seen:
                seen.add(route)
                routes.append(route)
        buses: list[dict[str, Any]] = []
        for route in routes[:6]:
            try:
                raw = await self._get(TRANSITVIEW_URL, {"route": route})
            except Exception:  # noqa: BLE001
                continue
            rows = raw.get("bus") if isinstance(raw, dict) else raw
            if not isinstance(rows, list):
                continue
            for item in rows:
                if isinstance(item, dict):
                    buses.append(item)
        return buses

    async def _load_map_vehicles(
        self, buses: list[dict[str, Any]], metro_vehicles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        vehicles: list[dict[str, Any]] = list(metro_vehicles)
        if self.show_rail:
            try:
                raw = await self._get(TRAINVIEW_URL, {})
                rows = raw if isinstance(raw, list) else []
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    point = _ll(item)
                    if not point:
                        continue
                    vehicles.append(
                        {
                            "id": str(item.get("trainno") or item.get("train_id") or ""),
                            "kind": "rail",
                            "lat": point[0],
                            "lon": point[1],
                            "dest": str(item.get("dest") or item.get("destination") or ""),
                            "line": str(item.get("line") or ""),
                            "late": item.get("late") or 0,
                            "next": str(item.get("nextstop") or item.get("next_stop") or ""),
                        }
                    )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("TrainView failed: %s", err)
        if self.show_bus:
            try:
                live = await self._live_buses(buses)
                for item in live:
                    point = _ll(item)
                    if not point:
                        continue
                    vehicles.append(
                        {
                            "id": str(item.get("VehicleID") or item.get("label") or ""),
                            "kind": "bus",
                            "lat": point[0],
                            "lon": point[1],
                            "dest": str(item.get("destination") or ""),
                            "line": str(item.get("route_id") or item.get("Route") or ""),
                            "late": item.get("late") or 0,
                            "next": str(item.get("next_stop_name") or item.get("nextstop") or ""),
                        }
                    )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Bus map lookup failed: %s", err)
        return vehicles[:120]

    async def _load_metro(self) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        empty = {"count": 0, "summary": "Off", "routes": {}}
        metro = {"count": 0, "summary": "Off", "l": 0, "b": 0, "m": 0, "routes": {}}
        trolley = {"count": 0, "summary": "Off", "gps": 0, "routes": {}}
        vehicles: list[dict[str, Any]] = []
        self._service_rows = []
        ids: list[str] = []
        if self.show_metro:
            ids.extend(METRO_ROUTE_IDS)
        if self.show_trolley:
            ids.extend(TROLLEY_ROUTE_IDS)
        if not ids:
            return metro, trolley, vehicles
        try:
            rows: list[dict[str, Any]] = []
            for route_id in ids:
                try:
                    raw = await self._get(V2_TRIPS_URL, {"route_id": route_id})
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(raw, list):
                    rows.extend(item for item in raw if isinstance(item, dict))
            self._service_rows = rows
            metro_routes: dict[str, int] = {}
            trolley_routes: dict[str, int] = {}
            l = b = m_count = gps = 0
            metro_n = trolley_n = 0
            for item in rows:
                route = str(item.get("route_id") or "")
                home = self.metro_home if route in METRO_ROUTE_IDS else self.trolley_home
                dest = self.metro_dest if route in METRO_ROUTE_IDS else self.trolley_dest
                if not _matches_commute(item, home, dest):
                    continue
                if route in METRO_ROUTE_IDS:
                    if self.metro_line and route != self.metro_line:
                        continue
                    metro_n += 1
                    metro_routes[route] = metro_routes.get(route, 0) + 1
                    if route.startswith("L"):
                        l += 1
                    elif route.startswith("B"):
                        b += 1
                    elif route.startswith("M"):
                        m_count += 1
                elif route in TROLLEY_ROUTE_IDS:
                    if self.trolley_line and route != self.trolley_line:
                        continue
                    trolley_n += 1
                    trolley_routes[route] = trolley_routes.get(route, 0) + 1
                    lat = item.get("lat")
                    if lat not in (None, "", "None"):
                        gps += 1
                point = _ll(item)
                if point:
                    vehicles.append(
                        {
                            "id": str(item.get("trip_id") or item.get("vehicle_id") or route),
                            "kind": "metro" if route in METRO_ROUTE_IDS else "trolley",
                            "lat": point[0],
                            "lon": point[1],
                            "dest": str(item.get("destination") or item.get("headsign") or ""),
                            "line": route,
                            "late": item.get("late") or 0,
                            "next": str(item.get("next_stop_name") or ""),
                        }
                    )
            metro = {
                "count": metro_n,
                "summary": f"{l} L · {b} B · {m_count} M" if metro_n else "None reporting",
                "l": l,
                "b": b,
                "m": m_count,
                "routes": metro_routes,
                "home": self.metro_home,
                "destination": self.metro_dest,
            }
            trolley = {
                "count": trolley_n,
                "summary": f"{gps} with GPS" if trolley_n else "None reporting",
                "gps": gps,
                "routes": trolley_routes,
                "home": self.trolley_home,
                "destination": self.trolley_dest,
            }
            return metro, trolley, vehicles
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Metro lookup failed: %s", err)
            return empty | {"l": 0, "b": 0, "m": 0}, empty | {"gps": 0}, []

    async def _pack_watches(self, buses: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
        """One summary per extra commute line added with the plus button."""
        out: dict[str, Any] = {}
        service_rows = getattr(self, "_service_rows", []) or []
        for watch in self.watches():
            mode = watch["mode"]
            enabled = {
                "rail": self.show_rail,
                "bus": self.show_bus,
                "metro": self.show_metro,
                "trolley": self.show_trolley,
            }[mode]
            if not enabled:
                continue
            try:
                out[watch["id"]] = await self._one_watch(watch, buses, service_rows, now)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Watch %s failed: %s", watch["id"], err)
                out[watch["id"]] = {"state": None, "summary": "Unavailable", "mode": mode}
        return out

    async def _one_watch(
        self,
        watch: dict[str, str],
        buses: list[dict[str, Any]],
        service_rows: list[dict[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        mode = watch["mode"]
        line = watch["line"]
        home = watch["home"]
        dest = watch["dest"]
        if mode == "rail":
            station = home or self.station
            raw = await self._get(ARRIVALS_URL, {"station": station, "results": BOARD_LIMIT})
            _north, south = _parse_arrivals(raw)
            south = [row for row in south if _matches_line(row, line)]
            if dest:
                want = _norm_name(dest)
                headed = [row for row in south if want in _norm_name(str(row.get("destination") or ""))]
                if headed:
                    south = headed
            nxt = south[0] if south else None
            return {
                "mode": mode,
                "line": line,
                "home": station,
                "destination": dest,
                "state": None if not nxt else nxt.get("minutes"),
                "summary": "No trains" if not nxt else f"{nxt.get('destination') or ''} · {nxt.get('clock') or ''}".strip(" ·"),
                "clock": "" if not nxt else nxt.get("clock") or "",
                "trains": _board_pack(south),
            }
        if mode == "bus":
            trips = buses
            if line:
                trips = [row for row in trips if str(row.get("route") or "").lower() == line.lower()]
            nxt = trips[0] if trips else None
            return {
                "mode": mode,
                "line": line,
                "state": None if not nxt else nxt.get("minutes"),
                "summary": "No buses" if not nxt else str(nxt.get("destination") or nxt.get("route") or ""),
                "clock": "" if not nxt else nxt.get("clock") or "",
                "route": "" if not nxt else nxt.get("route") or line,
            }
        routes = METRO_ROUTE_IDS if mode == "metro" else TROLLEY_ROUTE_IDS
        matched = []
        for item in service_rows:
            route = str(item.get("route_id") or "")
            if route not in routes:
                continue
            if line and route != line:
                continue
            if not _matches_commute(item, home, dest):
                continue
            matched.append(item)
        return {
            "mode": mode,
            "line": line,
            "home": home,
            "destination": dest,
            "state": len(matched),
            "summary": f"{len(matched)} vehicles" if matched else "None reporting",
            "routes": sorted({str(item.get("route_id") or "") for item in matched}),
        }

    async def _station_coords(self) -> tuple[float, float] | None:
        want = _norm_name(self.station)
        for line in RAIL_LINES:
            try:
                raw = await self._get(STOPS_URL, {"req1": line})
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(raw, list):
                continue
            for item in raw:
                if not isinstance(item, dict):
                    continue
                name = _norm_name(str(item.get("stopname") or ""))
                if name == want or want in name or name in want:
                    try:
                        return float(item["lat"]), float(item.get("lng") or item.get("lon"))
                    except (TypeError, ValueError, KeyError):
                        continue
        return None

    @property
    def station(self) -> str:
        return self.entry.data.get(CONF_STATION, "Lansdale")

    @property
    def destination(self) -> str:
        return self.entry.options.get(
            CONF_DESTINATION, self.entry.data.get(CONF_DESTINATION, DEFAULT_DESTINATION)
        )

    def _opt_str(self, key: str) -> str:
        return str(self.entry.options.get(key, self.entry.data.get(key, "")) or "").strip()

    @property
    def bus_dest(self) -> str:
        return self._opt_str(CONF_BUS_DEST)

    @property
    def metro_home(self) -> str:
        return self._opt_str(CONF_METRO_STATION)

    @property
    def metro_dest(self) -> str:
        return self._opt_str(CONF_METRO_DEST)

    @property
    def trolley_home(self) -> str:
        return self._opt_str(CONF_TROLLEY_STATION)

    @property
    def trolley_dest(self) -> str:
        return self._opt_str(CONF_TROLLEY_DEST)

    @property
    def rail_line(self) -> str:
        return self._opt_str(CONF_RAIL_LINE).upper()

    @property
    def bus_line(self) -> str:
        return self._opt_str(CONF_BUS_LINE)

    @property
    def metro_line(self) -> str:
        return self._opt_str(CONF_METRO_LINE)

    @property
    def trolley_line(self) -> str:
        return self._opt_str(CONF_TROLLEY_LINE)

    def watches(self) -> list[dict[str, str]]:
        raw = self.entry.options.get(CONF_WATCHES, self.entry.data.get(CONF_WATCHES, []))
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return []
        if not isinstance(raw, list):
            return []
        out: list[dict[str, str]] = []
        counts: dict[str, int] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            mode = str(item.get("mode") or "")
            if mode not in ("rail", "bus", "metro", "trolley"):
                continue
            counts[mode] = counts.get(mode, 0) + 1
            if counts[mode] > 3:
                continue
            wid = re.sub(r"[^a-z0-9]", "", str(item.get("id") or "").lower())[:12]
            if not wid:
                continue
            out.append(
                {
                    "id": wid,
                    "mode": mode,
                    "line": str(item.get("line") or "")[:24],
                    "home": str(item.get("home") or "")[:80],
                    "dest": str(item.get("dest") or "")[:80],
                }
            )
        return out

    @property
    def walk(self) -> int:
        return int(self.entry.options.get(CONF_WALK, self.entry.data.get(CONF_WALK, DEFAULT_WALK)))

    def _flag(self, key: str, default: bool) -> bool:
        if key in self.entry.options:
            return bool(self.entry.options[key])
        return bool(self.entry.data.get(key, default))

    @property
    def show_rail(self) -> bool:
        return self._flag(CONF_SHOW_RAIL, DEFAULT_SHOW_RAIL)

    @property
    def show_bus(self) -> bool:
        return self._flag(CONF_SHOW_BUS, DEFAULT_SHOW_BUS)

    @property
    def show_metro(self) -> bool:
        return self._flag(CONF_SHOW_METRO, DEFAULT_SHOW_METRO)

    @property
    def show_trolley(self) -> bool:
        return self._flag(CONF_SHOW_TROLLEY, DEFAULT_SHOW_TROLLEY)

    async def _get(self, url: str, params: dict[str, Any]) -> Any:
        async with self.session.get(url, params=params, timeout=20) as resp:
            resp.raise_for_status()
            text = await resp.text()
            cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
            return json.loads(cleaned)

    async def _async_update_data(self) -> dict[str, Any]:
        now = datetime.now(NY)
        north: list[dict[str, Any]] = []
        south: list[dict[str, Any]] = []
        commute: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
        if self.show_rail:
            try:
                arrivals_raw = await self._get(
                    ARRIVALS_URL, {"station": self.station, "results": BOARD_LIMIT}
                )
                nta_raw = await self._get(
                    NTA_URL,
                    {"req1": self.station, "req2": self.destination, "req3": 6},
                )
                alerts_raw = await self._get(ALERTS_URL, {})
            except Exception as err:  # noqa: BLE001
                raise UpdateFailed(f"SEPTA request failed: {err}") from err

            north, south = _parse_arrivals(arrivals_raw)
            north = [row for row in north if _matches_line(row, self.rail_line)]
            south = [row for row in south if _matches_line(row, self.rail_line)]
            north = _pad_schedule(self.station, "N", north, now)
            south = _pad_schedule(self.station, "S", south, now)
            north = [row for row in north if _matches_line(row, self.rail_line)]
            south = [row for row in south if _matches_line(row, self.rail_line)]
            commute = _parse_nta(nta_raw, now)
            if self.rail_line:
                commute = [row for row in commute if _matches_line(row, self.rail_line)]
            alerts = _parse_alerts(alerts_raw, self.station)

        buses = await self._load_buses(now) if self.show_bus else []
        if self.bus_line:
            want = self.bus_line.lower()
            buses = [row for row in buses if str(row.get("route") or "").lower() == want]
        metro, trolley, metro_vehicles = await self._load_metro()
        coords = await self._station_coords()
        map_vehicles = await self._load_map_vehicles(buses, metro_vehicles)

        next_s = south[0] if south else None
        next_n = north[0] if north else None
        next_c = commute[0] if commute else None
        next_bus = buses[0] if buses else None
        leave = None
        if next_c and next_c.get("depart_dt"):
            leave = minutes_until(next_c["depart_dt"] - timedelta(minutes=self.walk), now)

        worst = 0
        for row in north + south:
            worst = max(worst, int(row.get("delay_min") or 0))
        status = "On Time"
        if not self.show_rail:
            status = "Rail off"
        elif any(a.get("suspended") for a in alerts):
            status = "Suspended"
        elif worst >= 10:
            status = f"{worst} min delay"
        elif worst > 0:
            status = f"{worst} min delay"
        elif alerts:
            status = "Advisory"

        return {
            "station": self.station,
            "destination": self.destination,
            "northbound": north,
            "southbound": south,
            "alerts": alerts,
            "next_south": next_s,
            "next_north": next_n,
            "southbound_board": _board_pack(south),
            "northbound_board": _board_pack(north),
            "next_commute": next_c,
            "next_bus": next_bus,
            "buses": buses,
            "leave_in": leave,
            "status": status,
            "metro": metro,
            "trolley": trolley,
            "map": {
                "home": {"lat": coords[0], "lon": coords[1]} if coords else None,
                "vehicles": map_vehicles,
            },
            "lines": await self._pack_watches(buses, now),
            "updated": now.isoformat(),
        }


def _matches_line(row: dict[str, Any], code: str) -> bool:
    if not code:
        return True
    line = str(row.get("line") or "")
    name = _LINE_NAMES.get(code.upper(), "")
    blob = line.lower()
    if code.upper() == line.upper() or code.lower() in blob:
        return True
    return bool(name) and name.lower() in blob


def _train(raw: dict[str, Any]) -> dict[str, Any]:
    status = str(raw.get("status") or "")
    delay, cancelled = parse_delay(status)
    sched = parse_naive(str(raw.get("sched_time") or raw.get("depart_time") or ""))
    return {
        "train_id": str(raw.get("train_id") or ""),
        "destination": str(raw.get("destination") or ""),
        "origin": str(raw.get("origin") or ""),
        "line": str(raw.get("line") or ""),
        "status": status,
        "delay_min": delay,
        "cancelled": cancelled,
        "track": str(raw.get("track_change") or raw.get("track") or "").strip(),
        "clock": format_clock(sched),
        "sched_dt": sched,
        "minutes": None,
        "service_type": str(raw.get("service_type") or raw.get("ServiceType") or "").strip(),
    }


def _board_pack(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows[:BOARD_LIMIT]:
        track = str(row.get("track") or "").strip()
        out.append(
            {
                "train_id": row.get("train_id") or "",
                "destination": row.get("destination") or "",
                "line": row.get("line") or "",
                "clock": row.get("clock") or "",
                "minutes": row.get("minutes"),
                "track": track,
                "platform": track,
                "status": row.get("status") or "",
                "delay_min": row.get("delay_min") or 0,
                "cancelled": bool(row.get("cancelled")),
                "scheduled": bool(row.get("scheduled")),
                "service_type": str(row.get("service_type") or "").strip(),
            }
        )
    return out


def _parse_arrivals(raw: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    north: list[dict[str, Any]] = []
    south: list[dict[str, Any]] = []
    if not isinstance(raw, dict) or not raw:
        return north, south
    header = next(iter(raw))
    groups = raw.get(header)
    if not isinstance(groups, list):
        return north, south
    now = datetime.now(NY)
    for group in groups:
        if not isinstance(group, dict):
            continue
        for item in group.get("Northbound") or []:
            if isinstance(item, dict):
                row = _train(item)
                row["minutes"] = minutes_until(row["sched_dt"], now)
                north.append(row)
        for item in group.get("Southbound") or []:
            if isinstance(item, dict):
                row = _train(item)
                row["minutes"] = minutes_until(row["sched_dt"], now)
                south.append(row)
    return north, south


def _matches_commute(item: dict[str, Any], home: str, dest: str) -> bool:
    hn = _norm_name(home)
    dn = _norm_name(dest)
    if not hn and not dn:
        return True
    nxt = _norm_name(str(item.get("next_stop_name") or ""))
    head = _norm_name(str(item.get("trip_headsign") or item.get("destination") or ""))
    at_home = bool(hn) and (hn in nxt or nxt in hn or hn in head or head in hn)
    to_dest = bool(dn) and (dn in head or head in dn)
    if hn and dn:
        return to_dest or at_home
    if dn:
        return to_dest
    return at_home


def _parse_nta(raw: Any, now: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        delay, cancelled = parse_delay(str(item.get("orig_delay") or ""))
        depart = parse_clock(str(item.get("orig_departure_time") or ""), now)
        out.append(
            {
                "train_id": str(item.get("orig_train") or ""),
                "line": str(item.get("orig_line") or ""),
                "depart": str(item.get("orig_departure_time") or ""),
                "arrive": str(item.get("orig_arrival_time") or ""),
                "delay": str(item.get("orig_delay") or ""),
                "delay_min": delay,
                "cancelled": cancelled,
                "depart_dt": depart,
                "minutes": minutes_until(depart, now),
            }
        )
    return out


def _strip_html(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&", "&", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_alerts(raw: Any, station: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    needle = station.lower().split("/")[0]
    for item in raw:
        if not isinstance(item, dict):
            continue
        if str(item.get("mode") or "") != "Regional Rail":
            continue
        alert = _strip_html(str(item.get("alert") or ""))
        advisory = _strip_html(str(item.get("advisory") or ""))
        if not alert and not advisory:
            continue
        blob = f"{item.get('route')} {item.get('route_name')} {item.get('route_id')}".lower()
        interesting = "lansdale" in blob or "doylestown" in blob or needle in blob
        flag = lambda k: str(item.get(k) or "").lower() in ("y", "yes", "true")
        if interesting or flag("isalert") or flag("isdelays") or flag("issuspended"):
            out.append(
                {
                    "route": str(item.get("route_name") or item.get("route") or ""),
                    "alert": alert or advisory,
                    "suspended": flag("issuspended") or flag("issuppend"),
                }
            )
    return out


def _overlay_live_buses(
    trips: list[dict[str, Any]], live: list[dict[str, Any]], stop_ids: list[str]
) -> list[dict[str, Any]]:
    stop_set = set(stop_ids)
    claimed: set[str] = set()
    for bus in live:
        route = str(bus.get("route_id") or bus.get("Route") or "")
        dest = str(bus.get("destination") or "").lower()
        token = dest.split()[0] if dest else ""
        next_id = str(bus.get("next_stop_id") or "")
        try:
            late = int(bus.get("late") or 0)
        except (TypeError, ValueError):
            late = 0
        key = f"{route}|{token}"
        stop_hit = next_id in stop_set
        if not stop_hit and key in claimed:
            continue
        for trip in trips:
            if trip.get("live"):
                continue
            if str(trip.get("route") or "") != route:
                continue
            tdest = str(trip.get("destination") or "").lower()
            if stop_hit and next_id == str(trip.get("stop_id") or ""):
                trip["delay_min"] = late
                trip["live"] = True
                claimed.add(key)
                break
            if token and token in tdest:
                trip["delay_min"] = late
                trip["live"] = True
                claimed.add(key)
                break
    return trips
