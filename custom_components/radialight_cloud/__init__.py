"""Radialight Cloud integration for Home Assistant."""

import logging
from datetime import timedelta
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RadialightAPIClient
from .coordinator import RadialightCoordinator
from .const import (
    DOMAIN,
    CONF_FIREBASE_API_KEY,
    CONF_REFRESH_TOKEN,
    CONF_POLLING_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    CONF_ENABLE_PRODUCT_ENTITIES,
    DEFAULT_ENABLE_PRODUCT_ENTITIES,
    CONF_ENABLE_USAGE_SENSORS,
    DEFAULT_ENABLE_USAGE_SENSORS,
    CONF_USAGE_SCALE,
    DEFAULT_USAGE_SCALE,
    DATA_API,
    DATA_COORDINATOR,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final = [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Radialight Cloud from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry.

    Returns:
        True if setup succeeded.
    """
    hass.data.setdefault(DOMAIN, {})

    # Extract credentials from config
    firebase_api_key = entry.data[CONF_FIREBASE_API_KEY]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]

    # Get polling interval from options or use default
    polling_interval = entry.options.get(
        CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL
    )
    enable_product_entities = entry.options.get(
        CONF_ENABLE_PRODUCT_ENTITIES, DEFAULT_ENABLE_PRODUCT_ENTITIES
    )
    enable_usage_sensors = entry.options.get(
        CONF_ENABLE_USAGE_SENSORS, DEFAULT_ENABLE_USAGE_SENSORS
    )
    usage_scale = entry.options.get(
        CONF_USAGE_SCALE, DEFAULT_USAGE_SCALE
    )

    # Create API client with session
    session = async_get_clientsession(hass)
    api = RadialightAPIClient(firebase_api_key, refresh_token, session)

    # Create coordinator
    coordinator = RadialightCoordinator(hass, api, polling_interval, usage_scale)

    # Load persisted energy storage
    await coordinator.async_load_energy_storage()

    # Perform initial fetch
    await coordinator.async_config_entry_first_refresh()

    # Store references
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_API: api,
        DATA_COORDINATOR: coordinator,
        CONF_POLLING_INTERVAL: polling_interval,
        CONF_ENABLE_PRODUCT_ENTITIES: enable_product_entities,
        CONF_ENABLE_USAGE_SENSORS: enable_usage_sensors,
        CONF_USAGE_SCALE: usage_scale,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Add listener for options update
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry.

    Returns:
        True if unload succeeded.
    """
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Clean up data
        hass.data[DOMAIN].pop(entry.entry_id, {})
        return True

    return False


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update.

    Args:
        hass: Home Assistant instance.
        entry: Config entry.
    """
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: RadialightCoordinator = data[DATA_COORDINATOR]

    # Update polling interval
    polling_interval = entry.options.get(
        CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL
    )
    enable_product_entities = entry.options.get(
        CONF_ENABLE_PRODUCT_ENTITIES, DEFAULT_ENABLE_PRODUCT_ENTITIES
    )
    enable_usage_sensors = entry.options.get(
        CONF_ENABLE_USAGE_SENSORS, DEFAULT_ENABLE_USAGE_SENSORS
    )
    usage_scale = entry.options.get(
        CONF_USAGE_SCALE, DEFAULT_USAGE_SCALE
    )
    coordinator.update_interval = timedelta(seconds=polling_interval)
    data[CONF_POLLING_INTERVAL] = polling_interval
    data[CONF_ENABLE_PRODUCT_ENTITIES] = enable_product_entities
    data[CONF_ENABLE_USAGE_SENSORS] = enable_usage_sensors
    data[CONF_USAGE_SCALE] = usage_scale

    _LOGGER.debug("Updated polling interval to %d seconds", polling_interval)

    # Trigger refresh
    await coordinator.async_request_refresh()
