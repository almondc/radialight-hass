"""Binary sensor platform for Radialight Cloud zones and products."""

from __future__ import annotations

from typing import Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import RadialightCoordinator
from .const import DOMAIN, DATA_COORDINATOR, CONF_ENABLE_PRODUCT_ENTITIES


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: RadialightCoordinator = data[DATA_COORDINATOR]
    enable_product_entities = data.get(CONF_ENABLE_PRODUCT_ENTITIES, False)

    entities: list[BinarySensorEntity] = []
    for zone_id, zone in coordinator.get_zones_by_id().items():
        entities.extend(_build_zone_binary_sensors(coordinator, zone_id, zone))

        if enable_product_entities:
            for product in zone.get("products", []):
                entities.extend(
                    _build_product_binary_sensors(coordinator, zone_id, zone, product)
                )

    async_add_entities(entities)


class BaseCoordinatorBinarySensor(
    CoordinatorEntity[RadialightCoordinator], BinarySensorEntity
):
    """Base coordinator binary sensor for a Radialight zone."""

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._zone = zone

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        return self.coordinator.get_zone(self._zone_id) is not None

    @property
    def device_info(self) -> DeviceInfo:
        zone = self.coordinator.get_zone(self._zone_id) or self._zone
        return DeviceInfo(
            identifiers={(DOMAIN, self._zone_id)},
            name=zone.get("name", f"Zone {self._zone_id}"),
            manufacturer="Radialight",
            model="ICON Zone",
        )


class ZoneOverrideFlagBinarySensor(BaseCoordinatorBinarySensor):
    """Zone override flag binary sensor."""

    _attr_entity_registry_enabled_default = False
    def __init__(
        self,
        coordinator: RadialightCoordinator,
        zone_id: str,
        zone: dict,
        key: str,
        label: str,
    ) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._key = key
        self._attr_name = f"{zone.get('name', 'Zone')} Override {label}"
        self._attr_unique_id = f"{zone_id}_override_{key}"

    @property
    def is_on(self) -> Optional[bool]:
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return None
        override = zone.get("override") or {}
        return bool(override.get(self._key))


class ZoneAnyWarmingBinarySensor(BaseCoordinatorBinarySensor):
    """Zone any warming binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Any Warming"
        self._attr_unique_id = f"{zone_id}_any_warming"

    @property
    def is_on(self) -> Optional[bool]:
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return None
        products = zone.get("products", [])
        return any(
            p.get("isWarming")
            for p in products
            if not p.get("isOffline", True)
        )


class ZoneAnyOverrideBinarySensor(BaseCoordinatorBinarySensor):
    """Zone any override binary sensor."""

    _attr_entity_registry_enabled_default = False
    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Any Override"
        self._attr_unique_id = f"{zone_id}_any_override"

    @property
    def is_on(self) -> Optional[bool]:
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return None
        override = zone.get("override") or {}
        zone_override = any(bool(v) for v in override.values())
        products = zone.get("products", [])
        product_override = any(p.get("isInOverride") for p in products)
        return bool(zone_override or product_override)


class ProductBinarySensor(
    CoordinatorEntity[RadialightCoordinator], BinarySensorEntity
):
    """Base product binary sensor."""

    def __init__(
        self,
        coordinator: RadialightCoordinator,
        zone_id: str,
        zone: dict,
        product: dict,
        key: str,
        label: str,
        device_class: Optional[BinarySensorDeviceClass] = None,
    ) -> None:
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._zone = zone
        self._product_id = product.get("id")
        self._product_name = product.get("name", "Product")
        self._key = key
        self._attr_name = f"{self._product_name} {label}"
        self._attr_unique_id = f"{self._product_id}_{key}"
        if device_class:
            self._attr_device_class = device_class
        if key == "isInOverride":
            self._attr_entity_registry_enabled_default = False

    @property
    def available(self) -> bool:
        product = _get_product(self.coordinator, self._zone_id, self._product_id)
        if not product:
            return False
        return not product.get("isOffline", True)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._product_id)},
            name=self._product_name,
            manufacturer="Radialight",
            model=_get_product_model(self.coordinator, self._zone_id, self._product_id),
            via_device=(DOMAIN, self._zone_id),
        )

    @property
    def is_on(self) -> Optional[bool]:
        product = _get_product(self.coordinator, self._zone_id, self._product_id)
        if product is None:
            return None
        return bool(product.get(self._key))


def _build_zone_binary_sensors(
    coordinator: RadialightCoordinator, zone_id: str, zone: dict
) -> list[BinarySensorEntity]:
    return [
        ZoneAnyWarmingBinarySensor(coordinator, zone_id, zone),
        ZoneAnyOverrideBinarySensor(coordinator, zone_id, zone),
        ZoneOverrideFlagBinarySensor(coordinator, zone_id, zone, "mode", "Mode"),
        ZoneOverrideFlagBinarySensor(coordinator, zone_id, zone, "window", "Window"),
        ZoneOverrideFlagBinarySensor(coordinator, zone_id, zone, "pir", "PIR"),
        ZoneOverrideFlagBinarySensor(coordinator, zone_id, zone, "lock", "Lock"),
        ZoneOverrideFlagBinarySensor(coordinator, zone_id, zone, "tComfort", "Comfort"),
        ZoneOverrideFlagBinarySensor(coordinator, zone_id, zone, "tECO", "Eco"),
    ]


def _build_product_binary_sensors(
    coordinator: RadialightCoordinator,
    zone_id: str,
    zone: dict,
    product: dict,
) -> list[BinarySensorEntity]:
    return [
        ProductBinarySensor(
            coordinator,
            zone_id,
            zone,
            product,
            "isWarming",
            "Warming",
            BinarySensorDeviceClass.HEAT,
        ),
        ProductBinarySensor(
            coordinator,
            zone_id,
            zone,
            product,
            "isOffline",
            "Offline",
            BinarySensorDeviceClass.PROBLEM,
        ),
        ProductBinarySensor(
            coordinator,
            zone_id,
            zone,
            product,
            "isInOverride",
            "In Override",
        ),
        ProductBinarySensor(
            coordinator,
            zone_id,
            zone,
            product,
            "isLedOn",
            "LED",
        ),
    ]


def _get_product(
    coordinator: RadialightCoordinator, zone_id: str, product_id: Optional[str]
) -> Optional[dict]:
    """Get product from coordinator, with fallback to searching zone products."""
    if product_id is None:
        return None
    
    # Try coordinator's products_by_id first (normalized)
    product = coordinator.get_product(product_id)
    if product is not None:
        return product
    
    # Fallback: search in zone products (for compatibility)
    zone = coordinator.get_zone(zone_id)
    if zone is None:
        return None
    for prod in zone.get("products", []):
        if prod.get("id") == product_id:
            return prod
    return None


def _get_product_model(
    coordinator: RadialightCoordinator, zone_id: str, product_id: Optional[str]
) -> str:
    product = _get_product(coordinator, zone_id, product_id)
    if product and product.get("model"):
        return product.get("model")
    return "ICON Product"
