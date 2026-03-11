"""Sensor platform for WIT 901 WIFI."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WitDataCoordinator

# Units not available as HA constants
UNIT_G = "g"
UNIT_DPS = "°/s"
UNIT_MICROTESLA = "µT"


@dataclass(frozen=True, kw_only=True)
class WitSensorEntityDescription(SensorEntityDescription):
    """Describe a WIT sensor entity."""

    value_key: str


SENSOR_DESCRIPTIONS: tuple[WitSensorEntityDescription, ...] = (
    WitSensorEntityDescription(
        key="roll",
        translation_key="roll",
        value_key="roll_deg",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WitSensorEntityDescription(
        key="pitch",
        translation_key="pitch",
        value_key="pitch_deg",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WitSensorEntityDescription(
        key="yaw",
        translation_key="yaw",
        value_key="yaw_deg",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WitSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        value_key="temperature_c",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WitSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        value_key="battery_voltage_v",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WitSensorEntityDescription(
        key="battery_percentage",
        translation_key="battery_percentage",
        value_key="battery_percentage",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WitSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        value_key="rssi_dbm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # --- Acceleration (disabled by default) ---
    WitSensorEntityDescription(
        key="acc_x",
        translation_key="acc_x",
        value_key="acc_x_g",
        native_unit_of_measurement=UNIT_G,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    WitSensorEntityDescription(
        key="acc_y",
        translation_key="acc_y",
        value_key="acc_y_g",
        native_unit_of_measurement=UNIT_G,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    WitSensorEntityDescription(
        key="acc_z",
        translation_key="acc_z",
        value_key="acc_z_g",
        native_unit_of_measurement=UNIT_G,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    # --- Gyroscope (disabled by default) ---
    WitSensorEntityDescription(
        key="gyro_x",
        translation_key="gyro_x",
        value_key="gyro_x_dps",
        native_unit_of_measurement=UNIT_DPS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    WitSensorEntityDescription(
        key="gyro_y",
        translation_key="gyro_y",
        value_key="gyro_y_dps",
        native_unit_of_measurement=UNIT_DPS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    WitSensorEntityDescription(
        key="gyro_z",
        translation_key="gyro_z",
        value_key="gyro_z_dps",
        native_unit_of_measurement=UNIT_DPS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    # --- Magnetometer (disabled by default) ---
    WitSensorEntityDescription(
        key="mag_x",
        translation_key="mag_x",
        value_key="mag_x_ut",
        native_unit_of_measurement=UNIT_MICROTESLA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    WitSensorEntityDescription(
        key="mag_y",
        translation_key="mag_y",
        value_key="mag_y_ut",
        native_unit_of_measurement=UNIT_MICROTESLA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    WitSensorEntityDescription(
        key="mag_z",
        translation_key="mag_z",
        value_key="mag_z_ut",
        native_unit_of_measurement=UNIT_MICROTESLA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    # --- Firmware version (diagnostic, disabled by default) ---
    WitSensorEntityDescription(
        key="firmware_version",
        translation_key="firmware_version",
        value_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WIT sensor entities."""
    coordinator: WitDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        WitSensorEntity(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class WitSensorEntity(CoordinatorEntity[WitDataCoordinator], SensorEntity):
    """A WIT 901 WIFI sensor entity."""

    entity_description: WitSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WitDataCoordinator,
        description: WitSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=f"WIT {coordinator.device_id}",
            manufacturer="WIT-Motion",
            model="WT901WIFI",
        )

    @property
    def available(self) -> bool:
        """Mark sensor as unavailable when device is offline."""
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.get("online", False)

    @property
    def native_value(self) -> float | None:
        """Return the sensor value from the latest frame."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.value_key)
