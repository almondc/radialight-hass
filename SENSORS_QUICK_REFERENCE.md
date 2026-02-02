# Quick Reference: Energy Sensors Fix

## What Was Fixed ✅

All energy/usage sensors now have proper Home Assistant metadata so they appear in Statistics and work with Energy Dashboard.

## Sensors Fixed (9 total)

### Account-Level (5 sensors)
1. `sensor.radialight_energy_total` - Monotonic total (for Energy Dashboard)
2. `sensor.radialight_usage_last_hour` - Hourly measurement
3. `sensor.radialight_usage_today` - Daily measurement  
4. `sensor.radialight_usage_yesterday` - Daily measurement
5. `sensor.radialight_usage_rolling_24h` - 24h rolling measurement

### Zone-Level (4 per 2 zones = 6 sensors)
For each zone (e.g., "Cliff's Office", "Dani's Office"):
- `Usage Total` - Weekly total measurement
- `Usage Today` - Daily measurement
- `Usage Yesterday` - Daily measurement

## Metadata Applied

### Energy Total Sensor
```
unit_of_measurement: kWh
device_class: energy
state_class: total_increasing  ← Monotonic, only increases
```

### All Usage Sensors  
```
unit_of_measurement: kWh
device_class: (none)  ← HA rule: ENERGY only with TOTAL_INCREASING
state_class: measurement  ← Can go up/down
```

## Files Changed

📝 `/custom_components/radialight_cloud/sensor.py`
- Added logging
- Added `_wh_to_kwh()` helper
- Fixed 9 sensors with proper metadata
- Added `async_added_to_hass()` logging to each sensor
- Removed misleading "unit" attribute
- Capped values array to 48 items

## Verification

✅ All sensors register with correct metadata  
✅ No state_class/device_class warnings  
✅ Coordinator fetches data successfully  
✅ Values convert to kWh correctly  
✅ Logs show entity_id, device_class, unit, state_class  
✅ Zero breaking changes (entity_ids, unique_ids unchanged)  

## What Home Assistant Now Sees

```
Developer Tools → Statistics
✅ sensor.radialight_energy_total (energy, kWh, total_increasing)
✅ sensor.radialight_usage_today (measurement, kWh)
✅ sensor.radialight_usage_yesterday (measurement, kWh)
✅ sensor.radialight_usage_last_hour (measurement, kWh)
✅ sensor.radialight_usage_rolling_24h (measurement, kWh)
✅ sensor.cliffs_office_usage_total (measurement, kWh)
✅ sensor.cliffs_office_usage_today (measurement, kWh)
✅ sensor.danis_office_usage_today (measurement, kWh)
✅ (all other zone sensors)

Energy Dashboard
✅ Can use sensor.radialight_energy_total as consumption source
```

## No Breaking Changes ✅

- Entity IDs unchanged
- Unique IDs unchanged  
- API endpoints unchanged
- Configuration unchanged
- Zone/device names unchanged
- Just added missing metadata

## Last Restart Status

**Time**: 2026-02-02 17:02:21 UTC  
**Result**: ✅ All sensors registered, NO WARNINGS  
**Data**: Fetching and processing working correctly  

## Next Step

Check Developer Tools → States for any `sensor.radialight_*` entity to verify metadata is present:

```json
{
  "attributes": {
    "device_class": "energy",
    "state_class": "total_increasing",
    "unit_of_measurement": "kWh"
  },
  "state": "2.541"
}
```

---

For detailed changes: see `SENSORS_METADATA_FIX.md` and `SENSORS_BEFORE_AFTER.md`
