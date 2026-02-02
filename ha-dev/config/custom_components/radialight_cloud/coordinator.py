"""Data update coordinator for Radialight Cloud zones."""

import logging
import asyncio
import random
import time
from typing import Any, Dict, Optional, List, Tuple
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import RadialightAPIClient, RadialightError
from .const import (
    LOG_RATE_LIMIT_SECONDS,
    POLL_JITTER_SECONDS,
    USAGE_SCALE_RAW,
    USAGE_SCALE_WH,
    USAGE_SCALE_DECIWH,
)

_LOGGER = logging.getLogger(__name__)


class RadialightCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Radialight zone data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: RadialightAPIClient,
        polling_interval: int,
        usage_scale: str = USAGE_SCALE_DECIWH,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            api: Radialight API client.
            polling_interval: Polling interval in seconds.
            usage_scale: Usage scaling mode (raw, wh, or deciwh).
        """
        super().__init__(
            hass,
            _LOGGER,
            name="Radialight Cloud",
            update_interval=timedelta(seconds=polling_interval),
        )
        self.api = api
        self.usage_scale = usage_scale
        self._last_failure_log: float = 0
        self._store = Store(hass, version=1, key="radialight_energy_total")
        self._accumulated_total_kwh: float = 0.0
        self._last_seen_usage_timestamp: Optional[datetime] = None

    async def async_load_energy_storage(self) -> None:
        """Load persisted energy total from storage."""
        try:
            data = await self._store.async_load()
            if data:
                self._accumulated_total_kwh = data.get("accumulated_total_kwh", 0.0)
                last_seen_str = data.get("last_seen_usage_timestamp_utc")
                if last_seen_str:
                    self._last_seen_usage_timestamp = datetime.fromisoformat(last_seen_str)
                _LOGGER.debug(
                    "Loaded energy storage: total=%.3f kWh, last_seen=%s",
                    self._accumulated_total_kwh,
                    self._last_seen_usage_timestamp,
                )
        except Exception as err:
            _LOGGER.warning("Failed to load energy storage, starting fresh: %s", err)
            self._accumulated_total_kwh = 0.0
            self._last_seen_usage_timestamp = None

    async def _async_save_energy_storage(self) -> None:
        """Save energy total to storage."""
        try:
            await self._store.async_save(
                {
                    "accumulated_total_kwh": self._accumulated_total_kwh,
                    "last_seen_usage_timestamp_utc": (
                        self._last_seen_usage_timestamp.isoformat()
                        if self._last_seen_usage_timestamp
                        else None
                    ),
                }
            )
        except Exception as err:
            _LOGGER.error("Failed to save energy storage: %s", err)

    def _convert_usage_to_kwh(self, raw_value: float) -> float:
        """Convert raw usage value to kWh based on usage_scale.
        
        Args:
            raw_value: Raw usage value from API.
            
        Returns:
            Energy in kWh.
        """
        if self.usage_scale == USAGE_SCALE_RAW:
            # Treat raw as already kWh (unusual, but possible)
            return raw_value
        elif self.usage_scale == USAGE_SCALE_WH:
            # API values are Wh
            return raw_value / 1000.0
        else:  # USAGE_SCALE_DECIWH (default)
            # API values are 0.1 Wh (deci-Wh)
            return (raw_value * 10.0) / 1000.0

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the API.

        Returns:
            Dictionary with zones, usage, and computed stats.

        Raises:
            UpdateFailed: If zones fetch fails.
        """
        start_time = time.monotonic()
        await self._jitter_sleep()

        zones_data = None
        zones_by_id = {}
        products_by_id = {}
        products_by_zone = {}
        usage_data = None
        usage_points: List[Tuple[Any, float]] = []

        # Fetch zones with retries
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self.api.get_zones()
                zones = response.get("zones", [])
                zones_by_id = {zone["id"]: zone for zone in zones}
                zones_data = response

                # Normalize products: extract from zones and organize
                for zone_id, zone in zones_by_id.items():
                    products_by_zone[zone_id] = []
                    for product in zone.get("products", []):
                        product_id = product.get("id")
                        if product_id:
                            # Ensure zoneId and zoneName are in product
                            product_copy = dict(product)
                            product_copy["zoneId"] = zone_id
                            product_copy["zoneName"] = zone.get("name", f"Zone {zone_id}")
                            products_by_id[product_id] = product_copy
                            products_by_zone[zone_id].append(product_copy)

                _LOGGER.debug(
                    "Successfully fetched zones in %.2fs: %s (%d products)",
                    time.monotonic() - start_time,
                    list(zones_by_id.keys()),
                    len(products_by_id),
                )
                break

            except RadialightError as err:
                if err.retryable and attempt < 3:
                    await self._backoff_sleep(attempt)
                    continue
                self._rate_limited_error(
                    "Failed to fetch Radialight zones: %s", err
                )
                raise UpdateFailed(f"Failed to fetch Radialight zones: {err}") from err
            except TimeoutError as err:
                if attempt < 3:
                    await self._backoff_sleep(attempt)
                    continue
                self._rate_limited_error("Timeout fetching Radialight zones")
                raise UpdateFailed("Timeout fetching Radialight zones") from err
            except Exception as err:
                self._rate_limited_error("Unexpected error fetching zones: %s", err)
                raise UpdateFailed(f"Unexpected error: {err}") from err

        # Fetch usage (graceful failure; do not raise if this fails)
        try:
            usage_data = await self.api.get_usage(period="day", comparison=0)
            usage_points = _parse_usage_points(usage_data)
            _LOGGER.debug(
                "Successfully fetched usage; %d points", len(usage_points)
            )
            
            # Process new usage points to update energy total
            await self._process_new_usage_points(usage_points)
            
        except RadialightError as err:
            self._rate_limited_error(
                "Failed to fetch usage data (zones still available): %s", err
            )

        # Calculate usage statistics in kWh
        usage_last_hour_kwh = None
        usage_today_kwh = None
        usage_yesterday_kwh = None
        usage_rolling_24h_kwh = None
        
        if usage_points:
            # Last hour (most recent point)
            usage_last_hour_kwh = self._convert_usage_to_kwh(usage_points[-1][1])
            
            # Today (sum from midnight local time)
            usage_today_raw = _compute_usage_today(usage_points)
            usage_today_kwh = self._convert_usage_to_kwh(usage_today_raw) if usage_today_raw else None
            
            # Yesterday (sum from yesterday's midnight to today's midnight)
            usage_yesterday_raw = _compute_usage_yesterday(usage_points)
            usage_yesterday_kwh = self._convert_usage_to_kwh(usage_yesterday_raw) if usage_yesterday_raw else None
            
            # Rolling 24h
            usage_24h_raw = _compute_usage_rolling(usage_points, hours=24)
            usage_rolling_24h_kwh = self._convert_usage_to_kwh(usage_24h_raw) if usage_24h_raw else None

        return {
            "zones_by_id": zones_by_id,
            "zones": zones_data,
            "products_by_id": products_by_id,
            "products_by_zone": products_by_zone,
            "usage": usage_data or {},
            "usage_points": usage_points,
            "energy_total_kwh": self._accumulated_total_kwh,
            "usage_last_hour_kwh": usage_last_hour_kwh,
            "usage_today_kwh": usage_today_kwh,
            "usage_yesterday_kwh": usage_yesterday_kwh,
            "usage_rolling_24h_kwh": usage_rolling_24h_kwh,
            "last_seen_usage_timestamp": self._last_seen_usage_timestamp,
        }

    async def _process_new_usage_points(
        self, usage_points: List[Tuple[datetime, float]]
    ) -> None:
        """Process new usage points and update accumulated energy total.
        
        Args:
            usage_points: List of (timestamp, raw_usage) tuples.
        """
        if not usage_points:
            return
        
        # If first run (no last_seen timestamp), initialize
        if self._last_seen_usage_timestamp is None:
            # Start tracking from the newest timestamp without adding to total
            self._last_seen_usage_timestamp = usage_points[-1][0]
            _LOGGER.info(
                "Initializing energy tracking at %s with total=%.3f kWh",
                self._last_seen_usage_timestamp,
                self._accumulated_total_kwh,
            )
            await self._async_save_energy_storage()
            return
        
        # Find new points (timestamps after last_seen)
        new_points = [
            (ts, raw_val)
            for ts, raw_val in usage_points
            if ts > self._last_seen_usage_timestamp
        ]
        
        if not new_points:
            _LOGGER.debug("No new usage points to process")
            return
        
        # Add new energy to total
        energy_added = 0.0
        for ts, raw_val in new_points:
            kwh = self._convert_usage_to_kwh(raw_val)
            energy_added += kwh
        
        old_total = self._accumulated_total_kwh
        self._accumulated_total_kwh += energy_added
        
        # Safety: never decrease total (clamp)
        if self._accumulated_total_kwh < old_total:
            _LOGGER.warning(
                "Energy total would decrease (%.3f -> %.3f), clamping to previous",
                old_total,
                self._accumulated_total_kwh,
            )
            self._accumulated_total_kwh = old_total
        
        # Update last seen timestamp to newest point
        self._last_seen_usage_timestamp = new_points[-1][0]
        
        _LOGGER.debug(
            "Processed %d new usage points, added %.3f kWh, total now %.3f kWh",
            len(new_points),
            energy_added,
            self._accumulated_total_kwh,
        )
        
        # Save to storage
        await self._async_save_energy_storage()

    async def _jitter_sleep(self) -> None:
        """Sleep a small random jitter to avoid stampedes."""
        jitter = random.uniform(0, POLL_JITTER_SECONDS)
        if jitter > 0:
            await asyncio.sleep(jitter)

    async def _backoff_sleep(self, attempt: int) -> None:
        """Exponential backoff with jitter for transient failures."""
        base = min(2 ** (attempt - 1), 10)
        delay = base + random.uniform(0, 1)
        await asyncio.sleep(delay)

    def _rate_limited_error(self, message: str, *args: Any) -> None:
        """Log errors with rate limiting to avoid spam."""
        now = time.monotonic()
        if now - self._last_failure_log >= LOG_RATE_LIMIT_SECONDS:
            _LOGGER.error(message, *args)
            self._last_failure_log = now

    def get_zones_by_id(self) -> Dict[str, Any]:
        """Get zones organized by ID.

        Returns:
            Dictionary mapping zone_id to zone data.
        """
        if self.data is None:
            return {}
        return self.data.get("zones_by_id", {})

    def get_zone(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific zone by ID.

        Args:
            zone_id: The zone ID.

        Returns:
            Zone data or None if not found.
        """
        zones = self.get_zones_by_id()
        return zones.get(zone_id)

    def get_products_by_id(self) -> Dict[str, Any]:
        """Get products organized by ID.

        Returns:
            Dictionary mapping product_id to product data (with zoneId/zoneName).
        """
        if self.data is None:
            return {}
        return self.data.get("products_by_id", {})

    def get_products_by_zone(self) -> Dict[str, list[Dict[str, Any]]]:
        """Get products organized by zone.

        Returns:
            Dictionary mapping zone_id to list of products in that zone.
        """
        if self.data is None:
            return {}
        return self.data.get("products_by_zone", {})

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific product by ID.

        Args:
            product_id: The product ID.

        Returns:
            Product data or None if not found.
        """
        products = self.get_products_by_id()
        return products.get(product_id)


def _parse_usage_points(usage_data: dict) -> List[Tuple[Any, float]]:
    """Parse usage data into sorted (datetime_utc, usage_float) tuples."""
    points = []
    values = usage_data.get("values", [])
    for item in values:
        try:
            date_str = item.get("date")
            usage_val = item.get("usage", 0)
            if date_str:
                # Parse ISO8601 string to aware datetime (UTC)
                dt_obj = dt_util.parse_datetime(date_str)
                if dt_obj:
                    points.append((dt_obj, float(usage_val)))
        except (ValueError, TypeError):
            continue
    points.sort(key=lambda x: x[0])
    return points


def _compute_usage_today(points: List[Tuple[Any, float]]) -> Optional[float]:
    """Sum usage for today (in local time).
    
    Note: API returns UTC timestamps; must convert to local time before comparing dates.
    """
    if not points:
        return None
    today = dt_util.now().date()
    total = 0.0
    for dt_utc, usage_val in points:
        # Convert UTC datetime to local timezone for date comparison
        dt_local = dt_util.as_local(dt_utc)
        if dt_local.date() == today:
            total += usage_val
    return total if total > 0 else None


def _compute_usage_yesterday(points: List[Tuple[Any, float]]) -> Optional[float]:
    """Sum usage for yesterday (in local time).
    
    Note: API returns UTC timestamps; must convert to local time before comparing dates.
    """
    if not points:
        return None
    yesterday = (dt_util.now() - timedelta(days=1)).date()
    total = 0.0
    for dt_utc, usage_val in points:
        # Convert UTC datetime to local timezone for date comparison
        dt_local = dt_util.as_local(dt_utc)
        if dt_local.date() == yesterday:
            total += usage_val
    return total if total > 0 else None


def _compute_usage_rolling(
    points: List[Tuple[Any, float]], hours: int = 24
) -> Optional[float]:
    """Sum usage for the last N hours."""
    if not points:
        return None
    now = dt_util.now()
    cutoff = now - timedelta(hours=hours)
    total = 0.0
    for dt_obj, usage_val in points:
        if dt_obj >= cutoff:
            total += usage_val
    return total if total > 0 else None
