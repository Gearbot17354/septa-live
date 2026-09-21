# SEPTA Transit for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Pulls live SEPTA Regional Rail arrivals, nearby bus departures, Metro, trolley, walk-window times, delays, and alerts into Home Assistant. Ships with ready-made Lovelace cards and a Bubble-style builder.

## Install with HACS (recommended)

This is a **custom repository** — the same way most community plugins are installed. It is not in the default HACS store.

1. Open **HACS → Integrations**.
2. Open the three-dot menu → **Custom repositories**.
3. Paste `https://github.com/Gearbot17354/septa-live`.
4. Category: **Integration**.
5. **Add**, then find **SEPTA Transit** and **Download** **1.8.5**.
6. **Restart Home Assistant**.
7. **Settings → Devices & Services → Add Integration → SEPTA Transit**.
8. Pick a station (for example Lansdale) and a destination (Jefferson Station) used for the leave-now countdown.
9. Turn on only the services you use: **Regional Rail**, **Buses**, **Metro**, **Trolley**. Lansdale defaults to rail + buses (no trolley).
10. Edit a dashboard → **Add card** → search **SEPTA**.

To change this later: **Settings → Devices & Services → SEPTA Transit → Configure**. Disabled services are not polled and their sensors are removed.

Repo: [github.com/Gearbot17354/septa-live](https://github.com/Gearbot17354/septa-live)

If Add card still does not list SEPTA Transit, enable Advanced Mode in your profile, then **Settings → Dashboards → ⋮ → Resources → Add**:

```
/local/septa-live-card.js?v=1.8.5
type: module
```

Hard-refresh the dashboard (or open it in a private window).

## Manual install (zip)

1. Download `septa_live.zip` from [Releases](https://github.com/Gearbot17354/septa-live/releases).
2. Unzip it into `config/custom_components/septa_live/` (create that folder).
3. Restart Home Assistant.
4. **Settings → Devices & Services → Add Integration → SEPTA Transit**.

## Ready-made cards

Search **SEPTA** in Add card. These drop in with your sensors already wired. Cards use SEPTA Metro’s official line squares (**L** blue, **B** orange, **M** purple, **T** green, **G** yellow, **D** pink) plus the circle mode marks (Metro, Bus, Regional Rail, Trolley).

| Card | What you get |
| --- | --- |
| **SEPTA Transit Train** | Hero card for the next inbound train |
| **SEPTA Transit Next Bus** | Next bus at the nearest stop |
| **SEPTA Transit Leave** | Walk-window countdown |
| **SEPTA Transit Inbound** | Next train into Center City |
| **SEPTA Transit Outbound** | Next train out of Center City |
| **SEPTA Transit Status** | On time, delay, or alert |
| **SEPTA Transit Board** | Inbound and outbound, two trains each |
| **SEPTA Transit Departures** | Next 5 trains each way, with platform |
| **SEPTA Transit Glance** | Leave, inbound, bus, status in one row |
| **SEPTA Transit Metro** | L, B, M plus trolleys |
| **SEPTA Transit Trolley** | T, G, and D |
| **SEPTA Transit Map** | Live GPS map on OpenStreetMap (no API key) |
| **SEPTA Transit Bubble** | Build your own from those pieces |

YAML if you want to paste:

```yaml
type: custom:septa-live-board
name: SEPTA Lansdale
south: sensor.septa_lansdale_next_southbound
north: sensor.septa_lansdale_next_northbound
bus: sensor.septa_lansdale_next_bus
leave: sensor.septa_lansdale_leave_in
status: sensor.septa_lansdale_status
```

```yaml
type: custom:septa-live-departures
name: Lansdale Regional Rail
south: sensor.septa_lansdale_southbound_board
north: sensor.septa_lansdale_northbound_board
```

```yaml
type: custom:septa-live-metro
name: SEPTA Metro
modules:
  - metro
  - trolley
  - status
```

```yaml
type: custom:septa-live-map
entity: sensor.septa_lansdale_map
name: Live map
```

A full view YAML is in `dashboards/septa.yaml`.

## Entities

Each station creates a device with:

| Entity | State |
| --- | --- |
| Next Inbound | minutes until the next train into Center City |
| Next Outbound | minutes until the next train out of Center City |
| Inbound Board | next inbound clock and track; `trains` lists up to 5 with platform |
| Outbound Board | next outbound clock and track; `trains` lists up to 5 with platform |
| Leave in | minutes until you should walk out (next train to your destination minus walk time) |
| Status | On Time / delay / alert |
| Next Bus | minutes until the next bus near the station |
| Metro | number of L / B / M trips in service |
| Trolley | number of T / G / D vehicles reporting |
| Map | number of GPS vehicles; `vehicles` lists lat/lon for the live map card |

Train attributes include train number, destination, track / platform, scheduled time, and delay. Board sensors expose a `trains` list of up to five upcoming trips. The Next Bus sensor includes route, destination, stop name, clock, live delay, and whether the time is GPS-backed. Leave in includes the train number, depart/arrive times, and destination.

Nearby bus stops are discovered from the rail station coordinates. Routes such as 132 and 96 at Lansdale show up automatically.

Data is fetched from SEPTA’s public Arrivals, NextToArrive, TrainView, Alerts, BusSchedules, locations, TransitView, and Metro v2 trip APIs.
