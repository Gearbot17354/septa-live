# SEPTA Transit for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Pulls live SEPTA Regional Rail arrivals, nearby bus departures, Metro, trolley, walk-window times, delays, and alerts into Home Assistant. Ships with ready-made Lovelace cards and a Bubble-style builder.

## Install with HACS (recommended)

This is a **custom repository** — the same way most community plugins are installed. It is not in the default HACS store.

1. Open **HACS → Integrations**.
2. Open the three-dot menu → **Custom repositories**.
3. Paste `https://github.com/Gearbot17354/septa-live`.
4. Category: **Integration**.
5. **Add**, then find **SEPTA Transit** and **Download** **1.10.0**.
6. **Restart Home Assistant**.
7. **Settings → Devices & Services → Add Integration → SEPTA Transit**.
8. Pick a station (for example Lansdale) and a destination (Jefferson Station) used for the leave-now countdown.
9. Turn on only the services you use: **Regional Rail**, **Buses**, **Metro**, **Trolley**. Lansdale defaults to rail + buses (no trolley).
10. Edit a dashboard → **Add card** → search **SEPTA**.

To change this later: **Settings → Devices & Services → SEPTA Transit → Configure**. Disabled services are not polled and their sensors are removed.

Repo: [github.com/Gearbot17354/septa-live](https://github.com/Gearbot17354/septa-live)

If Add card still does not list SEPTA Transit, enable Advanced Mode in your profile, then **Settings → Dashboards → ⋮ → Resources → Add**:

```
/local/septa-live-card.js?v=1.10.0
type: module
```

Hard-refresh the dashboard (or open it in a private window).

## Sidebar app

After you restart, **SEPTA** shows up in the left menu. That page is the live board (inbound, outbound, bus, leave-in, and the departure list) plus setup for destination, walk time, and which services to poll.

Turn the menu item off from the page (**Show in sidebar**) or from **Settings → Devices & Services → SEPTA Transit → Configure → Show SEPTA in the sidebar**. Turn it back on the same way. The page is always at `/septa-live` even when the menu item is hidden.

## What's new in 1.10.0

- **Which train am I on.** Pick your phone's `device_tracker` (or a `person`) under Configure. After two moving fixes near a TrainView train, `binary_sensor.septa_<station>_riding` turns on and `sensor.septa_<station>_my_train` shows the train number.
- The new **SEPTA Transit My Train** card hides until you are actually on board. It shows the train, line, destination, delay, next stop, and the next remaining stops.
- Boarded and exited events: `septa_live_train_boarded` and `septa_live_train_exited`.
- Saving options still does not reload the integration, and the options form no longer wipes sidebar watches or line picks.

## What's new in 1.9.13

- Save no longer crashes. The options handler was missing an import, so every Save raised before it could store anything.

## What's new in 1.9.12

- Save no longer reloads the integration. New and removed lines add or delete their sensors in place, and the board updates from the coordinator without leaving the sidebar.

## What's new in 1.9.11

- Save no longer crashes with "Unknown error" when you change or remove a line.
- Bus schedules that SEPTA returns with an error status are kept, so a route like the 118 can show its next trip.

## What's new in 1.9.10

- Bus home stop and commute-to are dropdowns. Picking a route loads that route's stops, not only stops near the rail station.
- Save waits for the new board, then the sidebar updates without a browser refresh.
- Minus, then Save, deletes that line's sensors from the SEPTA device.

## What's new in 1.9.9

- Narrow cards no longer stack the clock on top of the status. Times stay on one line, and a tight card drops the late label under the time.
- Departure rows keep time, destination, platform, and expected in their own columns.
- The live map no longer falls back to the tile set that stamps "API key required" over the trains.

## What's new in 1.9.8

- A SEPTA API miss no longer marks every sensor unavailable. The board keeps the scheduled trains.
- Cards ignore unavailable entities instead of drawing a blank "On time" row.
- Save refreshes the sidebar board in place, without a manual page reload.

## What's new in 1.9.7

- Line badges use the short colored codes from the webpage, such as green LAN instead of LANSDALE/DOYLESTOWN.
- Save stays on the SEPTA page instead of reloading you out of the sidebar app.

## What's new in 1.9.6

- An extra rail line shows inbound and outbound cards, including the overnight schedule, the same way the webpage does.
- Those cards are also sensors on the SEPTA device: Warminster inbound and Warminster outbound.

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
| **SEPTA Transit My Train** | The train you are riding. Hidden until you board, unless `show_idle: true` |
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
| My train | train number while you are riding, otherwise empty. Attributes: line, destination, next stop, late minutes, consist, remaining stops |
| Riding | on while the phone is matched to that train (`binary_sensor.septa_<station>_riding`) |

Object ids stay `sensor.septa_<station>_my_train` and `binary_sensor.septa_<station>_riding`. If Home Assistant prefixes an area, the card still finds `sensor.<area>_septa_<station>_my_train`.

## Which train am I on

In **Settings → Devices & Services → SEPTA Transit → Configure**, set **Phone tracker** to the Companion app's `device_tracker` (or the `person` that uses it). Leave it empty and nothing extra is created: no listeners, no extra SEPTA calls, no new entities.

The integration compares that tracker's existing Home Assistant location to SEPTA TrainView. It does not run a separate location service and it does not put your coordinates on the sensor. Attributes include distance, train, and stops only.

Defaults: within 300 m (plus a little slack when the train position is a few seconds old), at least 15 mph, two fixes in a row on the same train, ignore GPS worse than 100 m. A heading check drops the train going the other way on the same track.

While you are riding, or a candidate is pending, or the phone is at a station on your line, TrainView is checked every 30 seconds. The normal board refresh stays on whatever interval you set.

Events fire once per board and once per exit:

```yaml
alias: SEPTA - boarded notification
triggers:
  - trigger: event
    event_type: septa_live_train_boarded
actions:
  - action: notify.mobile_app_ryans_iphone
    data:
      title: "🚆 Train {{ trigger.event.data.train }}"
      message: >-
        You're on train {{ trigger.event.data.train }} to {{ trigger.event.data.destination }},
        {{ 'on time' if trigger.event.data.late_min|int(0) <= 0 else trigger.event.data.late_min ~ ' min late' }},
        next stop {{ trigger.event.data.next_stop }}
      data:
        url: "/dashboard-home/0#train"
        clickAction: "/dashboard-home/0#train"
        push:
          interruption-level: time-sensitive
```

Replace `notify.mobile_app_ryans_iphone` with your Companion notify service. Tapping the notification opens the dashboard hash. It does not force a pop-up on an idle screen; that needs browser_mod, which this does not assume.

Bubble Card pop-up (use the entity id Home Assistant actually created if it prefixed an area):

```yaml
type: vertical-stack
cards:
  - type: custom:bubble-card
    card_type: pop-up
    hash: "#train"
    name: My train
    icon: mdi:train
  - type: custom:septa-live-my-train
    entity: sensor.server_rack_septa_lansdale_my_train
```

On a sections dashboard the reliable hide is a visibility condition, because a hidden custom card can still leave an empty slot:

```yaml
type: custom:septa-live-my-train
entity: sensor.septa_lansdale_my_train
visibility:
  - condition: state
    entity: binary_sensor.septa_lansdale_riding
    state: "on"
```

### Phone location

Detection is only as good as the Companion app's updates. The "allow location" popup is the Companion app, not SEPTA.

iPhone has no high-accuracy command. Updates come from significant-location changes (often a few hundred meters and a few minutes), zone enter and exit, background refresh, opening the app, and occasional `request_location_update` pushes. Companion's own docs say not to rely on those pushes.

- Allow Location **Always**, Precise on.
- Add Home Assistant zones about 200–250 m around Lansdale (40.24278, -75.28500) and the usual destination (Jefferson 39.95250, -75.15806; Suburban 39.95389, -75.16778). iOS watches up to 20 regions. Entering or leaving a zone forces a fix when the train arrives or leaves.
- Optional **Ask the phone for a fresh location near a station** (off by default) sends `request_location_update` at most every 2 minutes while a candidate is pending or you are near a station. It does not send it while you are already matched, and the push itself has no coordinates.
- Expect the first match a minute or two after departure. If fixes are sparse, set **Fixes in a row** to 1. The heading check still rejects the opposite train.

Android can turn on high accuracy from a zone automation:

```yaml
alias: SEPTA - high accuracy at the station
triggers:
  - trigger: zone
    entity_id: person.ryan
    zone: zone.lansdale
    event: enter
actions:
  - action: notify.mobile_app_ryans_phone
    data:
      message: command_high_accuracy_mode
      data:
        command: turn_on
```

Turn it off on zone exit, or when `septa_live_train_exited` fires. `high_accuracy_update_interval` can go as low as 5 seconds.

`last_updated` on the tracker has to change when a fix arrives. A position that does not bump `last_updated` is ignored.

## Privacy

- **No API keys.** Maps use OpenStreetMap (Esri as a fallback). SEPTA’s live APIs are public.
- **No Home Assistant tokens.** Lovelace cards read sensors already in your HA; they do not need a long-lived access token.
- **Your commute stays in Home Assistant.** Station and destination are config-entry options on your machine, not committed here. Sample YAML uses Lansdale only as an example.
- **Map GPS is vehicles, not you.** The map plots SEPTA train/bus/trolley positions. It does not upload phone location.
- **Ride detection stays in Home Assistant.** The phone position already in your Companion `device_tracker` is compared locally to TrainView. It is not logged, not stored on the sensor, and not sent anywhere new. The location permission popup is the Companion app, not this integration.
