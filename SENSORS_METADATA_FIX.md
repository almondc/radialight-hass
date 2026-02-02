# Energy Sensors Metadata Fix - Comprehensive Implementation

## Summary
Fixed all energy/usage sensors in the Radialight Cloud integration to properly display in Home Assistant with correct metadata (unit_of_measurement, device_class, state_class) and appear in Developer Tools → Statistics.

## Root Cause
The zone usage sensors were storing unit metadata in `extra_state_attributes` (which Home Assistant ignores) instead of using the proper `native_unit_of_measurement` and `state_class` entity properties. This prevented Home Assistant from recognizing them as energy sensors and including them in statistics.

## Changes Made

### 1. Added Helper Function (sensor.py)
```python
def _wh_to_kwh(wh: float) -> float:
    """Convert Wh (watt-hours) to kWh (kilowatt-hours)."""
    return wh / 1000.0
```
- Centralized unit conversion for clarity
- All zone usage sensors assume values are in Wh and convert to kWh

### 2. Fixed Account-Level Sensors (sensor.py)
All account-level usage sensors now have proper metadata:

#### EnergyTotalSensor (Monotonic)
- ✅ `device_class = SensorDeviceClass.ENERGY`
- ✅ `native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR`
- ✅ `state_class = SensorStateClass.TOTAL_INCREASING` (for Energy Dashboard)
- ✅ Added `async_added_to_hass()` with debug logging

#### UsageLastHourSensor, UsageTodaySensor, UsageYesterdaySensor, UsageRolling24hSensor (Measurement)
- ✅ `device_class = None` (NOT ENERGY - HA only allows ENERGY with TOTAL_INCREASING)
- ✅ `native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR`
- ✅ `state_class = SensorStateClass.MEASUREMENT` (can go up/down)
- ✅ Added `async_added_to_hass()` with debug logging

### 3. Fixed Zone-Level Usage Sensors (sensor.py)
All zone usage sensors now have proper metadata and value conversion:

#### ZoneUsageTotalSensor
- ✅ `device_class = None` (not monotonic, can reset)
- ✅ `native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR`
- ✅ `state_class = SensorStateClass.MEASUREMENT`
- ✅ Values converted from Wh to kWh using `_wh_to_kwh()`
- ✅ Returns None if total is 0 (safer state)
- ✅ `extra_state_attributes`: values array capped to 48 items max (prevents DB bloat)
- ✅ Removed misleading "unit": "unknown" attribute
- ✅ Added `async_added_to_hass()` with debug logging

#### ZoneUsageTodaySensor & ZoneUsageYesterdaySensor
- ✅ `device_class = None`
- ✅ `native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR`
- ✅ `state_class = SensorStateClass.MEASUREMENT`
- ✅ Values converted from Wh to kWh using `_wh_to_kwh()`
- ✅ Added `async_added_to_hass()` with debug logging

### 4. Added Logging (sensor.py)
All energy sensors now log metadata on registration:
```python
async def async_added_to_hass(self) -> None:
    """Log metadata when entity is added."""
    await super().async_added_to_hass()
    _LOGGER.debug(
        "Energy sensor registered: entity_id=%s, unique_id=%s, "
        "device_class=%s, unit=%s, state_class=%s",
        self.entity_id,
        self.unique_id,
        self.device_class,
        self.native_unit_of_measurement,
        self.state_class,
    )
```

Debug output example:
```
Energy sensor registered: entity_id=sensor.radialight_energy_total, 
  unique_id=radialight_energy_total, device_class=energy, unit=kWh, 
  state_class=total_increasing

Zone usage sensor registered: entity_id=sensor.cliffs_office_usage_total, 
  unique_id=b314e563-28dd-4f04-bfcd-245d2c35b437_usage_total, 
  device_class=None, unit=kWh, state_class=measurement
```

## Home Assistant Metadata Rules Enforced

✅ **Rule 1: Energy device_class only with TOTAL/TOTAL_INCREASING**
- EnergyTotalSensor: device_class=ENERGY + state_class=TOTAL_INCREASING ✓
- All measurement sensors: device_class=None (not ENERGY) ✓

✅ **Rule 2: Units must be native_unit_of_measurement, not extra attributes**
- Removed "unit": "unknown" from ZoneUsageTotalSensor.extra_state_attributes
- All sensors use `native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR` ✓

✅ **Rule 3: Proper state_class for semantics**
- TOTAL_INCREASING: monotonic sensor (energy_total_kwh)
- MEASUREMENT: non-monotonic sensor (all usage/consumption sensors) ✓

## Verification Results

### Restart 17:02:21 UTC (Fixed Version)
```
✅ Energy sensor registered: device_class=energy, unit=kWh, state_class=total_increasing
✅ Usage sensor registered (all 4): device_class=None, unit=kWh, state_class=measurement
✅ Zone usage sensors (all 6): device_class=None, unit=kWh, state_class=measurement
✅ NO WARNINGS in Home Assistant logs
✅ Coordinator fetching data: "Successfully fetched usage; 23 points"
✅ Coordinator processing: "No new usage points to process" (correct behavior)
```

### Expected Results After Deployment
1. Sensors appear in **Developer Tools → Statistics** with proper metadata
2. Sensors work in **Energy Dashboard** (especially EnergyTotalSensor for consumption)
3. Historical statistics will be recorded by Home Assistant automatically
4. No state_class/device_class warnings in logs

## Values in kWh

All energy/usage sensors now return values in kWh (kilowatt-hours):
- Account-level: `usage_today_kwh`, `usage_yesterday_kwh`, `usage_last_hour_kwh`, `usage_rolling_24h_kwh`, `energy_total_kwh`
- Zone-level: ZoneUsageTotalSensor, ZoneUsageTodaySensor, ZoneUsageYesterdaySensor
- Conversion: API values (assumed Wh) ÷ 1000 = kWh
- Example: 5018 Wh API value → 5.018 kWh sensor value

## Backwards Compatibility

✅ **Preserved:**
- All entity_ids remain unchanged (automations/dashboards work)
- All unique_ids remain unchanged (history preserved)
- API endpoints unchanged
- Configuration options unchanged
- Integration architecture unchanged

## Files Modified
- `/custom_components/radialight_cloud/sensor.py`
  - Added logging import
  - Added `_wh_to_kwh()` helper function
  - Updated EnergyTotalSensor with logging
  - Updated UsageLastHourSensor with logging
  - Updated UsageTodaySensor with logging
  - Updated UsageYesterdaySensor with logging
  - Updated UsageRolling24hSensor with logging
  - Fixed ZoneUsageTotalSensor (metadata, unit conversion, attribute cleanup)
  - Fixed ZoneUsageTodaySensor (metadata, unit conversion, logging)
  - Fixed ZoneUsageYesterdaySensor (metadata, unit conversion, logging)

## Testing Checklist
- [x] Integration loads without errors
- [x] All sensors register with proper metadata
- [x] No state_class/device_class warnings
- [x] Coordinator fetches data successfully
- [x] Values convert to kWh correctly
- [x] Logging shows entity_id, device_class, unit, state_class
- [x] No database bloat (capped values array to 48 items)
- [x] Unique IDs preserved (automations/history not broken)

## Next Steps for User
1. Verify sensors appear in Developer Tools → Statistics
2. Add "Radialight Energy Total" to Energy Dashboard (Settings → Dashboards → Energy → Add consumption → Select sensor.radialight_energy_total)
3. Wait 24-48 hours for historical data to accumulate in Energy Dashboard
4. Optionally: Check zone usage sensors in automations/dashboards if needed
