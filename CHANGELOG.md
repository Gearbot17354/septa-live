# Changelog

## 1.13.9

### Fixed

- Timetable search no longer freezes the Home Assistant event loop on a low-power host. A city-to-home itinerary is indexed once per service day instead of scanning every stop on every refresh.
- A connection shorter than the minimum transfer is no longer chosen ahead of a legal one.
- A train that keeps its number and runs through onto another line is one direct trip, not a zero-minute transfer.
- Direct trains no longer carry a blank transfer object.
- Times after midnight, such as 24:27, are the next calendar day.
- An expected train accepts a line prefix (`LAN5305`) or the bare number (`5305`).

### Changed

- State attributes are smaller. The default cap is 20 trains. Direction sensors no longer repeat both directions. Large lists, including `trains`, `stops`, `vehicles`, and `updated`, are excluded from the recorder.
- Day-train and Going Home skeletons are rebuilt only when the trip changes. Live minutes are overlaid on the cached timetable.

### Added

- Each train row can include `train_number`, `service_type`, `stops_count`, `stops`, `skipped`, and `through`.
- Websocket `septa_live/day_trains` returns the full list when the sensor attribute is capped.
- Diagnostics include a `perf` block: index build time, cache hits, and cache misses.

Existing entities, services, and automations keep working. `trains` on the sensor is capped at the option (20 by default). The full list is on `septa_live/day_trains`.

## 1.13.8

### Added

- The "Into the City" suggestion now counts the walk from the arrival station to your event, so an 8:30 event with a 10-minute buffer and a 10-minute walk suggests a train arriving by 8:10.
- New `day_trains` attributes: `egress_walk_min`, `arrive_deadline`, `leave_by`, `spare_min`, `suggest_reason`.
- Events later today or tomorrow are planned against that day's timetable. All-day events are ignored. New option: event look-ahead hours.
- New read-only trip planner: websocket `septa_live/plan` and service `septa_live.plan_trips` (returns a response) list trains from any station to any station (default: home) after a time or arriving by a time, including transfers. It never changes a rider's live Going Home origin.
- No behaviour change for existing entities or services.

## 1.13.7

### Added

- Rider train trackers (`device_tracker.septa_<rider>_train` and `my_train`) now include the route the train is running: a simplified map line (`route_shape`), the line colour (`route_color`), and its stops with passed/remaining flags plus the rider's `alight_station`.
- Route lines come from SEPTA's published GTFS feed, which the timetable refresher already downloads. No extra network calls. If a trip has no shape, the line is drawn through its stops.
- The attributes are kept small (under 16 KB) and are left out of the recorder history.
- New websocket command `septa_live/route` returns the full-resolution route for cards that want more detail.
- No behaviour change for existing entities or services.

## 1.13.6

### Fixed

- Service calls now accept numbers wherever a train, station or id is expected. A template like `train: "{{ train }}"` no longer fails with `expected str at 'train'`.
- All service and websocket inputs are trimmed, and blank values are treated as "not set".
- Numeric options sent as text (e.g. `"300"`) are accepted.
- No behaviour change for existing calls.
- Regional Rail station pickers now only list Regional Rail stations, sorted and validated. Metro and trolley stops stay on their own lists. A saved value that is not Regional Rail is left as it is and a repair issue points at the options flow.

### Added

- The rail timetable refreshes itself from SEPTA's published GTFS feed. It is checked daily and updates before the old one expires. The bundled timetable stays as the fallback. `sensor.septa_rail_schedule` shows the valid-through date, and a repair issue appears if the refresh keeps failing while the timetable is expired or about to expire.
- `septa_live.refresh_schedule` forces a timetable refresh.
- Trains list who is riding them (`riders`, with profile pictures) so cards can show a face on each train.
- A per-rider train tracker, `device_tracker.septa_<rider>_train`, puts that rider's current train on the Home Assistant map. It uses the rider's picture, and the line, next stop, and delay. It has no location when the ride ends. People on the same train each get a marker at the same point so the entity id never changes.

## 1.13.5

### Fixed

- My Train stop times include the live delay, and they move when the delay changes. Each stop has `est_source` (`rr`, `delay`, or `sched`). `delay_min` is the delay that was applied.
- The remaining-stop list keeps moving from the train's own position and times when the phone's GPS stalls. You stay marked as riding. `stop_source` says whether the cut came from the train, its position, or the clock.
- The list ends at your stop: the planned destination, the connection, or your home station when the train is still heading there. `alight_station` and `alight_source` say which. `final_destination` is filled in. A home station you have already left does not cut the list.
- A through-running train no longer shows the same stop twice.
- Going Home uses the ride when your coordinates are stale and you are on a train, and the last nearby station when they are stale and you are not. A fallback to the default station still sets `origin_skip_reason`.

## 1.13.4

### Changed

- Going Home and Day Trains are named for every rider, including the first: `sensor.septa_going_home_<rider>` and `sensor.septa_day_trains_<rider>`. Existing entities are renamed when the new id is free, and they keep their history. A hand-renamed entity is left alone. Update dashboards that still use the old ids. Services still accept the old ids for this release.

### Fixed

- Going Home uses the rider's current location again. It reads coordinates from the person or the tracker, whichever is newer and actually has a location, and it follows a tracker change. A zone whose name is a station is used directly. `origin_entity`, `origin_fix_lat`, `origin_fix_lon`, `origin_fix_accuracy`, `origin_fix_age_s`, and `origin_skip_reason` explain a fallback to the default station.

## 1.13.3

### Fixed

- Ride detection no longer changes to another line's train just because the tracks run together. The train you boarded stays until a real transfer, or until the ride ends the way it already did.
- Boarding prefers the train scheduled to leave the nearest stop around that time.
- Corridor heading follows the track in either direction. A train going the other way is still rejected. An estimated position uses the train's direction of travel, not the order of stops in the map file.
- A phone speed over 90 mph is ignored. It does not count as a fast fix, it does not set a course, and it does not start or change a ride.
- TrainView rows that are not Regional Rail train numbers are dropped.
- Service alerts follow the station and line you configured. A line name is no longer built into the filter.

### Added

- `switch_blocked_reason`, `boarding_match`, `heading_source`, `riding_train_missing_polls`, `riding_train_seen`, and `phone_speed_raw_mph`. The train you are on stays in `candidates` even when it is missing from a poll.

## 1.13.2

### Fixed

- A tracker update is no longer dropped just because `last_updated` did not move. The same timestamp is used when the location, speed, or accuracy changed. An identical sample is still `duplicate_ts`.
- A real ride on a train whose TrainView dot is sitting on the last station can match. After two fixes at about 20 mph, a fresh TrainView, and a heading that agrees, the nearest estimated train within 1500 m is accepted. A train facing the wrong way, such as 100° off, is still rejected.
- Each candidate now includes `last_reject_reason` and `stale_reason`. The rider includes `accepted_fix_count`, `skipped_fix_count`, and `last_fix_ts`.

### Changed

- Riding and My Train are named for the rider, including the first one: `binary_sensor.septa_riding_<rider>` and `sensor.septa_my_train_<rider>`. The unique id stays the same, so history is kept. On startup the old `binary_sensor.septa_<station>_riding` and `sensor.septa_<station>_my_train` ids are renamed when you have not renamed them yourself and the new id is free. Update automations or dashboards that still use the station name if the automatic rename did not run.
- Riding sensors show `integration_version`.

## 1.13.1

### Fixed

- Day trains, Going Home, trip, and riding sensors no longer store the long train lists in the recorder. Dashboards still see `trains`, `trips`, `suggested`, and `candidates` on the live state.
- The calendar field on the shared dynamic-trips step is the default for every rider. A rider can still set a different calendar.
- A campus address or ZIP matches a station without the optional geocoder. University City and 19104 resolve to Penn Medicine. 19122 resolves to Temple University. A line that does not serve Penn Medicine transfers at a shared station such as 30th Street.

### Changed

- `max_trains` (default 60) caps the live `trains` list. `trains_total` is the count before that cap. Suggested trains are chosen from the full list. Row field names are unchanged, including nulls.

## 1.13.0

### Added

- Going Home and day-train sensors for each rider. The primary rider has no suffix. Other riders use their slug.
- Origin resolution: a station you set, the nearest timetable station, the usual city station, then the last origin that worked.
- Destination resolution: a station you set, an input helper, a calendar location, then the default. Geocoding is off unless you opt in.
- One-transfer itineraries through a station both lines serve, with `at_risk` when the wait is shorter than `transfer_min`.
- Services `septa_live.set_origin_station` and `septa_live.set_destination`.
- When the bundled timetable is past `validUntil`, a once-a-day refresh from SEPTA's public rail GTFS. If that fails, day trains use live NextToArrive only.

### Changed

- Configured trips can number 20, up from 8. Each trip can list up to 20 departures. The default is still 4.
- NextToArrive calls are shared across trips and riders for the same station pair.

### Migration

- Existing entries keep their trips and entity ids.
- The current station becomes `home_station`. The current destination becomes `default_city_station`.
