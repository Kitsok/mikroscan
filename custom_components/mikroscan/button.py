"""Button platform for the Mikroscan integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SCAN_RANGE,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)


@dataclass(frozen=True, slots=True)
class MikroscanButtonDescription:
    """Description of one Mikroscan button."""

    key: str
    name: str


BUTTONS = (
    MikroscanButtonDescription(key="scan", name="Refresh Network"),
    MikroscanButtonDescription(key="generate_topology", name="Generate Topology"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mikroscan buttons from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    async_add_entities(
        MikroscanButton(entry, coordinator, client, description)
        for description in BUTTONS
    )


class MikroscanButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Mikroscan action button."""

    entity_description: MikroscanButtonDescription

    def __init__(self, entry: ConfigEntry, coordinator, client, description: MikroscanButtonDescription) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._client = client
        self.entity_description = description
        self._attr_name = f"Mikroscan {description.name}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the Mikroscan service."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Mikroscan",
            manufacturer="Mikroscan",
            model="Local API",
            configuration_url=f"http://{self._entry.data['host']}:{self._entry.data['web_port']}/",
        )

    async def async_press(self) -> None:
        """Trigger the button action."""
        if self.entity_description.key == "scan":
            ip_range = self._entry.options.get(CONF_SCAN_RANGE) or self._entry.data.get(CONF_SCAN_RANGE) or None
            await self._client.async_trigger_scan(ip_range)
        else:
            await self._client.async_generate_topology()

        await self.coordinator.async_request_refresh()
