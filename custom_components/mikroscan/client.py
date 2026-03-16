"""Async client for the local Mikroscan HTTP API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientSession


class MikroscanApiError(Exception):
    """Raised when the local Mikroscan API returns an error."""


@dataclass(slots=True)
class MikroscanApiClient:
    """Small client for the local Mikroscan service."""

    session: ClientSession
    host: str
    port: int

    @property
    def base_url(self) -> str:
        """Return the base URL of the local Mikroscan API."""
        return f"http://{self.host}:{self.port}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        allow_not_found: bool = False,
    ) -> dict[str, Any]:
        """Send one JSON request to the local Mikroscan API."""
        url = f"{self.base_url}{path}"
        try:
            async with self.session.request(method, url, json=payload) as response:
                data = await response.json()
        except ClientError as exc:
            raise MikroscanApiError(str(exc)) from exc

        if response.status == 404 and allow_not_found:
            return {}

        if response.status >= 400:
            raise MikroscanApiError(
                data.get("error")
                or data.get("message")
                or f"request failed with status {response.status}"
            )

        return data

    async def async_get_status(self) -> dict[str, Any]:
        """Return the current Mikroscan status."""
        return await self._request("GET", "/api/status")

    async def async_get_topology(self) -> dict[str, Any]:
        """Return the current structured topology."""
        return await self._request("GET", "/api/topology", allow_not_found=True)

    async def async_trigger_scan(self, ip_range: str | None = None) -> dict[str, Any]:
        """Trigger a background scan or refresh."""
        payload: dict[str, Any] = {}
        if ip_range:
            payload["ip_range"] = ip_range
        return await self._request("POST", "/api/scan", payload=payload)

    async def async_generate_topology(self) -> dict[str, Any]:
        """Trigger topology regeneration."""
        return await self._request("POST", "/api/generate-topology", payload={})
