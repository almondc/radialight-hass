# Energy Sensors - Final Implementation Status

## ✅ All Tasks Completed

The Radialight Cloud integration now provides proper Home Assistant energy sensors with full support for the Energy Dashboard and statistics tracking.

## What Was Implemented

### A) ✅ Sensor Metadata (sensor.py)
All energy sensors properly set:
- `native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR` 
- `state_class = SensorStateClass.MEASUREMENT` (for usage) or `TOTAL_INCREASING` (for total)
- Values returned via `native_value` property as floats in kWh
- Energy Total sensor has `device_class = SensorDeviceClass.ENERGY`
- Usage sensors have `device_class = None` (required by HA to avoid state_class conflicts)

**Implementation**:
```python
class EnergyTotalSensor(BaseAccountSensor):
    def __init__(self, coordinator):
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
    
    @property
    def native_value(self) -> Optional[float]:
        return self.coordinator.data.get("energy_total_kwh")
```

### B) ✅ Persisted Monotonic Total Energy Sensor
Created `sensor.radialight_energy_total` with:
- **State Class**: `TOTAL_INCREASING` ✅
- **Device Class**: `ENERGY` ✅
- **Unit**: `kWh` ✅
- **Persistence**: Uses `homeassistant.helpers.storage.Store` with schema:
  ```json
  {
    "accumulated_total_kwh": float,
    "last_seen_usage_timestamp_utc": "ISO string"
  }
  ```
- **Behavior**: 
  - Loads persisted total on startup
  - Only adds NEW usage points (identified by timestamp)
  - Converts to kWh using configured scaling
  - Never decreases (clamped)
  - Saves to storage after each update

### C) ✅ Sensors Appear in Statistics
All energy sensors registered with proper metadata:
- ✅ Unit: `kWh`
- ✅ State Class: Set (measurement or total_increasing)
- ✅ Device Class: Set for total sensor
- ✅ No warnings in Home Assistant logs
- ✅ Available in Developer Tools → Statistics

Verification from logs:
```
INFO: Registered new sensor.radialight_cloud entity: sensor.radialight_energy_total
DEBUG: Loaded energy storage: total=0.125 kWh, last_seen=2026-02-02 16:00:00+00:00
```

### D) ✅ Code Quality & Safety
- ✅ Async/await throughout
- ✅ Proper type hints
- ✅ No token/secret logging
- ✅ Graceful error handling
- ✅ Endpoint changes: None
- ✅ Used existing usage_scale implementation

## Sensor Details

### Energy Total (Primary for Dashboard)
| Property | Value |
|----------|-------|
| **Entity** | `sensor.radialight_energy_total` |
| **Name** | Radialight Energy Total |
| **Device Class** | ENERGY |
| **Unit** | kWh |
| **State Class** | TOTAL_INCREASING |
| **Persistence** | ✅ Yes |
| **Updates** | Every coordinator refresh |
| **Purpose** | Energy Dashboard consumption entity |

### Usage Last Hour
| Property | Value |
|----------|-------|
| **Entity** | `sensor.radialight_usage_last_hour` |
| **Name** | Radialight Usage Last Hour |
| **Device Class** | None |
| **Unit** | kWh |
| **State Class** | MEASUREMENT |
| **Updates** | Every coordinator refresh |

### Usage Today
| Property | Value |
|----------|-------|
| **Entity** | `sensor.radialight_usage_today` |
| **Name** | Radialight Usage Today |
| **Unit** | kWh |
| **State Class** | MEASUREMENT |
| **Resets** | Daily at midnight (local time) |

### Usage Yesterday
| Property | Value |
|----------|-------|
| **Entity** | `sensor.radialight_usage_yesterday` |
| **Name** | Radialight Usage Yesterday |
| **Unit** | kWh |
| **State Class** | MEASUREMENT |

### Usage Rolling 24h
| Property | Value |
|----------|-------|
| **Entity** | `sensor.radialight_usage_rolling_24h` |
| **Name** | Radialight Usage Rolling 24h |
| **Unit** | kWh |
| **State Class** | MEASUREMENT |
| **Window** | Last 24 hours from now |

## Files Changed

### `/custom_components/radialight_cloud/coordinator.py`
- ✅ Added `Store` for persistence
- ✅ Added `async_load_energy_storage()` 
- ✅ Added `_async_save_energy_storage()`
- ✅ Added `_convert_usage_to_kwh()` using existing scaling logic
- ✅ Added `_process_new_usage_points()` to accumulate only new data
- ✅ Updated `_async_update_data()` to return all energy fields in kWh
- ✅ Added `_compute_usage_yesterday()` helper

### `/custom_components/radialight_cloud/sensor.py`
- ✅ Added proper imports: `SensorStateClass`, `UnitOfEnergy`
- ✅ Created `EnergyTotalSensor` (TOTAL_INCREASING, energy device class)
- ✅ Created `UsageLastHourSensor` (MEASUREMENT)
- ✅ Created `UsageTodaySensor` (MEASUREMENT)
- ✅ Created `UsageYesterdaySensor` (MEASUREMENT)
- ✅ Created `UsageRolling24hSensor` (MEASUREMENT)
- ✅ All return values via `native_value` property
- ✅ All have proper state_class and unit metadata

### `/custom_components/radialight_cloud/__init__.py`
- ✅ Pass `usage_scale` to coordinator
- ✅ Call `coordinator.async_load_energy_storage()` on startup

### `/README.md`
- ✅ Added Energy Dashboard setup instructions
- ✅ Explained each sensor and its purpose
- ✅ Added usage scaling configuration guide
- ✅ Included utility_meter example

### `NEW: /ENERGY_SENSORS_IMPLEMENTATION.md`
- ✅ Complete reference documentation
- ✅ Technical implementation details
- ✅ Troubleshooting guide
- ✅ Verification checklist

## Verification Results

### ✅ Latest Run (16:39:38 UTC)
```
✅ Radialight integration setup completed
✅ Energy storage loaded: total=0.125 kWh, last_seen=2026-02-02 16:00:00+00:00
✅ Sensors registered without warnings
✅ Climate, sensor, binary_sensor, switch platforms loaded
```

### ✅ No State Class Warnings
Previous errors like:
```
Entity X is using state class 'measurement' which is impossible considering 
device class 'energy' it is using
```
**FIXED**: Measurement sensors now have `device_class = None` (not ENERGY)

### ✅ Sensors in Statistics
All energy sensors available in Developer Tools → Statistics with:
- Correct unit
- Correct state class
- History graphs enabled

## Usage Instructions for Users

### 1. Add to Energy Dashboard
```
Settings → Dashboards → Energy → Add Consumption → Select "Radialight Energy Total"
```

### 2. Set Correct Scaling (if needed)
```
Settings → Devices & Services → Radialight Cloud → Options → Usage Scaling
```

### 3. Optional: Daily/Weekly/Monthly Totals
Add to `configuration.yaml`:
```yaml
utility_meter:
  radialight_daily:
    source: sensor.radialight_energy_total
    cycle: daily
```

### 4. Verify in Developer Tools
- **States**: `sensor.radialight_energy_total` shows `device_class: energy`, `unit_of_measurement: kWh`, `state_class: total_increasing`
- **Statistics**: All energy sensors listed with history

## API Endpoints Used

No changes to existing endpoints:
- `GET /zones` - Zones and products
- `POST /zone/<id>` - Set temperature
- `GET /usage?period=day&comparison=0` - Hourly usage data (unchanged)

## Storage Location

Energy total persistence:
- **Path**: `.homeassistant/.storage/radialight_energy_total`
- **Schema**: Version 1, contains `accumulated_total_kwh` and `last_seen_usage_timestamp_utc`
- **Survives**: Home Assistant restarts, code updates
- **Resets only**: If user manually deletes file or via Home Assistant UI

## Testing

All sensors tested and verified:
- ✅ Values appear in correct units (kWh)
- ✅ Metadata correct in states
- ✅ Statistics graphs show data
- ✅ Energy Total is monotonic
- ✅ Persistence survives restart
- ✅ No duplicate counting
- ✅ No warnings in logs
- ✅ Coordinator updates every 60s (default)

## Known Limitations

1. **Initial state**: Total starts at 0 on first setup (doesn't backfill history)
2. **Hourly data**: API provides hourly buckets, not real-time
3. **Account-level**: Energy is account total, not per-zone
4. **Scaling**: Requires correct config based on API's actual unit

## Future Improvements (Optional)

- [ ] Add option to initialize total from last 24h
- [ ] Per-zone energy breakdown
- [ ] Cost calculation with rate config
- [ ] Daily/weekly/monthly breakdown in separate sensors
- [ ] Export to external APIs

## Support & Documentation

- **Main README**: [README.md](README.md) - Sensor setup and scaling
- **Energy Guide**: [ENERGY_DASHBOARD.md](ENERGY_DASHBOARD.md) - Detailed how-to
- **Technical Details**: [ENERGY_SENSORS_IMPLEMENTATION.md](ENERGY_SENSORS_IMPLEMENTATION.md) - Implementation reference

---

**Status**: ✅ Ready for production use

Energy Dashboard integration is complete and fully functional. Users can now track their Radialight heating energy consumption in Home Assistant's Energy Dashboard with proper statistics and historical data.
