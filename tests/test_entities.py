"""Tests for WIT 901 WIFI sensor entity descriptions."""

from __future__ import annotations

import pytest

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import EntityCategory

from custom_components.wit_901_wifi.sensor import SENSOR_DESCRIPTIONS

# Keys of the 10 new sensors added in 0.3.0
NEW_SENSOR_KEYS = {
    "acc_x", "acc_y", "acc_z",
    "gyro_x", "gyro_y", "gyro_z",
    "mag_x", "mag_y", "mag_z",
    "firmware_version",
}

# Map description key → expected value_key in protocol output
VALUE_KEY_MAP = {
    "acc_x": "acc_x_g",
    "acc_y": "acc_y_g",
    "acc_z": "acc_z_g",
    "gyro_x": "gyro_x_dps",
    "gyro_y": "gyro_y_dps",
    "gyro_z": "gyro_z_dps",
    "mag_x": "mag_x_ut",
    "mag_y": "mag_y_ut",
    "mag_z": "mag_z_ut",
    "firmware_version": "version",
}

_DESCRIPTIONS_BY_KEY = {d.key: d for d in SENSOR_DESCRIPTIONS}


def test_all_new_sensors_present():
    """All 10 new sensor descriptions must exist."""
    keys = {d.key for d in SENSOR_DESCRIPTIONS}
    assert NEW_SENSOR_KEYS.issubset(keys), f"Missing: {NEW_SENSOR_KEYS - keys}"


def test_total_sensor_count():
    """7 original + 10 new = 17 sensor descriptions."""
    assert len(SENSOR_DESCRIPTIONS) == 17


@pytest.mark.parametrize("key", sorted(NEW_SENSOR_KEYS))
def test_new_sensors_disabled_by_default(key: str):
    """New sensors must be disabled by default."""
    desc = _DESCRIPTIONS_BY_KEY[key]
    assert desc.entity_registry_enabled_default is False


def test_firmware_entity_category_diagnostic():
    """Firmware version must be EntityCategory.DIAGNOSTIC."""
    desc = _DESCRIPTIONS_BY_KEY["firmware_version"]
    assert desc.entity_category == EntityCategory.DIAGNOSTIC


def test_firmware_no_state_class():
    """Firmware version must not have a state_class."""
    desc = _DESCRIPTIONS_BY_KEY["firmware_version"]
    assert desc.state_class is None


@pytest.mark.parametrize("key", sorted(NEW_SENSOR_KEYS - {"firmware_version"}))
def test_measurement_sensors_have_state_class(key: str):
    """Acceleration, gyroscope, and magnetometer sensors need MEASUREMENT state class."""
    desc = _DESCRIPTIONS_BY_KEY[key]
    assert desc.state_class == SensorStateClass.MEASUREMENT


@pytest.mark.parametrize("key,expected_value_key", sorted(VALUE_KEY_MAP.items()))
def test_value_key_mapping(key: str, expected_value_key: str):
    """value_key must map to the correct protocol output field."""
    desc = _DESCRIPTIONS_BY_KEY[key]
    assert desc.value_key == expected_value_key


def test_firmware_no_unit():
    """Firmware version should have no unit of measurement."""
    desc = _DESCRIPTIONS_BY_KEY["firmware_version"]
    assert desc.native_unit_of_measurement is None
