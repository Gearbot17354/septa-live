"""Constants for SEPTA Live."""

from typing import Final

DOMAIN: Final = "septa_live"
PLATFORMS: Final = ["sensor"]

CONF_STATION: Final = "station"
CONF_DESTINATION: Final = "destination"
CONF_WALK: Final = "walk_minutes"
CONF_SCAN: Final = "scan_interval"

DEFAULT_STATION: Final = "Lansdale"
DEFAULT_DESTINATION: Final = "Jefferson Station"
DEFAULT_WALK: Final = 8
DEFAULT_SCAN: Final = 60

ARRIVALS_URL: Final = "https://www3.septa.org/api/Arrivals/index.php"
NTA_URL: Final = "https://www3.septa.org/api/NextToArrive/index.php"
ALERTS_URL: Final = "https://www3.septa.org/api/Alerts/index.php"
STOPS_URL: Final = "https://www3.septa.org/api/Stops/index.php"
LOCATIONS_URL: Final = "https://www3.septa.org/api/locations/get_locations.php"
BUS_SCHEDULES_URL: Final = "https://www3.septa.org/api/BusSchedules/index.php"
TRANSITVIEW_URL: Final = "https://www3.septa.org/api/TransitView/index.php"
V2_TRIPS_URL: Final = "https://www3.septa.org/api/v2/trips/"
METRO_ROUTE_IDS: Final = ["L1", "B1", "B2", "B3", "M1"]
TROLLEY_ROUTE_IDS: Final = ["T1", "T2", "T3", "T4", "T5", "G1", "D1", "D2"]
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
