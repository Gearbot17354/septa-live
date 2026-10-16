"""Download the Regional Rail timetable and swap it in without touching live trains."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import (
    CONF_GTFS_URL,
    DOMAIN,
    GTFS_URL,
    SCHEDULE_MAX_BYTES,
    SCHEDULE_NEAR_DAYS,
    SCHEDULE_REFRESH_DAYS,
    SCHEDULE_STARTUP_DELAY_S,
)
from .coordinator import cached_schedule, set_cached_schedule
from .dynamic import legacy_non_rail, rail_picker_options
from .schedule import MAX_BYTES, ScheduleBook, build_schedule, read_schedule_file, shapes_needed, shapes_retry_unconditional, stamp, write_schedule_file
from .shapes import SHAPES_FORMAT, absorb_shapes, attach_route, cleared_route, read_shapes_file, write_shapes_file

_LOGGER = logging.getLogger(__name__)
_KEEPER = "septa_live_rail_schedule"
_STORAGE = "septa_live_rail_schedule.json"
_SHAPES = "septa_live_rail_shapes.json"
_LEGACY_LOGGED: set[str] = set()


def active_schedule(hass: HomeAssistant) -> dict:
    keeper = hass.data.get(_KEEPER)
    book = getattr(keeper, "book", None)
    if book is not None and isinstance(book.schedule, dict) and book.schedule.get("stations"):
        return book.schedule
    return cached_schedule()


def rail_names(hass: HomeAssistant, line: str | None = None, fallback: list[str] | None = None) -> list[str]:
    return rail_picker_options(active_schedule(hass), fallback or [], line)


class RailSchedule:
    """One shared timetable for every config entry."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.book = ScheduleBook()
        self.path = Path(hass.config.path(".storage", _STORAGE))
        self.shapes_path = Path(hass.config.path(".storage", _SHAPES))
        self.shapes: dict = {"shapes": {}, "trains": {}, "routes": {}}
        self.shape_memo: dict = {}
        self.shapes_built: str | None = None
        self.shapes_error: str | None = None
        self._shapes_after = 0.0
        self._shapes_fails = 0
        self._shapes_warn_day = ""
        self._shapes_logged = False
        self._unsubs: list = []
        self._running = False

    def async_stop(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001
                continue
        self._unsubs.clear()

    async def async_start(self) -> None:
        await self.hass.async_add_executor_job(self._load_local)
        self._unsubs.append(async_call_later(self.hass, SCHEDULE_STARTUP_DELAY_S, self._kick))
        self._unsubs.append(async_track_time_interval(self.hass, self._daily, timedelta(days=1)))

    def _load_local(self) -> None:
        from .coordinator import _load_schedule

        bundled = _load_schedule()
        cached = read_schedule_file(self.path)
        if cached is None:
            previous = Path(self.hass.config.path(".storage", f"{DOMAIN}_schedule.json"))
            cached = read_schedule_file(previous)
        self.book.load(bundled, cached, date.today())
        if self.book.schedule.get("stations"):
            set_cached_schedule(self.book.schedule)
        loaded = read_shapes_file(self.shapes_path)
        self.shapes = loaded or {"shapes": {}, "trains": {}, "routes": {}, "format": 0}
        self.shape_memo = {}
        if isinstance(loaded, dict) and loaded.get("format"):
            self.shapes_built = loaded.get("built")

    async def _kick(self, _now) -> None:
        await self.async_refresh(force=False)

    async def _daily(self, _now) -> None:
        await self.async_refresh(force=False)

    def _url(self) -> str:
        data = self.hass.data.get(DOMAIN) or {}
        for coordinator in data.values():
            entry = getattr(coordinator, "entry", None)
            options = getattr(entry, "options", None) or {}
            custom = str(options.get(CONF_GTFS_URL) or "").strip()
            if custom:
                return custom
        return GTFS_URL

    async def async_refresh(self, force: bool = False) -> None:
        if self._running:
            return
        today = datetime.now().astimezone().date()
        try:
            from .coordinator import NY

            today = datetime.now(NY).date()
        except Exception:  # noqa: BLE001
            pass
        want_timetable = self.book.should_fetch(today, SCHEDULE_REFRESH_DAYS, force=force)
        want_shapes = shapes_needed(self.shapes, SHAPES_FORMAT)
        if want_shapes and not want_timetable and not force and time.time() < self._shapes_after:
            return
        if not want_timetable and not want_shapes and not force:
            return
        self._running = True
        now = datetime.now().astimezone().isoformat()
        try:
            fetched = await self._download(self._url(), conditional=not want_shapes)
            if shapes_retry_unconditional(fetched.get("status"), self.shapes, SHAPES_FORMAT):
                fetched = await self._download(self._url(), conditional=False)
            if fetched.get("status") == 304 and not want_shapes:
                self.book.note_not_modified(now)
                if fetched.get("etag"):
                    self.book.etag = fetched.get("etag")
                return
            if fetched.get("error") or not fetched.get("body"):
                if want_timetable:
                    self.book.fail(now, fetched.get("error") or "download")
                if want_shapes:
                    self._shapes_fail(fetched.get("error") or "download")
                return
            await self._store_shapes(fetched["body"], now)
            if not want_timetable and not force:
                return
            try:
                built = await self.hass.async_add_executor_job(build_schedule, fetched["body"])
            except ValueError as err:
                self.book.fail(now, str(err) or "parse")
                return
            if not self.book.accept(built, now, today):
                return
            self.book.etag = fetched.get("etag") or self.book.etag
            self.book.modified = fetched.get("modified") or self.book.modified
            payload = {
                "fetched_at": now,
                "etag": self.book.etag,
                "modified": self.book.modified,
                "schedule": self.book.schedule,
            }
            await self.hass.async_add_executor_job(write_schedule_file, self.path, payload)
            set_cached_schedule(self.book.schedule)
            await self._publish()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("SEPTA timetable refresh failed: %s", err)
            self.book.fail(now, "download")
            if want_shapes:
                self._shapes_fail("download")
        finally:
            self._running = False
            self._sync_issue()

    async def _store_shapes(self, blob: bytes, now: str) -> None:
        shapes, err = await self.hass.async_add_executor_job(absorb_shapes, self.shapes, blob)
        if err or not isinstance(shapes, dict) or not (shapes.get("trains") or {}):
            self._shapes_fail(err or "shapes")
            return
        shapes = dict(shapes)
        shapes["format"] = SHAPES_FORMAT
        shapes["built"] = now
        self.shapes = shapes
        self.shape_memo = {}
        self.shapes_built = now
        self.shapes_error = None
        self._shapes_fails = 0
        self._shapes_after = 0.0
        count = len(shapes.get("trains") or {})
        if not self._shapes_logged:
            self._shapes_logged = True
            _LOGGER.info("SEPTA route shapes ready: %s trains", count)
        try:
            await self.hass.async_add_executor_job(write_shapes_file, self.shapes_path, self.shapes)
        except Exception:  # noqa: BLE001
            _LOGGER.warning("SEPTA route shape cache was not saved")
            self.shapes_error = "shapes"

    def _shapes_fail(self, reason: str) -> None:
        self.shapes_error = str(reason or "shapes")
        self._shapes_fails += 1
        delay = 30 * 60 if self._shapes_fails <= 1 else 24 * 3600
        self._shapes_after = time.time() + delay
        today = date.today().isoformat()
        if self._shapes_warn_day != today:
            self._shapes_warn_day = today
            _LOGGER.warning("SEPTA route shapes were not built: %s", self.shapes_error)

    async def _download(self, url: str, conditional: bool = True) -> dict:
        session = async_get_clientsession(self.hass)
        headers = {"User-Agent": "septa-live"}
        if conditional and self.book.etag:
            headers["If-None-Match"] = self.book.etag
        if conditional and self.book.modified:
            headers["If-Modified-Since"] = self.book.modified
        try:
            async with session.get(url, headers=headers, timeout=60) as resp:
                if resp.status == 304:
                    return {
                        "status": 304,
                        "etag": resp.headers.get("ETag") or self.book.etag,
                        "modified": resp.headers.get("Last-Modified") or self.book.modified,
                    }
                if resp.status != 200:
                    return {"status": resp.status, "error": f"http {resp.status}"}
                length = resp.content_length or 0
                if length and length > SCHEDULE_MAX_BYTES:
                    return {"status": 200, "error": "too_large"}
                body = bytearray()
                async for chunk in resp.content.iter_chunked(65536):
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        return {"status": 200, "error": "too_large"}
                return {
                    "status": 200,
                    "body": bytes(body),
                    "etag": resp.headers.get("ETag"),
                    "modified": resp.headers.get("Last-Modified"),
                }
        except Exception as err:  # noqa: BLE001
            return {"error": str(err) or "download"}

    async def _publish(self) -> None:
        data = self.hass.data.get(DOMAIN) or {}
        for coordinator in data.values():
            board = getattr(coordinator, "dynamic", None)
            if board is not None and hasattr(board, "async_reload_schedule"):
                try:
                    await board.async_reload_schedule()
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("SEPTA schedule reload skipped", exc_info=True)
            elif board is not None and hasattr(board, "reload_schedule"):
                try:
                    board.reload_schedule()
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("SEPTA schedule reload skipped", exc_info=True)
            if hasattr(coordinator, "async_request_refresh"):
                try:
                    await coordinator.async_request_refresh()
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("SEPTA coordinator refresh skipped", exc_info=True)
            if board is not None and hasattr(board, "async_refresh"):
                try:
                    await board.async_refresh(force=True)
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("SEPTA day-train refresh skipped", exc_info=True)

    def _sync_issue(self) -> None:
        try:
            from homeassistant.helpers import issue_registry as ir
        except ImportError:
            return
        try:
            today = date.today()
            if self.book.needs_repair(today, SCHEDULE_NEAR_DAYS):
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "rail_schedule_stale",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="rail_schedule_stale",
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, "rail_schedule_stale")
        except Exception:  # noqa: BLE001
            _LOGGER.debug("SEPTA schedule repair issue skipped", exc_info=True)

    def route_for(self, data: dict) -> dict:
        try:
            if not isinstance(self.shape_memo, dict):
                self.shape_memo = {}
            try:
                from .ride import _load_geo

                geo = _load_geo()
            except Exception:  # noqa: BLE001
                geo = {}
            return attach_route(data if isinstance(data, dict) else {}, self.shapes or {}, self.shape_memo, geo=geo)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("SEPTA route shape skipped", exc_info=True)
            missed = cleared_route()
            missed["route_shape_reason"] = "exception"
            missed["route_shape_source"] = "none"
            return missed

    def status(self) -> dict:
        try:
            from .coordinator import NY

            today = datetime.now(NY).date()
        except Exception:  # noqa: BLE001
            today = date.today()
        payload = self.book.sensor(today)
        for key in ("last_check", "last_success"):
            payload[key] = stamp(payload.get(key))
        payload["shapes_trains"] = len((self.shapes or {}).get("trains") or {})
        payload["shapes_built"] = self.shapes_built
        payload["shapes_error"] = self.shapes_error
        return payload


async def async_attach_schedule(hass: HomeAssistant, coordinator) -> RailSchedule:
    keeper = hass.data.get(_KEEPER)
    if keeper is None:
        keeper = RailSchedule(hass)
        hass.data[_KEEPER] = keeper
        await keeper.async_start()
    coordinator.rail_schedule = keeper
    return keeper


def async_detach_schedule(hass: HomeAssistant) -> None:
    if hass.data.get(DOMAIN):
        return
    keeper = hass.data.pop(_KEEPER, None)
    if keeper is not None:
        keeper.async_stop()


def audit_saved_stations(hass: HomeAssistant, entry) -> None:
    """Leave a Metro-only saved value in place and point at the options flow."""
    from .const import METRO_STATIONS, TROLLEY_STATIONS

    schedule = active_schedule(hass)
    values: list[str] = []
    data = dict(getattr(entry, "data", None) or {})
    options = dict(getattr(entry, "options", None) or {})
    for key in ("station", "destination", "home_station", "default_city_station"):
        values.append(str(data.get(key) or options.get(key) or ""))
    riders = options.get("riders_cfg") if isinstance(options.get("riders_cfg"), dict) else {}
    for cfg in riders.values():
        if not isinstance(cfg, dict):
            continue
        for key in ("home_station", "city_station", "default_destination"):
            values.append(str(cfg.get(key) or ""))
    bad = legacy_non_rail(values, schedule, list(METRO_STATIONS), list(TROLLEY_STATIONS))
    try:
        from homeassistant.helpers import issue_registry as ir
    except ImportError:
        return
    issue_id = "rail_station_legacy"
    if not bad:
        try:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
        except Exception:  # noqa: BLE001
            return
        return
    token = f"{getattr(entry, 'entry_id', '')}:{bad[0]}"
    if token not in _LEGACY_LOGGED:
        _LEGACY_LOGGED.add(token)
        _LOGGER.warning("SEPTA saved station %s is not Regional Rail. It was left unchanged.", bad[0])
    try:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="rail_station_legacy",
            translation_placeholders={"station": bad[0]},
        )
    except Exception:  # noqa: BLE001
        _LOGGER.debug("SEPTA station repair issue skipped", exc_info=True)
