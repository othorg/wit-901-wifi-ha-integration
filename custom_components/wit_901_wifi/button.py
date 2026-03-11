"""Button platform for WIT 901 WIFI."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    """Set up WIT button entities."""
    coordinator: WitDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([WitRebootButton(coordinator)])


class WitRebootButton(CoordinatorEntity[WitDataCoordinator], ButtonEntity):
    """Button to trigger a sensor reboot."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "reboot"

    def __init__(self, coordinator: WitDataCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_id}_reboot"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=f"WIT {coordinator.device_id}",
            manufacturer="WIT-Motion",
            model="WT901WIFI",
        )

    async def async_press(self) -> None:
        """Reboot the sensor."""
        await self.coordinator.async_reboot()
