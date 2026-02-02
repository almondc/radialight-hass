# Product Entities & LED Control - Complete Implementation Summary

## Changes Overview

Successfully implemented product-level entities with LED control for the Radialight Cloud integration. The integration now exposes per-product temperature sensors, state binary sensors, and LED control switches. Product entities are enabled by default (suitable for small installations with 2 radiators).

---

## File-by-File Changes

### 1. **api.py**
**Change**: Added LED control method
```python
async def async_set_product_light(self, product_id: str, on: bool) -> dict | None:
    """Set product LED state."""
    payload = {"light": on}
    return await self._request("POST", f"/product/{product_id}", json=payload)
```
- Sends POST request to `/product/{product_id}` with `{"light": true/false}`
- Reuses `_request()` wrapper for auth, 401 retry, and backoff
- Raises `RadialightError` on failure
- No token/auth logging via existing redaction

---

### 2. **coordinator.py**
**Changes**: Product normalization and helper methods

**In `_async_update_data()`**:
- Added `products_by_id = {}` and `products_by_zone = {}` initialization
- Loop through zones and extract products:
  ```python
  for zone_id, zone in zones_by_id.items():
      products_by_zone[zone_id] = []
      for product in zone.get("products", []):
          product_id = product.get("id")
          if product_id:
              product_copy = dict(product)
              product_copy["zoneId"] = zone_id
              product_copy["zoneName"] = zone.get("name")
              products_by_id[product_id] = product_copy
              products_by_zone[zone_id].append(product_copy)
  ```
- Updated return dict to include `"products_by_id"` and `"products_by_zone"`

**New Helper Methods**:
```python
def get_products_by_id(self) -> Dict[str, Any]:
    """Get products organized by ID."""
    if self.data is None:
        return {}
    return self.data.get("products_by_id", {})

def get_products_by_zone(self) -> Dict[str, list[Dict[str, Any]]]:
    """Get products organized by zone."""
    if self.data is None:
        return {}
    return self.data.get("products_by_zone", {})

def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific product by ID."""
    products = self.get_products_by_id()
    return products.get(product_id)
```

---

### 3. **switch.py** (NEW FILE)
**Created**: Complete switch platform for LED control

**File Structure**:
- `async_setup_entry()`: Extracts products from coordinator and creates switches for each if `enable_product_entities=True`
- `ProductLEDSwitch`: SwitchEntity subclass
  - Reads state from `product["isLedOn"]`
  - `async_turn_on()`: Calls `api.async_set_product_light(product_id, True)` + refresh
  - `async_turn_off()`: Calls `api.async_set_product_light(product_id, False)` + refresh
  - Availability: `not product["isOffline"]`
  - Device info: Product device with `via_device=(DOMAIN, zone_id)`
  - Icon: `mdi:led-on`
  - Error handling: Catches `RadialightError` and raises `HomeAssistantError`

**Key Features**:
- Fully async, proper error handling
- Automatic refresh after toggle to sync state
- Device linking to zone (zone as parent device)
- Clean type hints throughout

---

### 4. **sensor.py**
**Changes**: Updated product helper method

**Updated `_get_product()` helper**:
- Now tries `coordinator.get_product(product_id)` first (normalized data)
- Falls back to searching zone products (for compatibility)
```python
def _get_product(coordinator, zone_id, product_id):
    if product_id is None:
        return None
    product = coordinator.get_product(product_id)  # NEW: Try normalized first
    if product is not None:
        return product
    # Fallback to zone search
    zone = coordinator.get_zone(zone_id)
    if zone is None:
        return None
    for prod in zone.get("products", []):
        if prod.get("id") == product_id:
            return prod
    return None
```

**Existing Product Sensors**:
- `ProductTemperatureSensor` (already implemented) unchanged
- Reads `detectedTemperature / 10.0` (deci-degrees to °C)
- Device class: `TEMPERATURE`
- Gated by `enable_product_entities` option

---

### 5. **binary_sensor.py**
**Changes**: Updated product helper method

**Updated `_get_product()` helper**:
- Same pattern as sensor.py (normalizes lookup)
- Ensures all product binary sensors use centralized retrieval

**Existing Product Binary Sensors**:
- `_build_product_binary_sensors()` (already implemented) unchanged:
  - Warming (isWarming, HEAT device class)
  - Offline (isOffline, PROBLEM device class)
  - In Override (isInOverride, no device class)
  - LED (isLedOn, informational)
- All gated by `enable_product_entities` option
- All include availability check

---

### 6. **const.py**
**Change**: Default for product entities

```python
DEFAULT_ENABLE_PRODUCT_ENTITIES = False  # BEFORE
DEFAULT_ENABLE_PRODUCT_ENTITIES = True   # AFTER
```

**Rationale**: Integration designed for small installations (2 radiators)

---

### 7. **__init__.py**
**Change**: Add switch platform

```python
PLATFORMS: Final = [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]
```

---

### 8. **manifest.json**
**Change**: Include switch platform

```json
"platforms": ["climate", "sensor", "binary_sensor", "switch"]
```

---

## Entity Structure

### Per Product (when `enable_product_entities=True`)

1. **Device**: `{(DOMAIN, product_id)}`
   - Name: Product name from API
   - Model: Product model from API
   - Serial: Product serial from API
   - Manufacturer: "Radialight"
   - Via Device: Zone device (zone_id as parent)

2. **Switch Entity**: LED Control
   - Unique ID: `{product_id}_led`
   - Name: `{product_name} LED`
   - Reads: `isLedOn`
   - Controls: POST `/product/{product_id}`
   - Icon: `mdi:led-on`

3. **Sensor Entity**: Temperature
   - Unique ID: `{product_id}_temperature`
   - Name: `{product_name} Temperature`
   - Reads: `detectedTemperature / 10` (deci-degrees to °C)
   - Device class: `TEMPERATURE`

4. **Binary Sensors**: State Indicators
   - Warming: `{product_id}_iswarming` (HEAT)
   - Offline: `{product_id}_isoffline` (PROBLEM)
   - Override: `{product_id}_isinoverride`
   - LED: `{product_id}_isledon` (informational)

---

## Data Structure in Coordinator

After fetch and normalization:

```python
coordinator.data = {
    "zones_by_id": {
        "zone1": {id, name, products: [...], ...},
        ...
    },
    "products_by_id": {
        "prod1": {
            id, name, serial, model,
            detectedTemperature, isLedOn, isWarming, isInOverride, isOffline,
            zoneId, zoneName,  # NEW: Added for context
            ...
        },
        "prod2": {...},
        ...
    },
    "products_by_zone": {
        "zone1": [prod1, prod2],
        ...
    },
    # ... usage data ...
}
```

---

## API Contract

### Write: LED Control
```
POST /product/{product_id}
Content-Type: application/json
Authorization: Bearer {id_token}

{
  "light": true  // or false
}
```

Response: Updated product object or 200 OK

**Error Handling**:
- 401 → Auto-retry with token refresh
- 4xx/5xx → RadialightError → HomeAssistantError
- Network timeout → Exponential backoff via coordinator

### Read: Product State
From coordinator.data["products_by_id"][product_id]:
- `id` (str)
- `name` (str)
- `serial` (str)
- `model` (str)
- `detectedTemperature` (int, deci-degrees)
- `isLedOn` (bool)
- `isWarming` (bool)
- `isInOverride` (bool)
- `isOffline` (bool)
- `zoneId` (str, zone context)
- `zoneName` (str, zone context)

---

## Configuration

### Default Settings
- **enable_product_entities**: `True` (enabled by default)
- Users can disable via Options UI if desired

### Options Flow
- Existing boolean option already in place
- Label: "Enable per-product entities"
- When changed: entities automatically recreated

---

## Testing Scenarios

### 1. Initial Setup
- [ ] Add integration with valid credentials
- [ ] Verify zone climate entities appear
- [ ] Verify 2 product devices appear in Devices list
- [ ] Each product device has correct name/model/serial

### 2. Product Entities
- [ ] Each product has:
  - 1 switch (LED)
  - 1 sensor (Temperature)
  - 4 binary sensors (Warming, Offline, Override, LED)
- [ ] All entities have correct unique_ids
- [ ] All entities link to zone device via `via_device`

### 3. LED Control
- [ ] Toggle LED switch in UI
- [ ] Switch becomes "turning on/off" state
- [ ] POST request sent to `/product/{id}`
- [ ] State updates after coordinator refresh
- [ ] Error handling if POST fails

### 4. Offline Handling
- [ ] Simulate radiator offline (via API or disconnect)
- [ ] All product entities become unavailable
- [ ] Offline binary sensor shows `on`
- [ ] Switch becomes disabled

### 5. Options Toggle
- [ ] Disable "Enable per-product entities"
- [ ] All product entities removed
- [ ] Re-enable, entities recreated
- [ ] No errors in logs

### 6. Edge Cases
- [ ] Remove radiator from account (coordinator refresh removes entity)
- [ ] Restart HA with disabled product entities
- [ ] Restart HA with enabled product entities

---

## Code Quality Checklist

- [x] All Python files compile without syntax errors
- [x] Type hints present throughout
- [x] All async methods properly defined
- [x] Error handling with HomeAssistantError
- [x] No token/auth logging
- [x] Follows Home Assistant patterns (CoordinatorEntity, DeviceInfo)
- [x] Consistent with existing code style
- [x] No breaking changes to existing entities
- [x] Backward compatible with previous integration versions

---

## Files Modified Summary

| File | Change Type | Status |
|------|------------|--------|
| api.py | Method Added | ✓ Complete |
| coordinator.py | Methods & Logic Added | ✓ Complete |
| switch.py | File Created | ✓ Complete |
| sensor.py | Helper Updated | ✓ Complete |
| binary_sensor.py | Helper Updated | ✓ Complete |
| const.py | Default Changed | ✓ Complete |
| __init__.py | Platform Added | ✓ Complete |
| manifest.json | Platform Added | ✓ Complete |

---

## Integration Details

**Platforms**:
- climate (zone thermostats)
- sensor (zone & account usage sensors, product temperature)
- binary_sensor (zone & product states)
- **switch** (product LED control) ← NEW

**Version**: 0.2.1 (or maintainer discretion)

**Compatibility**: Home Assistant Core 2023.12+

**Backward Compatible**: Yes, fully additive changes

---

## Deployment

1. **Source**: All changes in `/Users/cliff/Dev/radialight-hass/custom_components/radialight_cloud/`
2. **Synced to Dev**: `/Users/cliff/Dev/radialight-hass/ha-dev/config/custom_components/radialight_cloud/`
3. **Next Steps**: Test in HA environment, verify all scenarios work as expected

---

## Notes for Future Development

1. **Product Update Endpoint**: Currently read-only (LED state from GET /zones). Could add more write endpoints if API expands.

2. **Device Grouping**: Products are linked to zones via `via_device`. If needed, could enhance with area assignments.

3. **Telemetry**: All product state is read from coordinator data. If real-time updates needed, could add event-based polling.

4. **Validation**: Product data is assumed valid from API. Consider adding data validation if API becomes unstable.

5. **Firmware/Updates**: No product firmware or update checking currently. Could be added if API supports it.
