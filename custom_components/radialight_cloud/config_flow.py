"""Config flow for Radialight Cloud integration."""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RadialightAPIClient, RadialightError
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
    CONF_SHOW_ADVANCED_ENTITIES,
    DEFAULT_SHOW_ADVANCED_ENTITIES,
    CONF_USAGE_SCALE,
    DEFAULT_USAGE_SCALE,
    USAGE_SCALE_RAW,
    USAGE_SCALE_WH,
    USAGE_SCALE_DECIWH,
)

_LOGGER = logging.getLogger(__name__)


async def validate_credentials(
    hass: HomeAssistant, firebase_api_key: str, refresh_token: str
) -> None:
    """Validate credentials by attempting to fetch zones.

    Args:
        hass: Home Assistant instance.
        firebase_api_key: Firebase API key.
        refresh_token: Refresh token.

    Raises:
        CannotConnect: If connection fails.
        InvalidAuth: If credentials are invalid.
    """
    session = async_get_clientsession(hass)
    try:
        api = RadialightAPIClient(firebase_api_key, refresh_token, session)
        await api.get_zones()
    except RadialightError as err:
        if err.retryable:
            raise CannotConnect("Cannot connect to Radialight Cloud") from err
        raise InvalidAuth(f"Invalid credentials: {err}") from err


class RadialightCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Radialight Cloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle user initiated config flow.

        Args:
            user_input: User provided input.

        Returns:
            Form step or create entry.
        """
        errors = {}

        if user_input is not None:
            # Validate credentials
            try:
                await validate_credentials(
                    self.hass,
                    user_input[CONF_FIREBASE_API_KEY],
                    user_input[CONF_REFRESH_TOKEN],
                )
            except InvalidAuth as err:
                errors["base"] = "invalid_auth"
                _LOGGER.error("Invalid credentials: %s", err)
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Cannot connect: %s", err)
            except Exception as err:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.error("Unexpected error: %s", err)

            if not errors:
                # Create config entry
                return self.async_create_entry(
                    title="Radialight Cloud",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_FIREBASE_API_KEY): str,
                vol.Required(CONF_REFRESH_TOKEN): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow."""
        return RadialightCloudOptionsFlow(config_entry)


class RadialightCloudOptionsFlow(OptionsFlow):
    """Options flow for Radialight Cloud."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle options flow.

        Args:
            user_input: User provided input.

        Returns:
            Form step or updated options.
        """
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        polling_interval = self.config_entry.options.get(
            CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL
        )
        enable_product_entities = self.config_entry.options.get(
            CONF_ENABLE_PRODUCT_ENTITIES, DEFAULT_ENABLE_PRODUCT_ENTITIES
        )
        enable_usage_sensors = self.config_entry.options.get(
            CONF_ENABLE_USAGE_SENSORS, DEFAULT_ENABLE_USAGE_SENSORS
        )
        show_advanced_entities = self.config_entry.options.get(
            CONF_SHOW_ADVANCED_ENTITIES, DEFAULT_SHOW_ADVANCED_ENTITIES
        )
        usage_scale = self.config_entry.options.get(
            CONF_USAGE_SCALE, DEFAULT_USAGE_SCALE
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLLING_INTERVAL,
                    default=polling_interval,
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                vol.Optional(
                    CONF_ENABLE_PRODUCT_ENTITIES,
                    default=enable_product_entities,
                ): bool,
                vol.Optional(
                    CONF_ENABLE_USAGE_SENSORS,
                    default=enable_usage_sensors,
                ): bool,
                vol.Optional(
                    CONF_SHOW_ADVANCED_ENTITIES,
                    default=show_advanced_entities,
                ): bool,
                vol.Optional(
                    CONF_USAGE_SCALE,
                    default=usage_scale,
                ): vol.In(
                    [USAGE_SCALE_RAW, USAGE_SCALE_WH, USAGE_SCALE_DECIWH]
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )


class CannotConnect(HomeAssistantError):
    """Exception for connection errors."""


class InvalidAuth(HomeAssistantError):
    """Exception for authentication errors."""
