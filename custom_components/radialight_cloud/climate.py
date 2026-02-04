"""Climate platform for Radialight Cloud zones."""

import logging
from typing import Any, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import HomeAssistantError

from .api import RadialightAPIClient, RadialightError
from .coordinator import RadialightCoordinator
from .const import (
    DOMAIN,
    DATA_API,
    DATA_COORDINATOR,
    MIN_TEMP,
    MAX_TEMP,
    TEMP_STEP,
    PRESET_PROGRAM,
    PRESET_COMFORT,
    PRESET_ECO,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: RadialightCoordinator = data[DATA_COORDINATOR]
    api: RadialightAPIClient = data[DATA_API]

    zones_by_id = coordinator.get_zones_by_id()
    entities = [
        RadialightClimate(coordinator, api, zone_id, zone)
        for zone_id, zone in zones_by_id.items()
    ]

    async_add_entities(entities)


class RadialightClimate(ClimateEntity):
    """Climate entity for a Radialight zone."""

    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_max_temp = MAX_TEMP
    _attr_min_temp = MIN_TEMP
    _attr_target_temperature_step = TEMP_STEP
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = [PRESET_PROGRAM, PRESET_COMFORT, PRESET_ECO]

    def __init__(
        self,
        coordinator: RadialightCoordinator,
        api: RadialightAPIClient,
        zone_id: str,
        zone: dict,
    ) -> None:
        """Initialize the climate entity.

        Args:
            coordinator: The data coordinator.
            api: The API client.
            zone_id: Zone ID.
            zone: Zone data.
        """
        self.coordinator = coordinator
        self.api = api
        self._zone_id = zone_id
        self._zone = zone

        self._attr_name = zone.get("name", f"Zone {zone_id}")
        self._attr_unique_id = zone_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        zone = self.coordinator.get_zone(self._zone_id) or self._zone
        return DeviceInfo(
            identifiers={(DOMAIN, self._zone_id)},
            name=zone.get("name", f"Zone {self._zone_id}"),
            manufacturer="Radialight",
            model="ICON Zone",
        )

    @property
    def available(self) -> bool:
        """Zone available if any product is online."""
        if not self.coordinator.last_update_success:
            return False
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return False

        products = zone.get("products", [])
        # Available if any product is not offline
        return any(not p.get("isOffline", True) for p in products)

    @property
    def hvac_mode(self) -> HVACMode:
        """Always in heat mode."""
        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode (not supported, always heat)."""
        pass

    @property
    def current_temperature(self) -> Optional[float]:
        """Return current temperature.

        Averages detected temperature of online products, or falls back to first product.
        """
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return None

        products = zone.get("products", [])
        if not products:
            return None

        # Get online products with temperature data
        online_products = [
            p for p in products
            if not p.get("isOffline", True) and "detectedTemperature" in p
        ]

        if online_products:
            temps = [p["detectedTemperature"] for p in online_products]
            avg_temp = sum(temps) / len(temps)
            return avg_temp / 10.0

        # Fallback to first product
        first_product = products[0]
        if "detectedTemperature" in first_product:
            return first_product["detectedTemperature"] / 10.0

        return None

    @property
    def target_temperature(self) -> Optional[float]:
        """Return target temperature."""
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return None

        t_comfort = zone.get("tComfort")
        if t_comfort is None:
            return None

        return t_comfort / 10.0

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode."""
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return None

        is_in_override = self._is_in_override(zone)
        if not is_in_override:
            return PRESET_PROGRAM

        t_comfort = zone.get("tComfort")
        t_eco = zone.get("tECO")
        if t_comfort is not None and t_eco is not None and t_comfort == t_eco:
            return PRESET_ECO

        return PRESET_COMFORT

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature.

        Args:
            **kwargs: Temperature and other parameters.
        """
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            raise HomeAssistantError("Zone not available")

        # Convert float °C to int deci-C
        t_comfort = round(temperature * 10)

        # Build payload with all required fields
        program = zone.get("program", {})
        program_id = program.get("id")
        if program_id is None:
            _LOGGER.error("Zone %s has no program ID", self._zone_id)
            return

        try:
            await self.api.set_zone_setpoint(
                self._zone_id,
                program_id,
                t_comfort,
                zone.get("tECO", 100),
                zone.get("window", 0),
                zone.get("mode", 0),
                zone.get("pir", 0),
                zone.get("lock", 0),
            )

            # Update coordinator data with new zone state
            try:
                await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.debug(
                    "Coordinator refresh failed after set temperature for zone %s: %s",
                    self._zone_id,
                    err,
                )

        except RadialightError as err:
            raise HomeAssistantError(
                f"Failed to set temperature for zone {self._zone_id}: {err}"
            ) from err

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode for the zone.

        "program" is best-effort until the exact API call is confirmed.
        """
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            raise HomeAssistantError("Zone not available")

        program = zone.get("program", {})
        program_id = program.get("id")
        if program_id is None:
            raise HomeAssistantError("Zone program not available")

        t_eco = zone.get("tECO", 100)
        t_comfort = zone.get("tComfort", 200)

        if preset_mode == PRESET_ECO:
            t_comfort = t_eco

        try:
            if preset_mode == PRESET_PROGRAM:
                await self.api.clear_override(
                    self._zone_id,
                    program_id,
                    t_comfort,
                    t_eco,
                    zone.get("window", 0),
                    zone.get("mode", 0),
                    zone.get("pir", 0),
                    zone.get("lock", 0),
                )
            else:
                await self.api.set_zone_setpoint(
                    self._zone_id,
                    program_id,
                    t_comfort,
                    t_eco,
                    zone.get("window", 0),
                    zone.get("mode", 0),
                    zone.get("pir", 0),
                    zone.get("lock", 0),
                )

            try:
                await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.debug(
                    "Coordinator refresh failed after set preset for zone %s: %s",
                    self._zone_id,
                    err,
                )
        except RadialightError as err:
            raise HomeAssistantError(
                f"Failed to set preset for zone {self._zone_id}: {err}"
            ) from err

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return {}

        products = zone.get("products", [])
        products_summary = [
            {
                "name": p.get("name"),
                "id": p.get("id"),
                "is_offline": p.get("isOffline"),
                "detected_temperature": p.get("detectedTemperature"),
                "is_warming": p.get("isWarming"),
                "is_in_override": p.get("isInOverride"),
            }
            for p in products
        ]

        t_eco = zone.get("tECO")
        t_eco_celsius = t_eco / 10.0 if t_eco is not None else None

        return {
            "zone_id": self._zone_id,
            "zone_name": zone.get("name"),
            "program_id": zone.get("program", {}).get("id"),
            "mode": zone.get("mode"),
            "info_mode": zone.get("infoMode"),
            "is_in_override": self._is_in_override(zone),
            "t_eco": t_eco,
            "t_eco_celsius": t_eco_celsius,
            "override": zone.get("override"),
            "window": zone.get("window"),
            "pir": zone.get("pir"),
            "lock": zone.get("lock"),
            "last_week_usage": zone.get("lastWeekUsage"),
            "products_summary": products_summary,
        }

    async def async_added_to_hass(self) -> None:
        """Register callback when entity is added."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.async_write_ha_state()

    @staticmethod
    def _is_in_override(zone: dict) -> bool:
        """Best-effort override detection from zone and products."""
        override = zone.get("override")
        if override:
            return True
        products = zone.get("products", [])
        return any(p.get("isInOverride") for p in products)
