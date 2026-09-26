"""Constants for SEPTA Transit."""

from typing import Final

DOMAIN: Final = "septa_live"
PLATFORMS: Final = ["sensor"]

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

