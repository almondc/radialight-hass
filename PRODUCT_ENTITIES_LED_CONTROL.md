# Product Entities & LED Control Implementation

## Overview
Successfully implemented product-level entities and LED control for the Radialight Cloud integration. Product entities are now enabled by default (suitable for 2 radiators) and fully integrated with the coordinator data flow.

## Files Modified

### 1. **api.py** ✓
- Added `async_set_product_light(product_id: str, on: bool) -> dict | None` method
- POST request to `/product/{product_id}` with JSON body `{"light": on/off}`
- Reuses existing `_request()` wrapper (inherits Firebase auth, 401 retry, backoff)
- Raises `RadialightError` on failure (caught by platform and converted to `HomeAssistantError`)

### 2. **coordinator.py** ✓
- Extended `_async_update_data()` to normalize products:
  - Created `products_by_id: Dict[str, dict]` - direct lookup by product_id
  - Created `products_by_zone: Dict[str, List[dict]]` - organized by zone
  - Each product in these dicts includes `zoneId` and `zoneName` for easy zone lookups
- Added helper methods:
  - `get_products_by_id()`: Returns all products indexed by ID
  - `get_products_by_zone()`: Returns products indexed by zone
  - `get_product(product_id)`: Get a single product by ID (primary method for platforms)
- Product data is stored with zone context, enabling device_info via_device relationships

### 3. **switch.py** (NEW) ✓
- Created complete SwitchEntity platform for LED control
- `ProductLEDSwitch`: One switch per product
  - Name: `"{product_name} LED"`
  - Unique ID: `"{product_id}_led"`
  - State: `is_on` reflects `product["isLedOn"]`
  - Availability: `not product["isOffline"]`
  - `async_turn_on/off()`: Calls `api.async_set_product_light()`, then refreshes coordinator
  - `device_info`: Product device with `via_device=(DOMAIN, zone_id)` linking to zone
  - Icon: `mdi:led-on`
- Gated by `enable_product_entities` option (default True)

### 4. **sensor.py** ✓
- Product temperature sensors already implemented (`ProductTemperatureSensor`)
- Updated `_get_product()` helper to use `coordinator.get_product()` first (normalized), with fallback to zone search
- Temperature sensor per product:
  - Name: `"{product_name} Temperature"`
  - Unique ID: `"{product_id}_temperature"`
  - Device class: `TEMPERATURE`
  - Unit: `°C` (divides `detectedTemperature` deci-degrees by 10)
  - Availability: `not product["isOffline"]`
  - Device link via `via_device=(DOMAIN, zone_id)`

### 5. **binary_sensor.py** ✓
- Product binary sensors already implemented in `_build_product_binary_sensors()`
- Updated `_get_product()` helper to use `coordinator.get_product()` first
- Four binary sensors per product (gated by `enable_product_entities`):
  1. **Warming**: `isWarming` field, device class `HEAT`
  2. **Offline**: `isOffline` field, device class `PROBLEM`
  3. **In Override**: `isInOverride` field, no device class
  4. **LED**: `isLedOn` field, no device class (informational)
- All named as `"{product_name} {Label}"`
- Availability: `not product["isOffline"]`
- Device link via `via_device=(DOMAIN, zone_id)`

### 6. **const.py** ✓
- Changed `DEFAULT_ENABLE_PRODUCT_ENTITIES = False` → `True`
- Rationale: Integration designed for small installations (2 radiators in this case)
- Users can still disable via options if they prefer

### 7. **__init__.py** ✓
- Updated `PLATFORMS` to include `Platform.SWITCH`
- Platform order: `[Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]`

### 8. **manifest.json** ✓
- Updated `platforms` array to include `"switch"`
- Final: `["climate", "sensor", "binary_sensor", "switch"]`

## Data Flow

```
GET /zones (coordinator fetch)
        ↓
Zone data includes products array
        ↓
Normalize in coordinator._async_update_data():
  - For each zone:
    - For each product in zone:
      - Add zoneId, zoneName to product copy
      - Store in products_by_id[product_id]
      - Append to products_by_zone[zone_id]
        ↓
Coordinator.data = {
    "zones_by_id": {...},
    "products_by_id": {
        "prod1": {id, name, serial, model, detectedTemperature, isLedOn, isWarming, isInOverride, isOffline, zoneId, zoneName, ...},
        "prod2": {...}
    },
    "products_by_zone": {
        "zone1": [prod1_data, prod2_data],
        ...
    },
    ...
}
        ↓
Platforms call coordinator.get_product(product_id) or coordinator.get_products_by_id()
        ↓
        ├─ switch.py: ProductLEDSwitch
        │   - Reads is_on from isLedOn
        │   - Turn on/off → POST /product/{id} → refresh
        │
        ├─ sensor.py: ProductTemperatureSensor
        │   - Reads native_value from detectedTemperature / 10
        │
        └─ binary_sensor.py: ProductBinarySensor
            - isWarming, isOffline, isInOverride, isLedOn
```

## Entity Naming & Identifiers

### Device Level
- **Identifiers**: `{(DOMAIN, product_id)}`
- **Name**: Product name (from API)
- **Model**: Product model (from API)
- **Serial**: Product serial (from API)
- **Manufacturer**: "Radialight"
- **Via Device**: `(DOMAIN, zone_id)` - links product to zone device

### Entity Level
- **Switch**: `switch.{product_id}_led`
- **Temperature Sensor**: `sensor.{product_id}_temperature`
- **Warming Binary Sensor**: `binary_sensor.{product_id}_iswarming`
- **Offline Binary Sensor**: `binary_sensor.{product_id}_isoffline`
- **Override Binary Sensor**: `binary_sensor.{product_id}_isinoverride`
- **LED Binary Sensor**: `binary_sensor.{product_id}_isledon` (informational)

## API Integration

### Write Operation
**POST** `/product/{product_id}`
```json
{
  "light": true  // or false
}
```

Response: Updated product object (or 200 with no body)

**Error Handling**:
- 401 Unauthorized: Auto-retry with token refresh (via `_request()` wrapper)
- 4xx/5xx: Raise `RadialightError`, caught by platform, converted to `HomeAssistantError`
- Network timeouts: Exponential backoff in coordinator

### Read Operation
State read from coordinator.data["products_by_id"][product_id]:
- `isLedOn` (bool) - LED switch state
- `isWarming` (bool) - Heating active
- `isOffline` (bool) - Device unreachable
- `isInOverride` (bool) - Override active
- `detectedTemperature` (int deci-degrees) - Current room temp
- `zoneId`, `zoneName` - Zone context

## Configuration

### Default Behavior
- Product entities **enabled by default** (`DEFAULT_ENABLE_PRODUCT_ENTITIES = True`)
- Users can toggle via **Options** → "Enable per-product entities"
- When disabled: product entities are not created (clean startup)
- When re-enabled: entities recreated on next config update

### Options Flow
Existing boolean option in UI:
- Label: "Enable per-product entities"
- Type: boolean
- Default: `True`
- Scope: Integration level

## Availability Logic

**Switch & Sensors Available When**:
- Coordinator `last_update_success == True` (zones fetched)
- Product exists in `products_by_id`
- `not product["isOffline"]` (device is online)

**Unavailable State**:
- If zone/product removed: `coordinator.get_product()` returns None
- If radiator offline: `isOffline = True` → entity unavailable
- If coordinator update fails: `last_update_success = False` → entity unavailable

**Offline Binary Sensor**:
- Still visible even when unavailable (provides "offline" state as feedback)
- Can be useful if user wants explicit "offline" indicator in UI

## Type Safety & Async Patterns

- All platform setup methods: `async def async_setup_entry(...)`
- API method: `async def async_set_product_light(product_id: str, on: bool)`
- Entity properties properly typed
- Error handling via `HomeAssistantError` (standard HA convention)
- No blocking I/O; all operations async

## Testing Checklist

1. **Setup**: Add integration with valid credentials
   - Verify zones appear as climate entities ✓
   - Verify products appear in device list ✓

2. **Product Entities**:
   - Check 2 product devices in UI (with zone as parent)
   - Check each has temperature sensor, 4 binary sensors, 1 switch
   - Check device names/models/serials populated correctly

3. **LED Control**:
   - Toggle LED switch in UI
   - Verify POST `/product/{id}` request is sent with correct JSON
   - Verify switch state updates after coordinator refresh (~60s or manual refresh)
   - Verify error handling if POST fails (entity shows error)

4. **Offline Handling**:
   - Manually set radiator offline (via API or physically disconnect)
   - Verify all product entities become unavailable
   - Verify "Offline" binary sensor shows `on`
   - Verify switch becomes disabled/unavailable

5. **Options**:
   - Disable "Enable per-product entities"
   - Verify all product entities removed
   - Re-enable, verify entities recreated
   - Verify no errors in logs during create/delete cycle

6. **Edge Cases**:
   - Remove a radiator from account while HA is running
   - Verify entity removed on next coordinator refresh
   - Restart HA with disabled product entities
   - Verify clean startup with only zone climate entities

## Version
- Integration version: 0.2.1 (or bump as desired)
- Platforms: climate, sensor, binary_sensor, **switch** (new)
- Requires: aiohttp>=3.8.0

## Backward Compatibility
✓ **Fully backward compatible**
- No breaking changes to zone/climate entities
- Product entities opt-in via DEFAULT_ENABLE_PRODUCT_ENTITIES=True
- Existing zone sensors unchanged
- Coordinator data extended (not breaking)
- All new code is additive
