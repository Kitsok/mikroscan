"""Sensor platform for the Mikroscan integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_WEB_PORT, DATA_COORDINATOR, DOMAIN


@dataclass(frozen=True, slots=True)
class MikroscanSensorDescription:
    """Description of one Mikroscan sensor."""

    key: str
    name: str
    extractor: Any
    device_class: SensorDeviceClass | None = None
    entity_category: EntityCategory | None = None


SENSORS = (
    MikroscanSensorDescription(
        key="node_count",
        name="Topology Nodes",
        extractor=lambda data: data["status"].get("topology", {}).get("node_count"),
    ),
    MikroscanSensorDescription(
        key="edge_count",
        name="Topology Edges",
        extractor=lambda data: data["status"].get("topology", {}).get("edge_count"),
    ),
    MikroscanSensorDescription(
        key="root_count",
        name="Topology Roots",
        extractor=lambda data: data["status"].get("topology", {}).get("root_count"),
    ),
    MikroscanSensorDescription(
        key="unresolved_host_count",
        name="Unresolved Hosts",
        extractor=lambda data: data["status"].get("topology", {}).get("unresolved_host_count"),
    ),
    MikroscanSensorDescription(
        key="device_count",
        name="Mapped Devices",
        extractor=lambda data: data["status"].get("last_result", {}).get("device_count"),
    ),
    MikroscanSensorDescription(
        key="host_count",
        name="Mapped Hosts",
        extractor=lambda data: data["status"].get("last_result", {}).get("host_count"),
    ),
    MikroscanSensorDescription(
        key="connection_count",
        name="Mapped Connections",
        extractor=lambda data: data["status"].get("last_result", {}).get("connection_count"),
    ),
    MikroscanSensorDescription(
        key="last_action",
        name="Last Action",
        extractor=lambda data: data["status"].get("last_action"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MikroscanSensorDescription(
        key="current_action",
        name="Current Action",
        extractor=lambda data: data["status"].get("current_action"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MikroscanSensorDescription(
        key="last_started_at",
        name="Last Started",
        extractor=lambda data: data["status"].get("last_started_at"),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MikroscanSensorDescription(
        key="last_finished_at",
        name="Last Finished",
        extractor=lambda data: data["status"].get("last_finished_at"),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mikroscan sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        MikroscanSensor(entry, coordinator, description) for description in SENSORS
    )


class MikroscanSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Mikroscan sensor."""

    entity_description: MikroscanSensorDescription

    def __init__(self, entry: ConfigEntry, coordinator, description: MikroscanSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_name = f"Mikroscan {description.name}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_entity_category = description.entity_category

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the Mikroscan service."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Mikroscan",
            manufacturer="Mikroscan",
            model="Local API",
            configuration_url=f"http://{self._entry.data['host']}:{self._entry.data[CONF_WEB_PORT]}/",
        )

    @property
    def native_value(self):
        """Return the current sensor value."""
        value = self.entity_description.extractor(self.coordinator.data)
        if value in ("", None):
            return None

        if self.entity_description.device_class is SensorDeviceClass.TIMESTAMP:
            return dt_util.parse_datetime(value)

        return value
