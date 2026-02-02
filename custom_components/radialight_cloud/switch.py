"""Switch platform for Radialight Cloud product LED control."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RadialightAPIClient, RadialightError
from .coordinator import RadialightCoordinator
from .const import DOMAIN, DATA_API, DATA_COORDINATOR, CONF_ENABLE_PRODUCT_ENTITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: RadialightCoordinator = data[DATA_COORDINATOR]
    api: RadialightAPIClient = data[DATA_API]
    enable_product_entities = data.get(CONF_ENABLE_PRODUCT_ENTITIES, False)

    entities: list[SwitchEntity] = []

    if enable_product_entities:
        for product_id, product in coordinator.get_products_by_id().items():
            entities.append(ProductLEDSwitch(coordinator, api, product_id, product))

    async_add_entities(entities)


class ProductLEDSwitch(CoordinatorEntity[RadialightCoordinator], SwitchEntity):
    """Switch entity for product LED control."""

    _attr_icon = "mdi:led-on"

    def __init__(
        self,
        coordinator: RadialightCoordinator,
        api: RadialightAPIClient,
        product_id: str,
        product: dict[str, Any],
    ) -> None:
        """Initialize the switch.

        Args:
            coordinator: The data coordinator.
            api: The API client.
            product_id: Product ID.
            product: Product data.
        """
        super().__init__(coordinator)
        self.api = api
        self._product_id = product_id
        self._product = product
        self._zone_id = product.get("zoneId")

        self._attr_name = f"{product.get('name', f'Product {product_id}')} LED"
        self._attr_unique_id = f"{product_id}_led"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        product = self.coordinator.get_product(self._product_id) or self._product
        return DeviceInfo(
            identifiers={(DOMAIN, self._product_id)},
            name=product.get("name", f"Product {self._product_id}"),
            model=product.get("model", "ICON Product"),
            serial_number=product.get("serial"),
            manufacturer="Radialight",
            via_device=(DOMAIN, self._zone_id) if self._zone_id else None,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if LED is on."""
        if not self.coordinator.data:
            return None
        product = self.coordinator.get_product(self._product_id)
        return product.get("isLedOn") if product else None

    @property
    def available(self) -> bool:
        """Return availability based on product online status."""
        if not self.coordinator.last_update_success:
            return False
        product = self.coordinator.get_product(self._product_id)
        if product is None:
            return False
        return not product.get("isOffline", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn LED on."""
        try:
            await self.api.async_set_product_light(self._product_id, True)
            await self.coordinator.async_request_refresh()
        except RadialightError as err:
            raise HomeAssistantError(f"Failed to turn on LED: {err}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn LED off."""
        try:
            await self.api.async_set_product_light(self._product_id, False)
            await self.coordinator.async_request_refresh()
        except RadialightError as err:
            raise HomeAssistantError(f"Failed to turn off LED: {err}") from err
