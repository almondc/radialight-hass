# Energy Dashboard Integration

This document explains how the Radialight Cloud integration implements proper Home Assistant Energy Dashboard support.

## Overview

The integration now provides a **monotonically increasing total energy sensor** (`sensor.radialight_energy_total`) that persists across restarts and is suitable for the Home Assistant Energy Dashboard.

## Energy Sensors

### 1. Energy Total (TOTAL_INCREASING) ⭐
**Entity**: `sensor.radialight_energy_total`

- **State Class**: `TOTAL_INCREASING` (monotonically increasing)
- **Device Class**: `ENERGY`
- **Unit**: `kWh`
- **Purpose**: Primary sensor for Energy Dashboard
- **Persistence**: Stored in `.storage/radialight_energy_total`
- **Behavior**: Never decreases, accumulates new energy usage

**How it works:**
1. On first run, initializes tracking from the most recent timestamp
2. On each update, identifies new usage data points since last seen
3. Converts raw API values to kWh using configured scaling
4. Adds only NEW points to the accumulated total
5. Persists total and last_seen_timestamp to storage
6. Survives Home Assistant restarts

### 2. Usage Measurement Sensors
These sensors use `state_class: measurement` and may fluctuate or reset:

- **`sensor.radialight_usage_last_hour`**: Most recent hourly usage (kWh)
- **`sensor.radialight_usage_today`**: Total usage since midnight local time (kWh)
- **`sensor.radialight_usage_yesterday`**: Total usage for yesterday (kWh)
- **`sensor.radialight_usage_rolling_24h`**: Total usage over last 24 hours (kWh)

## Usage Scaling

The integration supports three scaling modes (configured in Options):

### deciwh (default)
- **Assumption**: API values are 0.1 Wh (deci-Wh)
- **Conversion**: `(raw_value × 10) ÷ 1000 = kWh`
- **Example**: API value 250 → 2.5 kWh

### wh
- **Assumption**: API values are Wh
- **Conversion**: `raw_value ÷ 1000 = kWh`
- **Example**: API value 250 → 0.25 kWh

### raw (debugging)
- **Assumption**: Display as-is
- **Conversion**: None
- **Purpose**: Troubleshooting and determining actual API units

## Adding to Energy Dashboard

### Step 1: Navigate to Energy Dashboard
1. Go to **Settings** → **Dashboards** → **Energy**
2. Click **Add Consumption**

### Step 2: Select Energy Total Sensor
1. Select `sensor.radialight_energy_total`
2. Click **Save**

### Step 3: Wait for Data
The Energy Dashboard requires:
- At least 2 hours of data for hourly view
- At least 2 days of data for daily view
- Statistics are built from the sensor's state_class and values

## Optional: Utility Meter for Daily/Weekly/Monthly Totals

You can create daily, weekly, and monthly reset meters using Home Assistant's built-in `utility_meter` integration.

Add this to your `configuration.yaml`:

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

After adding, restart Home Assistant. This creates:
- `sensor.radialight_daily`: Resets at midnight
- `sensor.radialight_weekly`: Resets weekly
- `sensor.radialight_monthly`: Resets monthly

## Technical Details

### Storage Format
`.storage/radialight_energy_total`:
```json
{
  "accumulated_total_kwh": 123.456,
  "last_seen_usage_timestamp_utc": "2026-02-02T15:00:00+00:00"
}
```

### Update Cycle
1. Coordinator fetches usage points from API (hourly data)
2. Identifies points with timestamp > last_seen_usage_timestamp
3. Converts each new point to kWh using usage_scale
4. Adds to accumulated_total_kwh
5. Updates last_seen_usage_timestamp to newest point
6. Saves to storage
7. Updates sensor state

### Safety Features
- **Never decreases**: Total is clamped if calculation would reduce it
- **Graceful degradation**: If usage fetch fails, total is not updated
- **Restart resilience**: Storage persists across reboots
- **Duplicate prevention**: Only processes new timestamps

### Long-Term Statistics
Home Assistant automatically creates long-term statistics for sensors with:
- `state_class = TOTAL_INCREASING`
- `device_class = ENERGY`
- `native_unit_of_measurement = kWh`

These statistics enable:
- Historical graphs
- Energy Dashboard integration
- Trend analysis
- Export for external analysis

## Troubleshooting

### Energy Total Not Increasing
1. Check coordinator is fetching new data: Look for "Successfully fetched usage" in logs
2. Verify timestamps: `last_seen_usage_timestamp` attribute should update
3. Check usage_scale: Ensure it matches your API's units
4. Review logs for "Processed X new usage points"

### Energy Dashboard Shows "No data"
1. Wait at least 2 hours after setup
2. Check Statistics: Developer Tools → Statistics
3. Verify sensor has `state_class: total_increasing`
4. Check for errors in Home Assistant logs

### Values Seem Wrong
1. Try different usage_scale settings
2. Compare with app values
3. Check diagnostics for raw values
4. Enable debug logging: `custom_components.radialight_cloud: debug`

### Storage Not Persisting
1. Check `.storage/radialight_energy_total` file exists
2. Verify Home Assistant has write permissions
3. Check logs for "Failed to save energy storage"

## Debug Logging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.radialight_cloud: debug
```

Look for:
- "Initializing energy tracking"
- "Processed X new usage points, added Y kWh"
- "Loaded energy storage: total=X kWh"

## API Data Points

The integration fetches hourly usage data from:
```
GET /usage?period=day&comparison=0
```

Response includes hourly timestamps and usage values. The integration:
1. Parses timestamps as UTC datetime objects
2. Tracks which timestamps have been processed
3. Only adds new timestamps to the total
4. Handles gaps and missing data gracefully
