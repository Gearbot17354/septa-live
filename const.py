"""Constants for SEPTA Transit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

_VERSION: str | None = None


def integration_version() -> str:
    """Manifest version, read once. Riding sensors expose this."""
    global _VERSION
    if _VERSION:
        return _VERSION
    path = Path(__file__).with_name("manifest.json")
    try:
        _VERSION = str(json.loads(path.read_text()).get("version") or "")
    except (OSError, ValueError):
        _VERSION = ""
    return _VERSION

DOMAIN: Final = "septa_live"
PLATFORMS: Final = ["sensor", "binary_sensor", "device_tracker"]

CONF_STATION: Final = "station"
CONF_DESTINATION: Final = "destination"
CONF_WALK: Final = "walk_minutes"
CONF_SCAN: Final = "scan_interval"
CONF_SHOW_RAIL: Final = "show_rail"
CONF_SHOW_BUS: Final = "show_bus"
CONF_SHOW_METRO: Final = "show_metro"
CONF_SHOW_TROLLEY: Final = "show_trolley"
CONF_BUS_DEST: Final = "bus_destination"
CONF_BUS_STOP: Final = "bus_stop"
CONF_METRO_STATION: Final = "metro_station"
CONF_METRO_DEST: Final = "metro_destination"
CONF_TROLLEY_STATION: Final = "trolley_station"
CONF_TROLLEY_DEST: Final = "trolley_destination"
CONF_SIDEBAR: Final = "show_sidebar"
CONF_RAIL_LINE: Final = "rail_line"
CONF_BUS_LINE: Final = "bus_line"
CONF_METRO_LINE: Final = "metro_line"
CONF_TROLLEY_LINE: Final = "trolley_line"
CONF_WATCHES: Final = "watches"
CONF_TRIPS: Final = "trips"
MAX_TRIPS: Final = 20
MAX_TRIP_COUNT: Final = 20
DEFAULT_TRIP_COUNT: Final = 4
CONF_HOME_STATION: Final = "home_station"
CONF_DEFAULT_CITY: Final = "default_city_station"
CONF_NEAR_RADIUS: Final = "near_radius_m"
CONF_GOING_HOME_COUNT: Final = "going_home_count"
CONF_TRANSFER_MIN: Final = "transfer_min"
CONF_EVENT_BUFFER: Final = "event_buffer_min"
CONF_EVENT_LOOKAHEAD: Final = "event_lookahead_h"
CONF_EVENT_WALK_SPEED: Final = "event_walk_speed"
CONF_DAY_WINDOW: Final = "day_window"
CONF_RIDERS_CFG: Final = "riders_cfg"
CONF_GEOCODE: Final = "geocode"
CONF_MAX_TRAINS: Final = "max_trains"
DEFAULT_NEAR_RADIUS: Final = 1500
DEFAULT_GOING_HOME_COUNT: Final = 6
DEFAULT_TRANSFER_MIN: Final = 3
DEFAULT_EVENT_BUFFER: Final = 15
DEFAULT_EVENT_LOOKAHEAD: Final = 24
DEFAULT_EVENT_WALK_SPEED: Final = 80
DEFAULT_DAY_WINDOW: Final = "rest_of_day"
DEFAULT_MAX_TRAINS: Final = 60
# Recorder skips these. The live state still has them for dashboards.
UNRECORDED_TRAIN_ATTRS: Final = frozenset(
    {
        "trains",
        "trips",
        "suggested",
        "candidates",
        "day",
        "remaining_stops",
        "route_shape",
        "stops",
    }
)
ORIGIN_HYSTERESIS_M: Final = 200
LIVE_WINDOW_MIN: Final = 90
GTFS_RAIL_API: Final = "https://api.github.com/repos/septadev/GTFS/releases/latest"
# Public regional-rail GTFS. google_rail.zip is inside this archive.
GTFS_URL: Final = "https://www3.septa.org/developer/gtfs_public.zip"
CONF_GTFS_URL: Final = "gtfs_url"
SCHEDULE_REFRESH_DAYS: Final = 7
SCHEDULE_NEAR_DAYS: Final = 2
SCHEDULE_MAX_BYTES: Final = 50 * 1024 * 1024
SCHEDULE_STARTUP_DELAY_S: Final = 300
TRAIN_TRACKER_STALE_S: Final = 300
CONF_RIDE_TRACKER: Final = "ride_tracker"
CONF_RIDE_RIDERS: Final = "ride_riders"
CONF_RIDE_ACTIVITY: Final = "ride_activity_sensor"
CONF_RIDE_RADIUS: Final = "ride_radius_m"
CONF_RIDE_MIN_SPEED: Final = "ride_min_speed_mph"
CONF_RIDE_MATCHES: Final = "ride_matches"
CONF_RIDE_MAX_ACCURACY: Final = "ride_max_accuracy_m"
CONF_RIDE_REQUEST: Final = "ride_request_updates"

DEFAULT_RIDE_RADIUS: Final = 300
DEFAULT_RIDE_MIN_SPEED: Final = 15
DEFAULT_RIDE_MATCHES: Final = 2
DEFAULT_RIDE_MAX_ACCURACY: Final = 100

# Ride end. The matcher also accepts these as constructor arguments.
ARRIVAL_RADIUS_M: Final = 250
SLOW_MPH: Final = 5
SLOW_SECONDS: Final = 180
APART_M: Final = 600
APART_FIXES: Final = 2
MAX_RIDE_SECONDS: Final = 3 * 3600
REBOARD_COOLDOWN_S: Final = 600
TERMINAL_GRACE_S: Final = 120

# A fresh TrainView position that is only estimated can still be the train
# you are on, once two fast fixes agree and the heading does.
FRESH_TRAINVIEW_S: Final = 60
SPEED_CONFIRM_MPH: Final = 20
SPEED_CONFIRM_FIXES: Final = 2
SPEED_MATCH_M: Final = 1500
ESTIMATE_SLACK_M: Final = 500

# Stay on the boarded train until it is really gone or the rider changes trains.
RIDE_MISSING_POLLS: Final = 5
BOARD_WINDOW_MIN: Final = 10
MAX_PLAUSIBLE_MPH: Final = 90
MIN_DERIVED_DT_S: Final = 20
STICKY_LIMIT_M: Final = 2000

DEFAULT_STATION: Final = "Lansdale"
DEFAULT_DESTINATION: Final = "Jefferson Station"
DEFAULT_WALK: Final = 8
DEFAULT_SCAN: Final = 60
DEFAULT_SHOW_RAIL: Final = True
DEFAULT_SHOW_BUS: Final = True
DEFAULT_SHOW_METRO: Final = False
DEFAULT_SHOW_TROLLEY: Final = False

ARRIVALS_URL: Final = "https://www3.septa.org/api/Arrivals/index.php"
NTA_URL: Final = "https://www3.septa.org/api/NextToArrive/index.php"
ALERTS_URL: Final = "https://www3.septa.org/api/Alerts/index.php"
STOPS_URL: Final = "https://www3.septa.org/api/Stops/index.php"
LOCATIONS_URL: Final = "https://www3.septa.org/api/locations/get_locations.php"
BUS_SCHEDULES_URL: Final = "https://www3.septa.org/api/BusSchedules/index.php"
TRANSITVIEW_URL: Final = "https://www3.septa.org/api/TransitView/index.php"
TRAINVIEW_URL: Final = "https://www3.septa.org/api/TrainView/index.php"
RRSCHEDULES_URL: Final = "https://www3.septa.org/api/RRSchedules/index.php"
RIDE_FAST_SCAN: Final = 30
V2_TRIPS_URL: Final = "https://www3.septa.org/api/v2/trips/"
METRO_ROUTE_IDS: Final = ["L1", "B1", "B2", "B3", "M1"]
TROLLEY_ROUTE_IDS: Final = ["T1", "T2", "T3", "T4", "T5", "G1", "D1", "D2"]
SERVICE_LINES: Final = {
    "metro": [
        ("L1", "Market–Frankford"),
        ("B1", "Broad Street Local"),
        ("B2", "Broad Street Express"),
        ("B3", "Broad-Ridge Spur"),
        ("M1", "Norristown High Speed"),
    ],
    "trolley": [
        ("T1", "13th St to 63rd–Malvern"),
        ("T2", "13th St to 61st–Baltimore"),
        ("T3", "13th St to Yeadon / Darby"),
        ("T4", "13th St to Darby TC"),
        ("T5", "13th St to 80th–Eastwick"),
        ("G1", "Girard"),
        ("D1", "Media"),
        ("D2", "Sharon Hill"),
    ],
}
RAIL_LINES: Final = [
    "AIR",
    "CHE",
    "CHW",
    "CYN",
    "FOX",
    "LAN",
    "MED",
    "NOR",
    "PAO",
    "TRE",
    "WAR",
    "WTR",
    "WIL",
]

STATIONS: Final = [
    "9th St",
    "30th Street Station",
    "Airport Terminal A",
    "Airport Terminal B",
    "Airport Terminals C & D",
    "Airport Terminals E & F",
    "Ambler",
    "Ardmore",
    "Bryn Mawr",
    "Chalfont",
    "Chestnut Hill East",
    "Chestnut Hill West",
    "Colmar",
    "Conshohocken",
    "Cornwells Heights",
    "Delaware Valley College",
    "Doylestown",
    "Elkins Park",
    "Exton",
    "Fern Rock Transportation Center",
    "Fort Washington",
    "Fox Chase",
    "Glenside",
    "Gwynedd Valley",
    "Hatboro",
    "Jefferson Station",
    "Jenkintown-Wyncote",
    "Lansdale",
    "Levittown",
    "Malvern",
    "Manayunk",
    "Media",
    "Melrose Park",
    "New Britain",
    "North Wales",
    "Norristown Transportation Center",
    "Oreland",
    "Paoli",
    "Penllyn",
    "Pennbrook",
    "Suburban Station",
    "Swarthmore",
    "Temple University",
    "Thorndale",
    "Trenton Transit Center",
    "University City",
    "Warminster",
    "Wayne Junction",
    "West Trenton",
    "Wilmington",
    "Yardley",
]

METRO_STATIONS: Final = [
    "13th St",
    "15th St/City Hall",
    "2nd St",
    "30th Street",
    "5th St/Independence Hall",
    "69th St Transit Center",
    "8th-Market",
    "City Hall",
    "Fern Rock Transit Center",
    "Frankford Transit Center",
    "Girard",
    "Norristown Transportation Center",
    "Olney Transit Center",
    "Walnut-Locust",
    "Wynnefield Avenue",
]

TROLLEY_STATIONS: Final = [
    "13th St",
    "15th St/City Hall",
    "36th St Portal",
    "40th St Portal",
    "63rd-Malvern",
    "69th St Transit Center",
    "Frankford Av & Delaware Av Loop",
    "Girard Av & 31st St",
    "Media",
    "Sharon Hill",
]

