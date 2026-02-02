# Usage Endpoint Implementation Summary

## Overview
Successfully implemented support for the `/usage` endpoint in the Radialight Cloud integration. This adds hourly usage tracking with three account-level sensors and complete UI/configuration support.

## Files Modified

### 1. **const.py** ✓
- Added `CONF_ENABLE_USAGE_SENSORS = "enable_usage_sensors"`
- Added `DEFAULT_ENABLE_USAGE_SENSORS = True`
- Usage sensors enabled by default, can be disabled via options

### 2. **api.py** ✓
- Added `async_get_usage(period: str = "day", comparison: int = 0)` method
- Reuses existing `_request()` wrapper (inherits auth, 401 retry, backoff)
- Returns parsed JSON from GET `/usage?comparison={comparison}&period={period}`

### 3. **coordinator.py** ✓
- Extended `_async_update_data()` to fetch both `/zones` (required) and `/usage` (graceful fail)
- Added helper functions:
  - `_parse_usage_points()`: Converts ISO8601 UTC timestamps to aware datetime tuples
  - `_compute_usage_today()`: Sums usage for current local date
  - `_compute_usage_rolling(hours)`: Sums last N hours of usage
- Stores in coordinator.data:
  - `usage_points`: List[Tuple[datetime, float]] sorted ascending
  - `usage_last`: Most recent data point
  - `usage_today`: Today's total usage
  - `usage_24h`: Last 24 hours total usage
  - `usage`: Raw API response dict

### 4. **sensor.py** ✓
- Updated imports to include `CONF_ENABLE_USAGE_SENSORS`
- Updated `async_setup_entry()` to:
  - Extract `enable_usage_sensors` from entry data
  - Conditionally create 3 account-level sensors if enabled
- Added `BaseAccountSensor` class (similar to BaseCoordinatorSensor but no device_info)
- Added three usage sensors:
  - `UsageLastHourSensor`: state = usage_last (most recent point)
  - `UsageTodaySensor`: state = usage_today (current day sum)
  - `UsageRolling24hSensor`: state = usage_24h (24-hour rolling sum)
- All sensors include extra_state_attributes:
  - `unit_hint`: "unknown (likely Wh)" (attach as attribute, not device_class)
  - `series_start`: Start timestamp of data series
  - `series_end`: End timestamp of data series
  - `point_count`: Number of hourly data points available
  - `last_48_hours`: Formatted list of last 48 points as dicts with timestamp + usage
- Added helper function `_format_last_n_points(points, n)`:
  - Formats last N points as list of dicts: `[{"timestamp": ISO8601, "usage": float}, ...]`
  - Caps to N items (default 48 for last 48 hours)

### 5. **config_flow.py** ✓
- Updated imports to include `CONF_ENABLE_USAGE_SENSORS` and `DEFAULT_ENABLE_USAGE_SENSORS`
- Updated `RadialightCloudOptionsFlow.async_step_init()`:
  - Extract `enable_usage_sensors` from config entry options
  - Added optional boolean schema field for `CONF_ENABLE_USAGE_SENSORS` (default True)
  - Users can now disable usage sensors via options UI

### 6. **__init__.py** ✓
- Updated imports to include `CONF_ENABLE_USAGE_SENSORS` and `DEFAULT_ENABLE_USAGE_SENSORS`
- Updated `async_setup_entry()`:
  - Extract `enable_usage_sensors` from entry.options
  - Store in `hass.data[DOMAIN][entry.entry_id][CONF_ENABLE_USAGE_SENSORS]`
- Updated `async_update_options()`:
  - Extract `enable_usage_sensors` from updated options
  - Update stored value in hass.data

### 7. **diagnostics.py** ✓
- Updated imports to include `CONF_ENABLE_USAGE_SENSORS`
- Extended `async_get_config_entry_diagnostics()`:
  - Added `enable_usage_sensors` flag to diagnostics
  - Added `usage` snapshot with:
    - `first_timestamp`: First data point (ISO8601)
    - `last_timestamp`: Last data point (ISO8601)
    - `point_count`: Total available data points
    - `sample_last_5_points`: Last 5 points formatted (for debugging without huge arrays)
  - Sanitized to prevent leaking full usage arrays

### 8. **translations/en.json** ✓
- Added UI label: `"enable_usage_sensors": "Enable usage sensors"`
- Appears in options flow under init step

## Data Flow

```
GET /usage?comparison=0&period=day
        ↓
RadialightAPIClient.get_usage()
        ↓
RadialightCoordinator._async_update_data()
        ↓
Parse ISO8601 timestamps → aware datetime objects (UTC)
Sort ascending, compute rolling stats
        ↓
coordinator.data = {
    "usage_points": [(datetime_utc, float_usage), ...],
    "usage_last": float,
    "usage_today": float,
    "usage_24h": float,
    "usage": {...},  # raw API response
    ...
}
        ↓
UsageLastHourSensor / UsageTodaySensor / UsageRolling24hSensor
        ↓
Expose state + attributes (with last 48 points)
```

## Entity UUIDs

All usage sensors are account-level (no zone_id, no product_id):
- `sensor.radialight_usage_last_hour` (unique_id: "radialight_usage_last_hour")
- `sensor.radialight_usage_today` (unique_id: "radialight_usage_today")
- `sensor.radialight_usage_24h` (unique_id: "radialight_usage_24h")

## Attributes

Example attributes for usage sensors:
```json
{
  "unit_hint": "unknown (likely Wh)",
  "series_start": "2024-01-15T00:00:00+00:00",
  "series_end": "2024-01-15T23:00:00+00:00",
  "point_count": 24,
  "last_48_hours": [
    {"timestamp": "2024-01-14T22:00:00+00:00", "usage": 0.5},
    {"timestamp": "2024-01-14T23:00:00+00:00", "usage": 0.3},
    {"timestamp": "2024-01-15T00:00:00+00:00", "usage": 0.2},
    ...
  ]
}
```

## Configuration

### Setup (No changes needed)
Same Firebase API Key and Refresh Token required.

### Options (New)
- **Polling Interval** (seconds): 10-3600, default 60
- **Enable per-product entities** (boolean): default false
- **Enable usage sensors** (boolean): default true ← NEW

## Backward Compatibility

✓ **Fully backward compatible**
- Existing zones/climate entities unaffected
- Existing zone sensors unchanged
- Usage sensors opt-in (enabled by default but can be disabled)
- If `/usage` endpoint fails, zones still update (graceful degradation)
- Coordinator data structure extended (not breaking)

## Error Handling

1. **Zone fetch fails**: Coordinator retries with exponential backoff, entities become unavailable
2. **Usage fetch fails**: Logged at rate-limited intervals, coordinator continues with previous usage_points, sensors show stale data until next success
3. **Parse error in usage**: Logged, coordinator.data gets empty usage_points, sensors show None/0

## Testing Recommendations

1. **Setup**: Add integration with valid credentials
2. **Options**: Toggle "Enable usage sensors" and verify entity creation/removal
3. **Polling**: Check that usage sensors update on coordinator refresh cycle
4. **Attributes**: Inspect last_48_hours in Developer Tools → States
5. **Diagnostics**: Call config entry diagnostics to verify usage snapshot
6. **Degradation**: Stop API server, verify zones still work while usage shows stale
7. **HA Restart**: Verify entities recreated with correct state

## Version
- Integration version: 0.2.0
- Supports: Home Assistant Core 2023.12+
- Requires: aiohttp>=3.8.0

## Notes

- Unit for usage is likely Wh (watt-hours) but not confirmed in API docs, so `unit_hint` attribute is used instead of `device_class`
- `last_48_hours` attribute caps to 48 points by design (prevents very large state objects)
- ISO8601 timestamps in attributes are UTC (Z suffix) for consistency with Home Assistant datetime strings
- No product-level usage sensors (endpoint returns account-level data only)
