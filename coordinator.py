"""Data update coordinator for SEPTA Live."""

from __future__ import annotations

from datetime import datetime, timedelta
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
    CONF_DESTINATION,
    CONF_SCAN,
    CONF_STATION,
    CONF_WALK,
    DEFAULT_DESTINATION,
    DEFAULT_SCAN,
    DEFAULT_WALK,
    DOMAIN,
    LOCATIONS_URL,
    METRO_ROUTE_IDS,
    NTA_URL,
    RAIL_LINES,
    STOPS_URL,
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

    async def _load_metro(self) -> tuple[dict[str, Any], dict[str, Any]]:
        empty = {"count": 0, "summary": "None reporting", "routes": {}}
        metro = {"count": 0, "summary": "None reporting", "l": 0, "b": 0, "m": 0, "routes": {}}
        trolley = {"count": 0, "summary": "None reporting", "gps": 0, "routes": {}}
        try:
            ids = METRO_ROUTE_IDS + TROLLEY_ROUTE_IDS
            rows: list[dict[str, Any]] = []
            for route_id in ids:
                try:
                    raw = await self._get(V2_TRIPS_URL, {"route_id": route_id})
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(raw, list):
                    rows.extend(item for item in raw if isinstance(item, dict))
            metro_routes: dict[str, int] = {}
            trolley_routes: dict[str, int] = {}
            l = b = m_count = gps = 0
            metro_n = trolley_n = 0
            for item in rows:
                route = str(item.get("route_id") or "")
                if route in METRO_ROUTE_IDS:
                    metro_n += 1
                    metro_routes[route] = metro_routes.get(route, 0) + 1
                    if route.startswith("L"):
                        l += 1
                    elif route.startswith("B"):
                        b += 1
                    elif route.startswith("M"):
                        m_count += 1
                elif route in TROLLEY_ROUTE_IDS:
                    trolley_n += 1
                    trolley_routes[route] = trolley_routes.get(route, 0) + 1
                    lat = item.get("lat")
                    if lat not in (None, "", "None"):
                        gps += 1
            metro = {
                "count": metro_n,
                "summary": f"{l} L · {b} B · {m_count} M" if metro_n else "None reporting",
                "l": l,
                "b": b,
                "m": m_count,
                "routes": metro_routes,
            }
            trolley = {
                "count": trolley_n,
                "summary": f"{gps} with GPS" if trolley_n else "None reporting",
                "gps": gps,
                "routes": trolley_routes,
            }
            return metro, trolley
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Metro lookup failed: %s", err)
            return empty | {"l": 0, "b": 0, "m": 0}, empty | {"gps": 0}

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

    @property
    def walk(self) -> int:
        return int(self.entry.options.get(CONF_WALK, self.entry.data.get(CONF_WALK, DEFAULT_WALK)))

    async def _get(self, url: str, params: dict[str, Any]) -> Any:
        async with self.session.get(url, params=params, timeout=20) as resp:
            resp.raise_for_status()
            text = await resp.text()
            cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
            return json.loads(cleaned)

    async def _async_update_data(self) -> dict[str, Any]:
        now = datetime.now(NY)
        try:
            arrivals_raw = await self._get(
                ARRIVALS_URL, {"station": self.station, "results": 8}
            )
            nta_raw = await self._get(
                NTA_URL,
                {"req1": self.station, "req2": self.destination, "req3": 6},
            )
            alerts_raw = await self._get(ALERTS_URL, {})
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"SEPTA request failed: {err}") from err

        north, south = _parse_arrivals(arrivals_raw)
        commute = _parse_nta(nta_raw, now)
        alerts = _parse_alerts(alerts_raw, self.station)
        buses = await self._load_buses(now)
        metro, trolley = await self._load_metro()

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
        if any(a.get("suspended") for a in alerts):
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
            "commute": commute,
            "alerts": alerts,
            "next_south": next_s,
            "next_north": next_n,
            "next_commute": next_c,
            "next_bus": next_bus,
            "buses": buses,
            "leave_in": leave,
            "status": status,
            "metro": metro,
            "trolley": trolley,
            "updated": now.isoformat(),
        }


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
        "track": str(raw.get("track_change") or raw.get("track") or ""),
        "sched_dt": sched,
        "minutes": None,
    }


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
