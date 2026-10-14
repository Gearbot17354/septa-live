# Changelog

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
