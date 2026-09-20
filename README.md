# SEPTA Live for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Pulls live SEPTA Regional Rail arrivals, nearby bus departures, Metro, trolley, commute times, delays, and alerts into Home Assistant. Ships with ready-made Lovelace cards and a Bubble-style builder.

## Install with HACS (recommended)

This is a **custom repository** — the same way most community plugins are installed. It is not in the default HACS store.

1. Open **HACS → Integrations**.
2. Open the three-dot menu → **Custom repositories**.
3. Paste `https://github.com/Gearbot17354/septa-live`.
4. Category: **Integration**.
5. **Add**, then find **SEPTA Live** and **Download** **1.4.6**.
6. **Restart Home Assistant**.
7. **Settings → Devices & Services → Add Integration → SEPTA Live**.
8. Pick a station (for example Lansdale) and commute destination (Jefferson Station).
9. Edit a dashboard → **Add card** → search **SEPTA**.

Repo: [github.com/Gearbot17354/septa-live](https://github.com/Gearbot17354/septa-live)

If Add card still does not list SEPTA Live, enable Advanced Mode in your profile, then **Settings → Dashboards → ⋮ → Resources → Add**:

```
/local/septa-live-card.js?v=1.4.6
type: module
```

Hard-refresh the dashboard (or open it in a private window).

## Manual install (zip)

1. Download `septa_live.zip` from [Releases](https://github.com/Gearbot17354/septa-live/releases).
2. Unzip it into `config/custom_components/septa_live/` (create that folder).
3. Restart Home Assistant.
4. **Settings → Devices & Services → Add Integration → SEPTA Live**.

## Ready-made cards

Search **SEPTA** in Add card. These drop in with your sensors already wired:

| Card | What you get |
| --- | --- |
| **SEPTA Live Commute** | Hero card for your next train |
| **SEPTA Live Next Bus** | Next bus at the nearest stop |
| **SEPTA Live Leave** | Walk-window countdown |
| **SEPTA Live Southbound** | Next inbound / south |
| **SEPTA Live Northbound** | Next outbound / north |
| **SEPTA Live Status** | On time, delay, or alert |
| **SEPTA Live Board** | Train, leave-now, both directions, bus |
| **SEPTA Live Glance** | Commute, leave, bus, status in one row |
| **SEPTA Live Metro** | L, B, M plus trolleys |
| **SEPTA Live Trolley** | T, G, and D |
| **SEPTA Live Bubble** | Build your own from those pieces |

YAML if you want to paste:

```yaml
type: custom:septa-live-board
name: SEPTA Lansdale
commute: sensor.septa_lansdale_commute
south: sensor.septa_lansdale_next_southbound
north: sensor.septa_lansdale_next_northbound
bus: sensor.septa_lansdale_next_bus
leave: sensor.septa_lansdale_leave_in
status: sensor.septa_lansdale_status
```

```yaml
type: custom:septa-live-metro
name: SEPTA Metro
modules:
  - metro
  - trolley
  - status
```

A full view YAML is in `dashboards/septa.yaml`.

## Entities

Each station creates a device with:

| Entity | State |
| --- | --- |
| Next Southbound | minutes until departure |
| Next Northbound | minutes until departure |
| Commute | minutes until the next train to your destination |
| Leave in | commute minus your walk time |
| Status | On Time / delay / alert |
| Next Bus | minutes until the next bus near the station |
| Metro | number of L / B / M trips in service |
| Trolley | number of T / G / D vehicles reporting |

Train attributes include train number, destination, track, scheduled time, and delay. The Next Bus sensor includes route, destination, stop name, clock, live delay, and whether the time is GPS-backed.

Nearby bus stops are discovered from the rail station coordinates. Routes such as 132 and 96 at Lansdale show up automatically.

Data is fetched from SEPTA’s public Arrivals, NextToArrive, TrainView, Alerts, BusSchedules, locations, TransitView, and Metro v2 trip APIs.
