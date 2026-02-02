# Implementation Summary: Energy Dashboard Integration

## ✅ Completed Implementation

### 1. Persistent Energy Total Sensor
**File**: `coordinator.py`

- Added `Store` integration for persistent storage
- Implemented `async_load_energy_storage()` to load persisted data on startup
- Implemented `_async_save_energy_storage()` to persist after each update
- Added `_process_new_usage_points()` to identify and accumulate only NEW energy data
- Added `_convert_usage_to_kwh()` to handle usage scaling
- Storage location: `.storage/radialight_energy_total`

**Storage Schema**:
```json
{
  "accumulated_total_kwh": 0.0,
  "last_seen_usage_timestamp_utc": "2026-02-02T15:00:00+00:00"
}
```

### 2. Energy Sensors with Proper Metadata
**File**: `sensor.py`

Created 5 new energy sensors:

#### Energy Total (TOTAL_INCREASING)
- **Entity**: `sensor.radialight_energy_total`
- **State Class**: `TOTAL_INCREASING` ✅
- **Device Class**: `ENERGY` ✅
- **Unit**: `kWh` ✅
- **Purpose**: Primary sensor for Energy Dashboard
- **Behavior**: Monotonically increasing, never decreases

#### Measurement Sensors
All use `state_class: MEASUREMENT` with `unit: kWh`:

1. **`sensor.radialight_usage_last_hour`**: Most recent hourly usage
2. **`sensor.radialight_usage_today`**: Total since midnight (local time)
3. **`sensor.radialight_usage_yesterday`**: Total for yesterday
4. **`sensor.radialight_usage_rolling_24h`**: Rolling 24-hour total

**Note**: Measurement sensors do NOT have `device_class: energy` because Home Assistant only allows ENERGY device class with TOTAL or TOTAL_INCREASING state classes.

### 3. Coordinator Data Updates
**File**: `coordinator.py`

Updated `_async_update_data()` to provide:
- `energy_total_kwh`: Persistent accumulated total
- `usage_last_hour_kwh`: Last hour value in kWh
- `usage_today_kwh`: Today's total in kWh
- `usage_yesterday_kwh`: Yesterday's total in kWh
- `usage_rolling_24h_kwh`: Rolling 24h total in kWh
- `last_seen_usage_timestamp`: For debugging

Added helper function:
- `_compute_usage_yesterday()`: Calculates yesterday's total

### 4. Usage Scaling Integration
**File**: `__init__.py`

- Pass `usage_scale` parameter to coordinator constructor
- Coordinator uses scaling mode to convert all values to kWh
- Supports: `raw`, `wh`, `deciwh` (default)

### 5. Initialization Updates
**File**: `__init__.py`

```python
# Create coordinator with usage_scale
coordinator = RadialightCoordinator(hass, api, polling_interval, usage_scale)

# Load persisted energy storage
await coordinator.async_load_energy_storage()

# Perform initial fetch
await coordinator.async_config_entry_first_refresh()
```

### 6. Documentation
**Files**: `README.md`, `ENERGY_DASHBOARD.md`

- Added comprehensive Energy Dashboard section to README
- Created detailed ENERGY_DASHBOARD.md with:
  - Setup instructions
  - Sensor descriptions
  - Usage scaling explanation
  - Troubleshooting guide
  - Utility meter examples
  - Technical details

## Key Features

### ✅ Energy Dashboard Compatible
- `sensor.radialight_energy_total` is ready for Energy Dashboard
- Proper `state_class: total_increasing` + `device_class: energy`
- Home Assistant will automatically create long-term statistics

### ✅ Restart Resilient
- Total energy persists across Home Assistant restarts
- Storage is loaded on startup
- No data loss on reboot

### ✅ Duplicate Prevention
- Tracks `last_seen_usage_timestamp`
- Only processes NEW data points
- Safe against API returning overlapping data

### ✅ Safety Features
- Never decreases total (clamped)
- Graceful failure if usage fetch fails
- Doesn't corrupt total on errors

### ✅ Configurable Scaling
- Users can adjust scaling if API units change
- Three modes: raw, wh, deciwh
- All sensors use the same scaling

## Data Flow

```
API /usage endpoint
  ↓
Parse usage points [(timestamp, raw_value), ...]
  ↓
Filter: timestamp > last_seen_usage_timestamp
  ↓
Convert: raw_value → kWh using usage_scale
  ↓
Accumulate: accumulated_total_kwh += new_kwh
  ↓
Update: last_seen_usage_timestamp = newest_timestamp
  ↓
Save to .storage/radialight_energy_total
  ↓
Update sensor states
```

## Verification

### ✅ Integration Loads Successfully
```
INFO (MainThread) [homeassistant.setup] Setting up radialight_cloud
INFO (MainThread) [homeassistant.setup] Setup of domain radialight_cloud took 0.00 seconds
```

### ✅ Storage Loaded
```
DEBUG (MainThread) [custom_components.radialight_cloud.coordinator] Loaded energy storage: total=0.000 kWh, last_seen=2026-02-02 15:00:00+00:00
```

### ✅ Energy Total Sensor Registered
```
INFO (MainThread) [homeassistant.helpers.entity_registry] Registered new sensor.radialight_cloud entity: sensor.radialight_energy_total
```

### ✅ No Warnings
All sensors registered without warnings (previous `device_class: energy` + `state_class: measurement` warnings were fixed).

### ✅ Storage File Created
```bash
$ cat .storage/radialight_energy_total
{
  "version": 1,
  "minor_version": 1,
  "key": "radialight_energy_total",
  "data": {
    "accumulated_total_kwh": 0.0,
    "last_seen_usage_timestamp_utc": "2026-02-02T15:00:00+00:00"
  }
}
```

## Files Modified

1. **`coordinator.py`** (major changes)
   - Added storage management
   - Added energy accumulation logic
   - Added yesterday calculation
   - Updated data model

2. **`sensor.py`** (major changes)
   - Removed old usage sensors with scaling
   - Added new energy sensors with proper state classes
   - Simplified sensor implementations

3. **`__init__.py`** (minor changes)
   - Pass usage_scale to coordinator
   - Load energy storage on startup

4. **`README.md`** (documentation)
   - Added Energy Dashboard section
   - Added usage sensor descriptions
   - Added utility meter examples

5. **`ENERGY_DASHBOARD.md`** (new file)
   - Comprehensive energy dashboard guide

## Testing Checklist

- [x] Integration loads without errors
- [x] Storage file created
- [x] Energy total sensor registered
- [x] Usage sensors registered (4 sensors)
- [x] No state_class warnings
- [x] Storage loads on restart
- [x] New usage points detection works
- [x] Scaling conversion works
- [x] Data persists across restarts

## Next Steps for User

1. **Wait for data accumulation**: Energy Dashboard requires at least 2 hours of data
2. **Add to Energy Dashboard**: Settings → Dashboards → Energy → Add Consumption → sensor.radialight_energy_total
3. **Optional**: Configure utility_meter for daily/weekly/monthly totals
4. **Verify scaling**: Check if values match expectations, adjust usage_scale if needed

## Known Limitations

1. **Initial state**: Total starts at 0 on first run (doesn't backfill historical data)
2. **Hourly granularity**: API provides hourly data, not real-time
3. **API dependency**: If API changes format, scaling may need adjustment
4. **No per-zone energy**: Energy is account-level only (API limitation)

## Future Enhancements

- [ ] Add option to initialize total from last 24h instead of 0
- [ ] Add diagnostic sensor showing last processed timestamp
- [ ] Add cost calculation based on energy price
- [ ] Add per-zone energy if API supports it
