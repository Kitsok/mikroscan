"""HTTP views for the Mikroscan Home Assistant integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DATA_CLIENT, DOMAIN, FRONTEND_CARD_URL

FRONTEND_FILE = Path(__file__).resolve().parent / "frontend" / "mikroscan-card.js"


async def async_register_static(hass: HomeAssistant) -> None:
    """Register static frontend assets for the Mikroscan dashboard card."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_CARD_URL, str(FRONTEND_FILE), cache_headers=False)]
    )


def _get_client(hass: HomeAssistant):
    """Return the Mikroscan API client for the configured entry."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise web.HTTPServiceUnavailable(text="Mikroscan is not configured")

    entry_data = next(iter(entries.values()))
    return entry_data[DATA_CLIENT]


class MikroscanTopologyView(HomeAssistantView):
    """Proxy topology data from the local Mikroscan service."""

    url = "/api/mikroscan/topology"
    name = "api:mikroscan:topology"
    requires_auth = True

    async def get(self, request):
        client = _get_client(request.app["hass"])
        return web.json_response(await client.async_get_topology())


class MikroscanStatusView(HomeAssistantView):
    """Proxy status data from the local Mikroscan service."""

    url = "/api/mikroscan/status"
    name = "api:mikroscan:status"
    requires_auth = True

    async def get(self, request):
        client = _get_client(request.app["hass"])
        return web.json_response(await client.async_get_status())


class MikroscanLayoutView(HomeAssistantView):
    """Proxy persisted layout data from the local Mikroscan service."""

    url = "/api/mikroscan/layout"
    name = "api:mikroscan:layout"
    requires_auth = True

    async def get(self, request):
        client = _get_client(request.app["hass"])
        return web.json_response(await client.async_get_layout())

    async def post(self, request):
        client = _get_client(request.app["hass"])
        payload: dict[str, Any] = await request.json()
        positions = payload.get("positions", {})
        return web.json_response(await client.async_save_layout(positions))


async def async_register_views(hass: HomeAssistant) -> None:
    """Register Mikroscan HTTP proxy views."""
    hass.http.register_view(MikroscanTopologyView)
    hass.http.register_view(MikroscanStatusView)
    hass.http.register_view(MikroscanLayoutView)
