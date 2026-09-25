# SEPTA Transit for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Pulls live SEPTA Regional Rail arrivals, nearby bus departures, Metro, trolley, walk-window times, delays, and alerts into Home Assistant. Ships with ready-made Lovelace cards and a Bubble-style builder.

## Install with HACS (recommended)

This is a **custom repository** — the same way most community plugins are installed. It is not in the default HACS store.

1. Open **HACS → Integrations**.
2. Open the three-dot menu → **Custom repositories**.
3. Paste `https://github.com/Gearbot17354/septa-live`.
4. Category: **Integration**.
5. **Add**, then find **SEPTA Transit** and **Download** **1.9.5**.
6. **Restart Home Assistant**.
7. **Settings → Devices & Services → Add Integration → SEPTA Transit**.
8. Pick a station (for example Lansdale) and a destination (Jefferson Station) used for the leave-now countdown.
9. Turn on only the services you use: **Regional Rail**, **Buses**, **Metro**, **Trolley**. Lansdale defaults to rail + buses (no trolley).
10. Edit a dashboard → **Add card** → search **SEPTA**.

To change this later: **Settings → Devices & Services → SEPTA Transit → Configure**. Disabled services are not polled and their sensors are removed.

Repo: [github.com/Gearbot17354/septa-live](https://github.com/Gearbot17354/septa-live)

If Add card still does not list SEPTA Transit, enable Advanced Mode in your profile, then **Settings → Dashboards → ⋮ → Resources → Add**:

```
/local/septa-live-card.js?v=1.9.5
type: module
```

Hard-refresh the dashboard (or open it in a private window).

## Sidebar app

After you restart, **SEPTA** shows up in the left menu. That page is the live board (inbound, outbound, bus, leave-in, and the departure list) plus setup for destination, walk time, and which services to poll.

Turn the menu item off from the page (**Show in sidebar**) or from **Settings → Devices & Services → SEPTA Transit → Configure → Show SEPTA in the sidebar**. Turn it back on the same way. The page is always at `/septa-live` even when the menu item is hidden.

## What's new in 1.9.5

- Plus and minus on each service add or remove an extra line, and each extra line gets its own sensor.
- Metro and trolley show a commute row and a board card when they are on.

## What's new in 1.9.4

- The sidebar app has the same Show on board and Commute rows as the webpage.
- Saving turns Regional Rail, bus, Metro, and trolley sensors on or off, and limits arrivals to the line you pick.

## What's new in 1.9.3

- Departure platform numbers sit in the Platform column, under the header.

## What's new in 1.9.2

- Sensors keep a stable id, `sensor.septa_<station>_<key>`, even when Home Assistant prefixes the device or area name.
- Cards find those sensors when the id is `sensor.<area>_septa_<station>_metro` (or inbound/outbound board).

## What's new in 1.9.1

- Lovelace cards use the same inset as the webpage bubbles. Clocks stay on one line instead of sitting on the card edge.
- The live map uses CARTO dark tiles so OpenStreetMap's block page no longer fills the card.

## What's new in 1.9.0

- Sidebar **SEPTA** page now uses the same board as the webpage: header, walk time, service chips, commute row, inbound/outbound bubbles, and the departure list.
- It reads the sensors HA actually created, so trains show up instead of empty cards.

## What's new in 1.8.9

- **SEPTA sidebar app** for the live board and commute setup. Toggle it in the side menu.
- Departure cards shrink their columns in narrow dashboard sections so times are not clipped.

## What's new in 1.8.8

- **Next 5 inbound / outbound** bubble cards: same layout as the two-train bubble, with `count: 5`.
- Compact rail departures columns line up (Time, Destination, Trk, Wait).

## What's new in 1.8.7

Rail departures card now matches the live board:

- **Station** picker covers every Regional Rail stop, not only the one you added in HA.
- **Inbound / Outbound** direction dropdown, same as the web board.
- **Compact / Regular / Large** sizes: 3, 5, or 8 trains. Switch on the card or set `size:` in YAML.

## What's new in 1.8.6

Ready-made Lovelace cards now match the live web board:

- **Board** shows inbound and outbound two-train bubbles plus the next bus bubble (clock, delay minutes, Local/Express, destination, track).
- **Inbound / Outbound / Next bus / Leave** cards use that same bubble layout.
- Copy-paste previews on the web app fill from live SEPTA times for your station, not overnight placeholders.

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
| **SEPTA Transit Inbound** | Next two inbound trains, delay minutes, Local/Express |
| **SEPTA Transit Outbound** | Next two outbound trains, delay minutes, Local/Express |
| **SEPTA Transit Status** | On time, delay, or alert |
| **SEPTA Transit Board** | Inbound, outbound, and next bus — same bubbles as the live board |
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
station: Lansdale
direction: south
size: regular
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

Data is fetched from SEPTA’s public Arrivals, NextToArrive, TrainView, Alerts, BusSchedules, locations, TransitView, and Metro v2 trip APIs. No SEPTA, map, or Home Assistant token is stored in this repository.

## Privacy

- **No API keys.** Maps use OpenStreetMap (Esri as a fallback). SEPTA’s live APIs are public.
- **No Home Assistant tokens.** Lovelace cards read sensors already in your HA; they do not need a long-lived access token.
- **Your commute stays in Home Assistant.** Station and destination are config-entry options on your machine, not committed here. Sample YAML uses Lansdale only as an example.
- **Map GPS is vehicles, not you.** The map plots SEPTA train/bus/trolley positions. It does not upload phone location.
