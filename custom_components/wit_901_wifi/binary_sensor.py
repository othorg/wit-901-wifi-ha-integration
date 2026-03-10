"""Binary sensor platform for WIT 901 WIFI."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WitDataCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WIT binary sensor entities."""
    coordinator: WitDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([WitOnlineBinarySensor(coordinator)])


class WitOnlineBinarySensor(CoordinatorEntity[WitDataCoordinator], BinarySensorEntity):
    """Binary sensor indicating whether the WT901WIFI device is online."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "online"

    def __init__(self, coordinator: WitDataCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_id}_online"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=f"WIT {coordinator.device_id}",
            manufacturer="WIT-Motion",
            model="WT901WIFI",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if the device sent data within the timeout window."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("online", False)
