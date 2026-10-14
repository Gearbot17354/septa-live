# Changelog

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
