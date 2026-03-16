"""Data update coordinator for the Mikroscan integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import MikroscanApiClient, MikroscanApiError
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL


LOGGER = logging.getLogger(__name__)


class MikroscanDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate status and topology polling from the local Mikroscan API."""

    def __init__(self, hass: HomeAssistant, client: MikroscanApiClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest status and topology model."""
        try:
            status = await self.client.async_get_status()
            topology = await self.client.async_get_topology()
        except MikroscanApiError as exc:
            raise UpdateFailed(str(exc)) from exc

        return {
            "status": status,
            "topology": topology,
        }
