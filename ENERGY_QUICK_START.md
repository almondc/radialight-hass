# Quick Start: Energy Dashboard

## In 3 Steps

### 1. Open Home Assistant Energy Dashboard
Settings → Dashboards → Energy

### 2. Add Consumption
Click "Add Consumption" button

### 3. Select Sensor
Choose **"Radialight Energy Total"** (sensor.radialight_energy_total)

That's it! 🎉

## What You'll See

- **Energy Today**: Updated hourly
- **Energy This Month**: Cumulative total
- **Energy Graph**: Historical trends (after 2+ hours of data)

## Sensor Entities Available

| Entity | Purpose | Updates |
|--------|---------|---------|
| `sensor.radialight_energy_total` | **Main dashboard entity** | Hourly |
| `sensor.radialight_usage_today` | Today's total | Hourly |
| `sensor.radialight_usage_yesterday` | Yesterday's total | When available |
| `sensor.radialight_usage_last_hour` | Most recent hour | Hourly |
| `sensor.radialight_usage_rolling_24h` | Last 24 hours | Hourly |

## Verify It Works

Developer Tools → States

Find `sensor.radialight_energy_total` and verify:
- ✅ `unit_of_measurement`: kWh
- ✅ `device_class`: energy
- ✅ `state_class`: total_increasing
- ✅ `state`: numeric value (e.g., 2.345)

## If Values Seem Wrong

Settings → Devices & Services → Radialight Cloud → Options

Try different "Usage Scaling":
- **deciwh** (default): Use if values are too small
- **wh**: Use if values are 1000x too large
- **raw**: Shows raw API values (for debugging)

## Daily/Weekly/Monthly Totals (Optional)

Add to your `configuration.yaml`:

```yaml
utility_meter:
  radialight_daily:
    source: sensor.radialight_energy_total
    cycle: daily
  radialight_weekly:
    source: sensor.radialight_energy_total
    cycle: weekly
```

This creates:
- `sensor.radialight_daily` (resets each day)
- `sensor.radialight_weekly` (resets each week)

## Troubleshooting

### Sensor shows 0 kWh
- Normal on first run (no history yet)
- Wait 24 hours for more meaningful data
- Check sensor attributes for last_seen_usage_timestamp

### Energy dashboard shows "No data"
- Wait at least 2 hours after setup
- Restart Home Assistant
- Check Developer Tools → Statistics for the entity

### Values look wrong
- Check Settings → Options → Usage Scaling
- Compare with your Radialight mobile app
- Try different scaling option

### Sensor missing
- Ensure "Enable usage sensors" is ON in integration Options
- Restart Home Assistant
- Check Home Assistant logs for errors

## Advanced: Automation Example

Show daily energy usage in a notification:

```yaml
automation:
  - alias: "Daily Energy Report"
    trigger:
      platform: time
      at: "23:59:00"
    action:
      service: notify.notify
      data:
        message: >
          Energy used today: {{ state_attr('sensor.radialight_usage_today', 'state') | float(0) | round(2) }} kWh
```

## More Information

- Full setup guide: See [README.md](README.md) Energy Sensors section
- Technical details: See [ENERGY_SENSORS_IMPLEMENTATION.md](ENERGY_SENSORS_IMPLEMENTATION.md)
- Scaling options: See [README.md](README.md) Usage Scaling section

---

**Need help?** Check the README.md or ENERGY_SENSORS_IMPLEMENTATION.md for detailed documentation.
