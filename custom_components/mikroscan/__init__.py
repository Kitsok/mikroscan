"""Mikroscan Home Assistant integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .client import MikroscanApiClient
from .const import (
    ATTR_IP_RANGE,
    CONF_SCAN_RANGE,
    CONF_WEB_PORT,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_SCAN_RANGE,
    DEFAULT_WEB_PORT,
    DOMAIN,
    PLATFORMS,
    SERVICE_GENERATE_TOPOLOGY,
    SERVICE_SCAN,
)
from .coordinator import MikroscanDataUpdateCoordinator


SCAN_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_IP_RANGE): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Mikroscan integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mikroscan from a config entry."""
    session = async_get_clientsession(hass)
    client = MikroscanApiClient(
        session=session,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_WEB_PORT],
    )
    coordinator = MikroscanDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    async def async_handle_scan(call: ServiceCall) -> None:
        ip_range = call.data.get(ATTR_IP_RANGE) or entry.options.get(CONF_SCAN_RANGE) or entry.data.get(CONF_SCAN_RANGE) or DEFAULT_SCAN_RANGE
        await client.async_trigger_scan(ip_range or None)
        await coordinator.async_request_refresh()

    async def async_handle_generate_topology(call: ServiceCall) -> None:
        await client.async_generate_topology()
        await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_SCAN):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SCAN,
            async_handle_scan,
            schema=SCAN_SERVICE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_GENERATE_TOPOLOGY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GENERATE_TOPOLOGY,
            async_handle_generate_topology,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    if not hass.data[DOMAIN]:
        for service_name in (SERVICE_SCAN, SERVICE_GENERATE_TOPOLOGY):
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)

    return unload_ok
