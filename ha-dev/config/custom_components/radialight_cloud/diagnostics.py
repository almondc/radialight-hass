"""Diagnostics support for Radialight Cloud integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import redact_jwt
from .const import (
    CONF_FIREBASE_API_KEY,
    CONF_REFRESH_TOKEN,
    CONF_POLLING_INTERVAL,
    CONF_ENABLE_PRODUCT_ENTITIES,
    CONF_ENABLE_USAGE_SENSORS,
    CONF_USAGE_SCALE,
    DATA_COORDINATOR,
    DOMAIN,
    INTEGRATION_VERSION,
)


def _redact(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return redact_jwt(value)
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _sanitize_config_entry(entry: ConfigEntry) -> dict[str, Any]:
    data = dict(entry.data)
    options = dict(entry.options)
    if CONF_FIREBASE_API_KEY in data:
        data[CONF_FIREBASE_API_KEY] = "<redacted>"
    if CONF_REFRESH_TOKEN in data:
        data[CONF_REFRESH_TOKEN] = "<redacted>"
    return {"data": data, "options": options}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    zones_by_id = coordinator.data.get("zones_by_id", {}) if coordinator.data else {}
    usage_points = coordinator.data.get("usage_points", []) if coordinator.data else []

    # Build usage snapshot (sanitized, showing only summary + sample)
    usage_snapshot = {}
    if usage_points:
        usage_snapshot = {
            "first_timestamp": usage_points[0][0].isoformat() if usage_points else None,
            "last_timestamp": usage_points[-1][0].isoformat() if usage_points else None,
            "point_count": len(usage_points),
            "sample_last_5_points": [
                {
                    "timestamp": dt_obj.isoformat(),
                    "usage": usage_val,
                }
                for dt_obj, usage_val in usage_points[-5:]
            ],
        }

    # Add usage calculations for different scales
    if coordinator.data:
        usage_snapshot["calculations"] = {
            "raw_today": coordinator.data.get("usage_today_raw"),
            "kwh_today_assuming_wh": coordinator.data.get("usage_today_kwh_wh"),
            "kwh_today_assuming_deciwh": coordinator.data.get("usage_today_kwh_deciwh"),
            "raw_24h": coordinator.data.get("usage_24h_raw"),
            "kwh_24h_assuming_wh": coordinator.data.get("usage_24h_kwh_wh"),
            "kwh_24h_assuming_deciwh": coordinator.data.get("usage_24h_kwh_deciwh"),
        }

    diagnostics = {
        "integration_version": INTEGRATION_VERSION,
        "config_entry": _sanitize_config_entry(entry),
        "polling_interval": hass.data[DOMAIN][entry.entry_id].get(
            CONF_POLLING_INTERVAL
        ),
        "enable_product_entities": hass.data[DOMAIN][entry.entry_id].get(
            CONF_ENABLE_PRODUCT_ENTITIES
        ),
        "enable_usage_sensors": hass.data[DOMAIN][entry.entry_id].get(
            CONF_ENABLE_USAGE_SENSORS
        ),
        "usage_scale": hass.data[DOMAIN][entry.entry_id].get(
            CONF_USAGE_SCALE
        ),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update": coordinator.last_update,
            "update_interval": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
        },
        "zones": _redact(zones_by_id),
        "usage": usage_snapshot,
    }

    return diagnostics
