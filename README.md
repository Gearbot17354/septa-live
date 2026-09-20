# SEPTA Live for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Pulls live SEPTA Regional Rail arrivals, nearby bus departures, commute times, delays, and alerts into Home Assistant. Ships with pre-made Lovelace cards that appear under **Add card**.

## Install with HACS (recommended)

This is a **custom repository** — the same way most community plugins are installed. It is not in the default HACS store.

1. Open **HACS → Integrations**.
2. Open the three-dot menu → **Custom repositories**.
3. Paste `https://github.com/Gearbot17354/septa-live`.
4. Category: **Integration**.
5. **Add**, then find **SEPTA Live** and **Download**.
6. **Restart Home Assistant**.
7. **Settings → Devices & Services → Add Integration → SEPTA Live**.
8. Pick a station (for example Lansdale) and commute destination (Jefferson Station).

After restart, edit a dashboard → **Add card** → search **SEPTA Live**.

Repo: [github.com/Gearbot17354/septa-live](https://github.com/Gearbot17354/septa-live)

## Manual install (zip)

1. Copy `custom_components/septa_live` into your Home Assistant `config/custom_components/` folder.
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → SEPTA Live**.

## Pre-made dashboard cards

After restart, Lovelace registers two cards automatically. Edit a dashboard → **Add card** → search **SEPTA Live**:

| Card | What you get |
| --- | --- |
| **SEPTA Live Board** | One card: commute, leave-now, southbound, northbound, and next bus |
| **SEPTA Live** | A single train or bus sensor as a hero card |

If they do not appear, copy `www/septa-live-card.js` (or `custom_components/septa_live/www/septa-live-card.js`) to `config/www/`, add a Lovelace resource (`/local/septa-live-card.js`, type Module), then:

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
type: custom:septa-live-card
entity: sensor.septa_lansdale_commute
```

```yaml
type: custom:septa-live-card
entity: sensor.septa_lansdale_next_bus
name: Next bus
```

Tile fallbacks (no custom card needed):

```yaml
type: tile
entity: sensor.septa_lansdale_next_southbound
name: Next southbound
icon: mdi:train
```

A full view YAML is in `dashboards/septa.yaml`. Paste it as a new dashboard view, or copy a card from the SEPTA Live app’s **Ready-made cards** tab.

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

Train attributes include train number, destination, track, scheduled time, and delay. The Next Bus sensor includes route, destination, stop name, clock, live delay, and whether the time is GPS-backed.

Nearby bus stops are discovered from the rail station coordinates. Routes such as 132 and 96 at Lansdale show up automatically.

Data is fetched from SEPTA’s public Arrivals, NextToArrive, TrainView, Alerts, BusSchedules, locations, and TransitView APIs.
