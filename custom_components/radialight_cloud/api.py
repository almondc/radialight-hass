"""Radialight Cloud API client with Firebase token refresh."""

import aiohttp
import logging
import re
import time
from typing import Any, Optional

from .const import FIREBASE_TOKEN_URL, RADIALIGHT_BASE_URL

_LOGGER = logging.getLogger(__name__)


class RadialightError(Exception):
    """Base exception for Radialight API errors."""

    def __init__(self, message: str, *, status: Optional[int] = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


_JWT_RE = re.compile(r"eyJ[a-zA-Z0-9_\-]+=*\.[a-zA-Z0-9_\-]+=*\.[a-zA-Z0-9_\-]+=*")


def redact_jwt(value: str) -> str:
    """Redact any JWT-like tokens from a string."""
    return _JWT_RE.sub("<redacted-jwt>", value)


class RadialightAPIClient:
    """Async client for Radialight Cloud API with Firebase token refresh."""

    def __init__(
        self,
        firebase_api_key: str,
        refresh_token: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client.

        Args:
            firebase_api_key: Firebase API key for token endpoint.
            refresh_token: Initial refresh token.
            session: aiohttp ClientSession for making requests.
        """
        self.firebase_api_key = firebase_api_key
        self.refresh_token = refresh_token
        self.session = session

        self.id_token: Optional[str] = None
        self.token_expires_at: float = 0

    async def ensure_token_valid(self) -> str:
        """Ensure a valid ID token is available, refreshing if needed.

        Returns:
            Valid ID token.

        Raises:
            RadialightError: If token refresh fails.
        """
        current_time = time.time()
        # Refresh 60 seconds early to avoid expiry during requests
        if self.id_token and current_time < self.token_expires_at - 60:
            return self.id_token

        # Token missing or about to expire; refresh
        await self._refresh_id_token()
        if not self.id_token:
            raise RadialightError("Token refresh did not return an ID token")
        return self.id_token

    async def _refresh_id_token(self) -> None:
        """Refresh the ID token using the refresh token.

        Raises:
            RadialightError: If refresh fails.
        """
        if not self.refresh_token:
            raise RadialightError("No refresh token available")

        url = f"{FIREBASE_TOKEN_URL}?key={self.firebase_api_key}"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }

        try:
            _LOGGER.debug("Refreshing ID token")
            async with self.session.post(url, data=data) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to refresh token: %d", response.status
                    )
                    raise RadialightError(
                        f"Token refresh failed: {response.status}",
                        status=response.status,
                        retryable=response.status >= 500,
                    )

                result = await response.json()

                self.id_token = result.get("id_token")
                expires_in_raw = result.get("expires_in", 3600)
                try:
                    expires_in = int(expires_in_raw)
                except (TypeError, ValueError):
                    expires_in = 3600
                self.token_expires_at = time.time() + expires_in

                # Capture rotated refresh token if provided
                if "refresh_token" in result:
                    self.refresh_token = result["refresh_token"]

                if not self.id_token:
                    raise RadialightError("Token refresh response missing id_token")

                _LOGGER.debug("ID token refreshed successfully")

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error during token refresh: %s", err)
            raise RadialightError(
                f"Token refresh network error: {err}", retryable=True
            ) from err

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict] = None,
        retry_on_401: bool = True,
    ) -> dict:
        """Make an authenticated request to the Radialight API.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path (e.g., "/zones").
            json: JSON body for POST requests.
            retry_on_401: Whether to retry once on 401.

        Returns:
            Parsed JSON response.

        Raises:
            RadialightError: If request fails.
        """
        url = f"{RADIALIGHT_BASE_URL}{endpoint}"

        token = await self.ensure_token_valid()
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with self.session.request(
                method, url, json=json, headers=headers
            ) as response:
                if response.status == 401 and retry_on_401:
                    # Token may have been revoked or is invalid
                    _LOGGER.debug("Received 401, refreshing token and retrying")
                    await self._refresh_id_token()
                    # Retry once with new token
                    return await self._request(
                        method, endpoint, json=json, retry_on_401=False
                    )

                if response.status != 200:
                    retryable = response.status >= 500 or response.status == 429
                    _LOGGER.debug(
                        "API request failed with status %s (retryable=%s)",
                        response.status,
                        retryable,
                    )
                    raise RadialightError(
                        f"API request failed: {response.status}",
                        status=response.status,
                        retryable=retryable,
                    )

                return await response.json()

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error during API request: %s", err)
            raise RadialightError(
                f"API request network error: {err}", retryable=True
            ) from err

    async def get_zones(self) -> dict:
        """Fetch all zones.

        Returns:
            API response with "zones" key.

        Raises:
            RadialightError: If request fails.
        """
        return await self._request("GET", "/zones")

    async def set_zone_setpoint(
        self,
        zone_id: str,
        program_id: str,
        t_comfort: int,
        t_eco: int,
        window: int,
        mode: int,
        pir: int,
        lock: int,
    ) -> dict:
        """Set zone target temperature and config.

        Args:
            zone_id: Zone ID.
            program_id: Program ID.
            t_comfort: Target comfort temperature (deci-degrees C).
            t_eco: Eco temperature (deci-degrees C).
            window: Window mode.
            mode: Mode value.
            pir: PIR sensor value.
            lock: Lock value.

        Returns:
            Updated zone object.

        Raises:
            RadialightError: If request fails.
        """
        payload = {
            "programId": program_id,
            "tECO": t_eco,
            "window": window,
            "tComfort": t_comfort,
            "mode": mode,
            "pir": pir,
            "lock": lock,
        }
        return await self._request("POST", f"/zone/{zone_id}", json=payload)

    async def clear_override(
        self,
        zone_id: str,
        program_id: str,
        t_comfort: int,
        t_eco: int,
        window: int,
        mode: int,
        pir: int,
        lock: int,
    ) -> dict:
        """Best-effort clear override by posting full zone payload.

        Note: The exact server-side override clearing is not yet confirmed,
        so this re-sends the current configuration to return to program.
        """
        return await self.set_zone_setpoint(
            zone_id,
            program_id,
            t_comfort,
            t_eco,
            window,
            mode,
            pir,
            lock,
        )

    async def get_usage(
        self, period: str = "day", comparison: int = 0
    ) -> dict:
        """Fetch usage data.

        Args:
            period: Period for usage data (e.g. "day", "month").
            comparison: Comparison mode (0 = no comparison).

        Returns:
            API response with "values" and "comparisonValues" keys.

        Raises:
            RadialightError: If request fails.
        """
        endpoint = f"/usage?comparison={comparison}&period={period}"
        return await self._request("GET", endpoint)

    async def async_set_product_light(self, product_id: str, on: bool) -> dict | None:
        """Set product LED state.

        Args:
            product_id: Product ID.
            on: True to turn LED on, False to turn off.

        Returns:
            Updated product object or None on success with no response.

        Raises:
            RadialightError: If request fails (after 401 retry).
        """
        payload = {"light": on}
        return await self._request("POST", f"/product/{product_id}", json=payload)
