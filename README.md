# Radialight Cloud Home Assistant Integration

![HACS Supported](https://img.shields.io/badge/HACS-supported-success)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration to control [Radialight ICON radiators](https://www.radialight.it/) via the cloud API.

> **Cloud-based integration:** This integration depends on Radialight's cloud API and requires internet connectivity.

## Features

- **Zone-Based Climate Control**: One climate entity per zone (not per radiator)
- **Cloud API Integration**: Communicates with `https://myradialight-fe-prod.opengate.it`
- **Firebase Authentication**: Secure token refresh flow for API access
- **Configurable Polling**: Adjustable polling interval (default: 60 seconds)
- **Real-Time Monitoring**: Current and target temperature display
- **Product Monitoring**: View connected radiator status and detected temperatures
- **Preset Modes**: program / comfort / eco
- **Energy Monitoring**: kWh sensors for Energy Dashboard integration
- **Diagnostics**: Built-in diagnostics (sanitized)

## Installation

### Option 1: HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance
2. In HACS, click the **⋮** (menu) button in the top right → **Custom repositories**
3. Add this repository:
   - **Repository URL**: `https://github.com/YOUR_GITHUB_USERNAME/radialight-hass`
   - **Category**: Integration
4. Click **Install**
5. Restart Home Assistant

### Option 2: Manual Installation

1. Copy the `radialight_cloud` folder into your Home Assistant `custom_components` directory:
   ```bash
   cp -r custom_components/radialight_cloud ~/.homeassistant/custom_components/
   ```

2. Restart Home Assistant or reload custom integrations.

### Post-Installation Setup

1. Go to **Settings** → **Devices & Services** → **Create Automation** and search for "Radialight Cloud".

## Configuration

### Prerequisites

You need:
- **Firebase API Key** (from Radialight's Firebase project)
- **Refresh Token** (obtained from the Radialight mobile app or web login)

### Setup Steps

1. In Home Assistant, navigate to **Settings** → **Devices & Services**
2. Click **Create Integration** and select **Radialight Cloud**
3. Enter your Firebase API Key and Refresh Token
4. The integration will validate your credentials by fetching your zones
5. Once validated, zones will appear as climate entities

### Options

Once the integration is added, you can adjust:
- **Polling Interval**: How often (in seconds) the integration fetches zone status from the cloud (default: 60 seconds, range: 10–3600 seconds)

The coordinator adds a small jitter (0–10s) and exponential backoff on transient errors to reduce API stampedes.

**Recommendation:** Keep the polling interval at 60 seconds or higher to avoid unnecessary load.

Adjust this in **Settings** → **Devices & Services** → **Radialight Cloud** → **Options**.

## Climate Entity Behavior

### Temperature Display

- **Current Temperature**: Average detected temperature of online radiators in the zone
  - Falls back to the first radiator if all are offline
  - Temperatures from the API are in deci-degrees (e.g., 211 = 21.1°C)

- **Target Temperature**: Zone's comfort temperature (`tComfort`)
  - Adjustable via the climate entity's set temperature control
  - Minimum: 7°C, Maximum: 30°C, Step: 0.5°C

### Availability

A zone is considered available if **any radiator in that zone is online** (`isOffline == false`).

### Setting Temperature

When you adjust the target temperature:
1. The integration converts your input (°C float) to deci-degrees (rounded integer)
2. It sends a POST request to `/zone/<zone_id>` with the **full zone configuration** including:
   - `programId`
   - `tComfort` (new target temperature in deci-degrees)
   - `tECO`, `window`, `mode`, `pir`, `lock` (existing values)
3. The coordinator refreshes zone data after the update

### Preset Modes

- **program**: Best-effort return to scheduled program. This currently re-sends the existing zone configuration.
- **comfort**: Sets the target to the zone comfort temperature.
- **eco**: Sets the target to the zone eco temperature (`tECO`).

> Note: The exact API call to clear server-side overrides is not yet confirmed. “program” is implemented as a safe best-effort payload re-send.

### Extra Attributes

The climate entity exposes these attributes:
- `zone_id`: Zone ID
- `zone_name`: Zone name
- `program_id`: Associated program ID
- `mode`: Current zone mode (numeric, not yet fully interpreted)
- `info_mode`: Zone info mode
- `is_in_override`: Best-effort override state
- `t_eco`: Eco temperature in deci-degrees
- `t_eco_celsius`: Eco temperature in °C
- `override`: Override object (if active)
- `window`: Window mode value
- `pir`: PIR sensor setting
- `lock`: Lock setting
- `last_week_usage`: Usage statistics
- `products_summary`: List of radiators with:
  - `name`, `id`
  - `is_offline`: Whether the radiator is offline
  - `detected_temperature`: Current temperature in deci-degrees
  - `is_warming`: Whether radiator is actively heating
  - `is_in_override`: Whether radiator is in override mode

## Entities & Controls

### Switches (LED Control)

Each radiator has an LED control switch:
- **Entity**: `switch.{product_name}_led`
- **Purpose**: Control the indicator LED brightness on the radiator
- **State**: On/Off reflects the LED status
- **Availability**: Switch unavailable if radiator is offline

### Binary Sensors (Product Status)

Each radiator has four binary sensors:
- **Warming** (`{product_name} Warming`): Indicates if radiator is actively heating
- **Offline** (`{product_name} Offline`): Indicates if radiator is offline or unreachable
- **In Override** (`{product_name} In Override`): Indicates if radiator has an active override
- **LED** (`{product_name} LED`): Reflects the current LED on/off state

All product entities are **enabled by default** and can be disabled via integration options if not needed.

### Temperature Sensors (Product Level)

Each radiator exposes:
- **Temperature** (`{product_name} Temperature`): Current detected temperature in °C
- **Availability**: Unavailable if radiator is offline

### Zone-Level Sensors
Zone-level sensors are provided:
- **Average Temperature** (°C)
- **Last Week Usage** (raw list in attributes; today/yesterday if available)

### Account-Level Energy Sensors

The integration provides energy monitoring sensors suitable for the **Home Assistant Energy Dashboard**:

#### Energy Total (for Energy Dashboard)
- **Entity**: `sensor.radialight_energy_total`
- **Type**: TOTAL_INCREASING (monotonically increasing)
- **Unit**: kWh
- **Purpose**: Canonical total energy sensor for the Energy Dashboard
- **Persistence**: Total is persisted across restarts in `.storage/radialight_energy_total`

This sensor accumulates energy usage by tracking new usage data points from the API. It never decreases and maintains state across Home Assistant restarts.

**To use in the Energy Dashboard:**
1. Go to **Settings** → **Dashboards** → **Energy**
2. Click **Add Consumption**
3. Select **sensor.radialight_energy_total**
4. Save

#### Usage Sensors (Measurement)
- **Radialight Usage Last Hour**: Most recent hourly usage point (kWh)
- **Radialight Usage Today**: Total usage since midnight local time (kWh)
- **Radialight Usage Yesterday**: Total usage for yesterday (kWh)
- **Radialight Usage Rolling 24h**: Total usage over last 24 hours (kWh)

These sensors use `state_class: measurement` and may fluctuate or reset daily.

#### Usage Scaling

The integration supports configurable usage scaling to match your API's units:
- **deciwh** (default): API values are 0.1 Wh (deci-Wh) → multiplied by 10 then divided by 1000 for kWh
- **wh**: API values are Wh → divided by 1000 for kWh
- **raw**: API values displayed as-is with no unit (for debugging)

Configure this in **Settings** → **Devices & Services** → **Radialight Cloud** → **Options**.

#### Using Utility Meter (Optional)

For daily/weekly/monthly totals, use Home Assistant's built-in `utility_meter`:

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

Add this to your `configuration.yaml` and restart Home Assistant to create daily/weekly/monthly reset meters.

## Authentication & Token Handling

The integration uses the **Firebase Secure Token refresh flow**:

1. Your refresh token is securely stored in Home Assistant's configuration
2. On startup and before token expiry, the integration fetches a new ID token from:
   ```
   POST https://securetoken.googleapis.com/v1/token?key=<FIREBASE_API_KEY>
   ```
3. All requests to the Radialight API include: `Authorization: Bearer <id_token>`
4. If a 401 response is received, the token is automatically refreshed and the request is retried
5. **Tokens and Authorization headers are never logged** to protect your credentials

## Data & Privacy

- This is a **cloud-based integration**; all data travels through Radialight's servers
- Refresh tokens and API keys are stored locally in Home Assistant and never shared with third parties
- The integration only fetches zone and radiator status data; it does not store historical data locally

## Diagnostics

Diagnostics are available via Home Assistant’s diagnostics panel and include sanitized zone data, polling interval, and coordinator status. Tokens and API keys are always redacted.

## Limitations & Important Warnings

⚠️ **Cloud-Based Integration**: This integration relies on Radialight's cloud API. If their service is unavailable, the integration cannot function. All data is transmitted through their servers.

⚠️ **Polling-Based Updates**: The integration fetches data every 60 seconds (configurable). This is not real-time control. There will be a delay between your action and when it takes effect.

⚠️ **API May Change**: The Radialight API is not officially documented. The underlying API may change without notice, which could break this integration. If the integration stops working, it may require an update.

⚠️ **Data Accuracy**: Energy values are calculated from API data and may not exactly match official Radialight app statistics due to rounding or data availability differences.

### Known Limitations

- **Schedules (WeekPlans)**: Program schedules are not editable via Home Assistant
- **Mode Interpretation**: The `mode` and `infoMode` fields are numeric; their exact meanings are not fully mapped
- **Per-Radiator Climate Entities**: Each zone has one climate entity (not per radiator)

## Documentation Policy

**This README is the single source of truth for user-facing documentation.** All future documentation updates must extend this file. Do not create additional .md files in the repository.

## Troubleshooting

### "Invalid credentials" error
- Verify your Firebase API Key and Refresh Token are correct
- Ensure your Radialight account is active and has at least one zone configured

### Climate entity shows "unavailable"
- Ensure at least one radiator in the zone is powered on and online
- Check the zone's `products` attribute to see radiator status

### Token refresh failures
- Check Home Assistant logs for network errors
- Ensure your internet connection is stable
- Verify the Radialight API is accessible

## API Endpoints Used

- `GET /zones`: Fetch all zones and their radiators
- `GET /usage?period=day&comparison=0`: Fetch account-level hourly usage
- `GET /usage?period=day&comparison=0&zone=<zone_id>`: Fetch per-zone hourly usage (each zone requires one call)
- `POST /zone/<zone_id>`: Update zone setpoint and configuration
- `POST https://securetoken.googleapis.com/v1/token`: Firebase token refresh

### Per-Zone Usage Fetching

The integration fetches energy usage separately for each zone using the zone query parameter:
```
GET https://myradialight-fe-prod.opengate.it/usage?comparison=0&period=day&zone=<zone_id>
```

This means:
- If you have N zones, the integration makes N+1 calls to the /usage endpoint per polling cycle (one per zone + one for account total)
- With default polling interval (60 seconds), this is approximately 1 call per second per zone in steady state
- Per-zone energy sensors show monotonic totals for that specific zone only
- Rolling 24-hour usage windows are calculated independently per zone using UTC cutoff

**Important:** Previously, all zones showed identical usage values because the same account-level endpoint was used. Now each zone's sensors use that zone's specific hourly usage data.

## Support

For issues, feature requests, or questions, please open an issue on the [GitHub repository](https://github.com/YOUR_GITHUB_USERNAME/radialight-hass).

## License

MIT License
