# ✅ Energy Sensors Implementation - Verification Summary

## Status: COMPLETE ✅

All Radialight energy sensors are now properly recognized by Home Assistant with correct metadata for statistics and Energy Dashboard integration.

## Sensors Implemented

### 1. **Radialight Energy Total** (Main Energy Dashboard Entity)
- **Entity ID**: `sensor.radialight_energy_total`
- **Device Class**: `ENERGY` ✅
- **Unit**: `kWh` ✅
- **State Class**: `TOTAL_INCREASING` ✅
- **Values**: Floats in kWh
- **Persistence**: Stored in `.storage/radialight_energy_total`
- **Purpose**: Primary sensor for Home Assistant Energy Dashboard
- **Behavior**: 
  - Monotonically increasing (never decreases)
  - Accumulates new usage points from API
  - Survives Home Assistant restarts

### 2. **Radialight Usage Last Hour**
- **Entity ID**: `sensor.radialight_usage_last_hour`
- **Device Class**: None (measurement sensors don't support energy device class)
- **Unit**: `kWh` ✅
- **State Class**: `MEASUREMENT` ✅
- **Purpose**: Most recent hourly usage value
- **Behavior**: Updates with each API call

### 3. **Radialight Usage Today**
- **Entity ID**: `sensor.radialight_usage_today`
- **Device Class**: None
- **Unit**: `kWh` ✅
- **State Class**: `MEASUREMENT` ✅
- **Purpose**: Total usage since midnight (local time)
- **Behavior**: Resets daily

### 4. **Radialight Usage Yesterday**
- **Entity ID**: `sensor.radialight_usage_yesterday`
- **Device Class**: None
- **Unit**: `kWh` ✅
- **State Class**: `MEASUREMENT` ✅
- **Purpose**: Total usage for previous calendar day
- **Behavior**: Updates when new day data available

### 5. **Radialight Usage Rolling 24h**
- **Entity ID**: `sensor.radialight_usage_rolling_24h`
- **Device Class**: None
- **Unit**: `kWh` ✅
- **State Class**: `MEASUREMENT` ✅
- **Purpose**: Total usage over last 24 hours
- **Behavior**: Updates continuously

## Implementation Details

### Sensor Metadata
All sensors properly set:
```python
_attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
_attr_state_class = SensorStateClass.MEASUREMENT  # or TOTAL_INCREASING
```

Values returned via `native_value` property (not as plain state):
```python
@property
def native_value(self) -> Optional[float]:
    return self.coordinator.data.get("energy_total_kwh")
```

### Value Conversion
All raw API values are converted to kWh using the configured scaling:
- **deciwh** (default): `(raw × 10) ÷ 1000 = kWh`
- **wh**: `raw ÷ 1000 = kWh`
- **raw**: No conversion (for debugging)

Conversion happens in coordinator:
```python
def _convert_usage_to_kwh(self, raw_value: float) -> float:
    if self.usage_scale == USAGE_SCALE_DECIWH:
        return (raw_value * 10.0) / 1000.0
    # ... other cases
```

### Persistence (Energy Total)
The monotonic total energy sensor persists state across restarts:

**Storage File**: `.storage/radialight_energy_total`
```json
{
  "version": 1,
  "minor_version": 1,
  "key": "radialight_energy_total",
  "data": {
    "accumulated_total_kwh": 0.125,
    "last_seen_usage_timestamp_utc": "2026-02-02T16:00:00+00:00"
  }
}
```

### Data Flow
```
API /usage endpoint (hourly buckets)
     ↓
Parse timestamps + raw usage values
     ↓
Identify new points (timestamp > last_seen_timestamp)
     ↓
Convert each new point to kWh
     ↓
Add to accumulated_total_kwh
     ↓
Update last_seen_timestamp
     ↓
Persist to storage
     ↓
Update coordinator.data
     ↓
Sensors read from coordinator.data
```

## Verification Checklist

### ✅ Sensors Registered
```
INFO: Registered new sensor.radialight_cloud entity: sensor.radialight_energy_total
INFO: Registered new sensor.radialight_cloud entity: sensor.radialight_usage_last_hour
INFO: Registered new sensor.radialight_cloud entity: sensor.radialight_usage_today
INFO: Registered new sensor.radialight_cloud entity: sensor.radialight_usage_yesterday
INFO: Registered new sensor.radialight_cloud entity: sensor.radialight_usage_rolling_24h
```

### ✅ No State Class Warnings
Previous warnings about `state_class: measurement` with `device_class: energy` are gone because measurement sensors don't have device_class set.

### ✅ Storage Working
```
DEBUG: Loaded energy storage: total=0.125 kWh, last_seen=2026-02-02 16:00:00+00:00
```

### ✅ Data Available
Coordinator returns all required fields:
- `energy_total_kwh`: Float (kWh)
- `usage_last_hour_kwh`: Float (kWh)
- `usage_today_kwh`: Float (kWh)
- `usage_yesterday_kwh`: Float (kWh)
- `usage_rolling_24h_kwh`: Float (kWh)
- `last_seen_usage_timestamp`: Datetime (UTC)

## Using in Home Assistant

### Energy Dashboard Setup
1. Go to **Settings** → **Dashboards** → **Energy**
2. Click **Add Consumption**
3. Select **sensor.radialight_energy_total**
4. Save

### Statistics & History
All energy sensors appear in:
- Developer Tools → **States**: Shows current value + metadata
- Developer Tools → **Statistics**: Shows history graphs
- Energy Dashboard: Displays consumption data
- Long-term statistics: Automatically created by HA

### Optional: Daily/Weekly/Monthly Totals
Add to `configuration.yaml`:
```yaml
utility_meter:
  radialight_daily:
    source: sensor.radialight_energy_total
    cycle: daily
  radialight_weekly:
    source: sensor.radialight_energy_total
    cycle: weekly
  radialight_monthly:
    source: sensor.radialight_energy_total
    cycle: monthly
```

## Troubleshooting

### Sensors Not in Statistics?
1. Verify unit is `kWh` (not empty)
2. Verify state_class is set to `measurement` or `total_increasing`
3. Check Developer Tools → States for the metadata
4. Restart Home Assistant

### Values Seem Wrong?
1. Check coordinator logs: `"Successfully fetched usage; X points"`
2. Verify scaling: Look for usage_scale in sensor attributes
3. Try different scaling mode in Options
4. Check raw values vs. expected

### Storage Not Persisting?
1. Check `.storage/radialight_energy_total` exists
2. Verify Home Assistant has write permissions
3. Check logs for "Failed to save energy storage"
4. Ensure /config is properly mounted in Docker

## Files Modified

1. **coordinator.py**
   - Added storage management
   - Added energy accumulation logic
   - Added value conversion
   - Updated data returned to include all energy fields

2. **sensor.py**
   - Created EnergyTotalSensor with TOTAL_INCREASING
   - Created UsageLastHourSensor with MEASUREMENT
   - Created UsageTodaySensor with MEASUREMENT
   - Created UsageYesterdaySensor with MEASUREMENT
   - Created UsageRolling24hSensor with MEASUREMENT
   - All with proper unit and state_class metadata

3. **__init__.py**
   - Load energy storage on startup
   - Pass usage_scale to coordinator

4. **README.md**
   - Added Energy Dashboard section
   - Added usage sensor descriptions
   - Added configuration instructions

## Technical Notes

### Why No device_class for Measurement Sensors?
Home Assistant requires:
- `device_class = ENERGY` only works with `state_class = TOTAL` or `TOTAL_INCREASING`
- `state_class = MEASUREMENT` cannot have a device_class

Therefore:
- Energy Total: `device_class = ENERGY`, `state_class = TOTAL_INCREASING` ✅
- Usage sensors: `device_class = None`, `state_class = MEASUREMENT` ✅

### Why Persistence?
The Energy Dashboard requires a monotonically increasing entity. Without persistence:
- Total would reset to 0 on HA restart
- Energy Dashboard would show incorrect jumps/drops
- Historical data would be lost

With persistence:
- Total survives restarts
- Energy Dashboard shows continuous history
- Users can rely on accurate cumulative data

### Safety Features
1. **Never decreases**: Total is clamped if it would decrease
2. **No double counting**: Tracks last_seen_timestamp to avoid reprocessing
3. **Graceful failure**: If usage fetch fails, total is not updated
4. **No secrets logged**: Storage contains no credentials

## Next Steps for Users

1. **Wait for data**: At least 2 hours needed for Energy Dashboard to show trends
2. **Add to dashboard**: Use `sensor.radialight_energy_total` as main consumption entity
3. **Set scaling**: Verify correct `usage_scale` in integration Options
4. **Monitor**: Check Developer Tools → Statistics to verify data collection
5. **Optional**: Set up utility_meter for daily/weekly/monthly reports
