"""Sensor platform for Radialight Cloud zones and products."""

from __future__ import annotations

from typing import Any, Optional

from datetime import date, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
import logging

_LOGGER = logging.getLogger(__name__)

from .coordinator import RadialightCoordinator
from .const import (
    DOMAIN,
    DATA_COORDINATOR,
    CONF_ENABLE_PRODUCT_ENTITIES,
    CONF_ENABLE_USAGE_SENSORS,
    CONF_USAGE_SCALE,
    DEFAULT_USAGE_SCALE,
    USAGE_SCALE_RAW,
    USAGE_SCALE_WH,
    USAGE_SCALE_DECIWH,
)


def _wh_to_kwh(wh: float) -> float:
    """Convert Wh (watt-hours) to kWh (kilowatt-hours)."""
    return wh / 1000.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: RadialightCoordinator = data[DATA_COORDINATOR]
    enable_product_entities = data.get(CONF_ENABLE_PRODUCT_ENTITIES, False)
    enable_usage_sensors = data.get(CONF_ENABLE_USAGE_SENSORS, True)
    usage_scale = data.get(CONF_USAGE_SCALE, DEFAULT_USAGE_SCALE)

    entities: list[SensorEntity] = []

    # Add usage sensors (account-level)
    if enable_usage_sensors:
        entities.append(EnergyTotalSensor(coordinator))
        entities.append(UsageLastHourSensor(coordinator))
        entities.append(UsageTodaySensor(coordinator))
        entities.append(UsageYesterdaySensor(coordinator))
        entities.append(UsageRolling24hSensor(coordinator))

    # Add zone sensors
    for zone_id, zone in coordinator.get_zones_by_id().items():
        entities.extend(_build_zone_sensors(coordinator, zone_id, zone))

        if enable_product_entities:
            for product in zone.get("products", []):
                entities.append(
                    ProductTemperatureSensor(
                        coordinator, zone_id, zone, product
                    )
                )

    async_add_entities(entities)


class BaseAccountSensor(CoordinatorEntity[RadialightCoordinator], SensorEntity):
    """Base account-level sensor."""

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "radialight_cloud")},
            name="Radialight Cloud",
            manufacturer="Radialight",
            model="Cloud API",
        )


class EnergyTotalSensor(BaseAccountSensor):
    """Total energy sensor (monotonically increasing, for Energy dashboard)."""

    def __init__(self, coordinator: RadialightCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Radialight Energy Total"
        self._attr_unique_id = "radialight_energy_total"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Energy sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get("energy_total_kwh")
        return round(value, 2) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        last_seen = self.coordinator.data.get("last_seen_usage_timestamp")
        return {
            "last_seen_usage_timestamp": last_seen.isoformat() if last_seen else None,
            "usage_scale": self.coordinator.usage_scale,
        }


class UsageLastHourSensor(BaseAccountSensor):
    """Usage last hour sensor."""

    def __init__(self, coordinator: RadialightCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Radialight Usage Last Hour"
        self._attr_unique_id = "radialight_usage_last_hour"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Usage sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get("usage_last_hour_kwh")
        return round(value, 2) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        usage_points = self.coordinator.data.get("usage_points", [])
        return {
            "point_count": len(usage_points),
            "last_48_hours": _format_last_n_points(usage_points, 48),
        }


class UsageTodaySensor(BaseAccountSensor):
    """Usage today sensor."""

    def __init__(self, coordinator: RadialightCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Radialight Usage Today"
        self._attr_unique_id = "radialight_usage_today"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Usage sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get("usage_today_kwh")
        return round(value, 2) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        usage_points = self.coordinator.data.get("usage_points", [])
        return {
            "point_count": len(usage_points),
            "last_48_hours": _format_last_n_points(usage_points, 48),
        }


class UsageYesterdaySensor(BaseAccountSensor):
    """Usage yesterday sensor."""

    def __init__(self, coordinator: RadialightCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Radialight Usage Yesterday"
        self._attr_unique_id = "radialight_usage_yesterday"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Usage sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get("usage_yesterday_kwh")
        return round(value, 2) if value is not None else None


class UsageRolling24hSensor(BaseAccountSensor):
    """Usage rolling 24h sensor."""

    def __init__(self, coordinator: RadialightCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Radialight Usage Rolling 24h"
        self._attr_unique_id = "radialight_usage_24h"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Usage sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get("usage_rolling_24h_kwh")
        return round(value, 2) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        usage_points = self.coordinator.data.get("usage_points", [])
        return {
            "point_count": len(usage_points),
            "last_48_hours": _format_last_n_points(usage_points, 48),
        }


class BaseCoordinatorSensor(CoordinatorEntity[RadialightCoordinator], SensorEntity):
    """Base coordinator sensor for a Radialight zone."""

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

class ZoneAverageTemperatureSensor(BaseCoordinatorSensor):
    """Zone average temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Average Temperature"
        self._attr_unique_id = f"{zone_id}_avg_temp"

    @property
    def native_value(self) -> Optional[float]:
        return _zone_stat_temperature(self.coordinator, self._zone_id, stat="avg")


class ZoneMinTemperatureSensor(BaseCoordinatorSensor):
    """Zone minimum temperature across online products."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Min Temperature"
        self._attr_unique_id = f"{zone_id}_min_temp"

    @property
    def native_value(self) -> Optional[float]:
        return _zone_stat_temperature(self.coordinator, self._zone_id, stat="min")


class ZoneMaxTemperatureSensor(BaseCoordinatorSensor):
    """Zone maximum temperature across online products."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Max Temperature"
        self._attr_unique_id = f"{zone_id}_max_temp"

    @property
    def native_value(self) -> Optional[float]:
        return _zone_stat_temperature(self.coordinator, self._zone_id, stat="max")


class ZoneOnlineCountSensor(BaseCoordinatorSensor):
    """Zone online product count sensor."""

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Online Products"
        self._attr_unique_id = f"{zone_id}_online_count"

    @property
    def native_value(self) -> Optional[int]:
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return None
        products = zone.get("products", [])
        return len([p for p in products if not p.get("isOffline", True)])


class ZoneOfflineCountSensor(BaseCoordinatorSensor):
    """Zone offline product count sensor."""

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Offline Products"
        self._attr_unique_id = f"{zone_id}_offline_count"

    @property
    def native_value(self) -> Optional[int]:
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return None
        products = zone.get("products", [])
        return len([p for p in products if p.get("isOffline", True)])


class ZoneModeSensor(BaseCoordinatorSensor):
    """Zone mode sensor (raw int)."""

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Mode"
        self._attr_unique_id = f"{zone_id}_mode"

    @property
    def native_value(self) -> Optional[int]:
        zone = self.coordinator.get_zone(self._zone_id)
        return zone.get("mode") if zone else None


class ZoneInfoModeSensor(BaseCoordinatorSensor):
    """Zone info mode sensor (raw int)."""

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Info Mode"
        self._attr_unique_id = f"{zone_id}_info_mode"

    @property
    def native_value(self) -> Optional[int]:
        zone = self.coordinator.get_zone(self._zone_id)
        return zone.get("infoMode") if zone else None


class ZoneWindowSensor(BaseCoordinatorSensor):
    """Zone window setting (raw int)."""

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Window"
        self._attr_unique_id = f"{zone_id}_window"

    @property
    def native_value(self) -> Optional[int]:
        zone = self.coordinator.get_zone(self._zone_id)
        return zone.get("window") if zone else None


class ZonePirSensor(BaseCoordinatorSensor):
    """Zone PIR setting (raw int)."""

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} PIR"
        self._attr_unique_id = f"{zone_id}_pir"

    @property
    def native_value(self) -> Optional[int]:
        zone = self.coordinator.get_zone(self._zone_id)
        return zone.get("pir") if zone else None


class ZoneLockSensor(BaseCoordinatorSensor):
    """Zone lock setting (raw int)."""

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Lock"
        self._attr_unique_id = f"{zone_id}_lock"

    @property
    def native_value(self) -> Optional[int]:
        zone = self.coordinator.get_zone(self._zone_id)
        return zone.get("lock") if zone else None


class ZoneEcoTemperatureSensor(BaseCoordinatorSensor):
    """Zone eco temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Eco Temperature"
        self._attr_unique_id = f"{zone_id}_t_eco"

    @property
    def native_value(self) -> Optional[float]:
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None or zone.get("tECO") is None:
            return None
        return zone.get("tECO") / 10.0


class ZoneComfortTemperatureSensor(BaseCoordinatorSensor):
    """Zone comfort temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Comfort Temperature"
        self._attr_unique_id = f"{zone_id}_t_comfort"

    @property
    def native_value(self) -> Optional[float]:
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None or zone.get("tComfort") is None:
            return None
        return zone.get("tComfort") / 10.0


class ZoneAlertCountSensor(BaseCoordinatorSensor):
    """Zone alert count sensor."""

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Alert Count"
        self._attr_unique_id = f"{zone_id}_alert_count"

    @property
    def native_value(self) -> Optional[int]:
        zone = self.coordinator.get_zone(self._zone_id)
        if zone is None:
            return None
        alerts = zone.get("alert", [])
        return len(alerts) if isinstance(alerts, list) else 0


class ZoneUsageTotalSensor(BaseCoordinatorSensor):
    """Zone total usage for the last week window in kWh (MEASUREMENT state_class)."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Usage Total"
        self._attr_unique_id = f"{zone_id}_usage_total"

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Zone usage sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        usage = _get_last_week_usage(self.coordinator, self._zone_id)
        if not usage:
            return None
        values = usage.get("values", [])
        total = 0.0
        for item in values:
            try:
                # Assume values are in Wh, convert to kWh
                total += _wh_to_kwh(float(item.get("usage", 0)))
            except (TypeError, ValueError):
                continue
        if total <= 0:
            return None
        return round(total, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        usage = _get_last_week_usage(self.coordinator, self._zone_id)
        if not usage:
            return {}
        values = usage.get("values", [])
        # Cap to 48 items max to avoid DB bloat
        capped_values = values[-48:] if len(values) > 48 else values
        return {
            "date_start": usage.get("dateStart"),
            "date_end": usage.get("dateEnd"),
            "values_count": len(values),
            "values": capped_values,
        }


class ZoneUsageTodaySensor(BaseCoordinatorSensor):
    """Zone usage for today in kWh."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Usage Today"
        self._attr_unique_id = f"{zone_id}_usage_today"

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Zone usage sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        value = _get_usage_for_date(self.coordinator, self._zone_id, dt_util.now().date())
        if value is None:
            return None
        # Assume values are in Wh, convert to kWh
        return round(_wh_to_kwh(value), 2)


class ZoneUsageYesterdaySensor(BaseCoordinatorSensor):
    """Zone usage for yesterday in kWh."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Usage Yesterday"
        self._attr_unique_id = f"{zone_id}_usage_yesterday"

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Zone usage sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        yesterday = dt_util.now().date() - timedelta(days=1)
        value = _get_usage_for_date(self.coordinator, self._zone_id, yesterday)
        if value is None:
            return None
        # Assume values are in Wh, convert to kWh
        return round(_wh_to_kwh(value), 2)


class ZoneEnergyTotalSensor(BaseCoordinatorSensor):
    """Zone monotonic total energy sensor (for Energy dashboard)."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Energy Total"
        self._attr_unique_id = f"{zone_id}_energy_total"

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Zone energy sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        if not self.coordinator.data:
            return None
        zone_energy_totals = self.coordinator.data.get("zone_energy_totals", {})
        zone_data = zone_energy_totals.get(self._zone_id)
        if zone_data is None:
            return None
        value = zone_data.get("total_kwh")
        return round(value, 2) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        zone_energy_totals = self.coordinator.data.get("zone_energy_totals", {})
        zone_data = zone_energy_totals.get(self._zone_id)
        if zone_data is None:
            return {}
        last_ts = zone_data.get("last_ts")
        return {
            "last_seen_timestamp": last_ts.isoformat() if isinstance(last_ts, type(dt_util.utcnow())) else last_ts,
        }


class ZoneUsageLast24hSensor(BaseCoordinatorSensor):
    """Zone usage for the last 24 hours (rolling window) in kWh."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RadialightCoordinator, zone_id: str, zone: dict) -> None:
        super().__init__(coordinator, zone_id, zone)
        self._attr_name = f"{zone.get('name', 'Zone')} Usage Last 24h"
        self._attr_unique_id = f"{zone_id}_usage_last_24h"

    async def async_added_to_hass(self) -> None:
        """Log metadata when entity is added."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Zone usage 24h sensor registered: entity_id=%s, unique_id=%s, device_class=%s, unit=%s, state_class=%s",
            self.entity_id,
            self.unique_id,
            self.device_class,
            self.native_unit_of_measurement,
            self.state_class,
        )

    @property
    def native_value(self) -> Optional[float]:
        if not self.coordinator.data:
            return None
        
        zone_usage_rolling_24h = self.coordinator.data.get("zone_usage_rolling_24h_kwh", {}).get(self._zone_id)
        return round(zone_usage_rolling_24h, 2) if zone_usage_rolling_24h is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        
        zone_usage_data = self.coordinator.data.get("usage_by_zone", {}).get(self._zone_id)
        if not zone_usage_data or not zone_usage_data.get("points"):
            return {}
        
        usage_points = zone_usage_data["points"]
        return {
            "point_count": len(usage_points),
            "latest_ts": zone_usage_data.get("latest_ts").isoformat() if zone_usage_data.get("latest_ts") else None,
            "last_48_hours": _format_last_n_points(usage_points, 48),
        }


class ProductTemperatureSensor(CoordinatorEntity[RadialightCoordinator], SensorEntity):
    """Product temperature sensor (optional)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: RadialightCoordinator,
        zone_id: str,
        zone: dict,
        product: dict,
    ) -> None:
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._zone = zone
        self._product_id = product.get("id")
        self._product_name = product.get("name", "Product")
        self._attr_name = f"{self._product_name} Temperature"
        self._attr_unique_id = f"{self._product_id}_temperature"

    @property
    def available(self) -> bool:
        product = _get_product(self.coordinator, self._zone_id, self._product_id)
        if not product:
            return False
        return not product.get("isOffline", True)

    @property
    def device_info(self) -> DeviceInfo:
        zone = self.coordinator.get_zone(self._zone_id) or self._zone
        return DeviceInfo(
            identifiers={(DOMAIN, self._product_id)},
            name=self._product_name,
            manufacturer="Radialight",
            model=_get_product_model(self.coordinator, self._zone_id, self._product_id),
            via_device=(DOMAIN, self._zone_id),
        )

    @property
    def native_value(self) -> Optional[float]:
        product = _get_product(self.coordinator, self._zone_id, self._product_id)
        if product is None:
            return None
        detected = product.get("detectedTemperature")
        if detected is None:
            return None
        return detected / 10.0


def _build_zone_sensors(
    coordinator: RadialightCoordinator, zone_id: str, zone: dict
) -> list[SensorEntity]:
    return [
        ZoneAverageTemperatureSensor(coordinator, zone_id, zone),
        ZoneMinTemperatureSensor(coordinator, zone_id, zone),
        ZoneMaxTemperatureSensor(coordinator, zone_id, zone),
        ZoneOnlineCountSensor(coordinator, zone_id, zone),
        ZoneOfflineCountSensor(coordinator, zone_id, zone),
        ZoneModeSensor(coordinator, zone_id, zone),
        ZoneInfoModeSensor(coordinator, zone_id, zone),
        ZoneWindowSensor(coordinator, zone_id, zone),
        ZonePirSensor(coordinator, zone_id, zone),
        ZoneLockSensor(coordinator, zone_id, zone),
        ZoneEcoTemperatureSensor(coordinator, zone_id, zone),
        ZoneComfortTemperatureSensor(coordinator, zone_id, zone),
        ZoneAlertCountSensor(coordinator, zone_id, zone),
        ZoneEnergyTotalSensor(coordinator, zone_id, zone),
        ZoneUsageLast24hSensor(coordinator, zone_id, zone),
        ZoneUsageTotalSensor(coordinator, zone_id, zone),
        ZoneUsageTodaySensor(coordinator, zone_id, zone),
        ZoneUsageYesterdaySensor(coordinator, zone_id, zone),
    ]


def _zone_stat_temperature(
    coordinator: RadialightCoordinator, zone_id: str, stat: str
) -> Optional[float]:
    zone = coordinator.get_zone(zone_id)
    if zone is None:
        return None
    products = zone.get("products", [])
    temps = [
        p.get("detectedTemperature")
        for p in products
        if not p.get("isOffline", True) and p.get("detectedTemperature") is not None
    ]
    if not temps:
        return None
    if stat == "min":
        return min(temps) / 10.0
    if stat == "max":
        return max(temps) / 10.0
    return (sum(temps) / len(temps)) / 10.0


def _get_last_week_usage(
    coordinator: RadialightCoordinator, zone_id: str
) -> Optional[dict]:
    zone = coordinator.get_zone(zone_id)
    if zone is None:
        return None
    last_week = zone.get("lastWeekUsage")
    if isinstance(last_week, dict):
        return last_week
    return None


def _get_usage_for_date(
    coordinator: RadialightCoordinator, zone_id: str, target: date
) -> Optional[float]:
    """Get usage for a specific date (in local time).
    
    Note: lastWeekUsage dates may be UTC strings; convert to local time before comparing.
    """
    usage = _get_last_week_usage(coordinator, zone_id)
    if not usage:
        return None
    values = usage.get("values", [])
    for item in values:
        date_str = item.get("date")
        if not date_str:
            continue
        # Parse the date string and convert to local time for comparison
        try:
            # Try parsing as ISO datetime first (handles both date and datetime formats)
            dt_obj = dt_util.parse_datetime(date_str)
            if dt_obj:
                # Convert UTC to local timezone
                dt_local = dt_util.as_local(dt_obj)
                if dt_local.date() == target:
                    return float(item.get("usage", 0))
            else:
                # Fallback: try parsing as date string directly
                from datetime import datetime as dt_class
                parsed_date = dt_class.fromisoformat(date_str).date()
                if parsed_date == target:
                    return float(item.get("usage", 0))
        except (ValueError, TypeError):
            continue
    return None


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


def _format_last_n_points(
    points: list[tuple[Any, float]], n: int
) -> list[dict[str, Any]]:
    """Format last N points as dicts for attributes."""
    return [
        {
            "timestamp": dt_obj.isoformat(),
            "usage": usage_val,
        }
        for dt_obj, usage_val in points[-n:]
    ]
