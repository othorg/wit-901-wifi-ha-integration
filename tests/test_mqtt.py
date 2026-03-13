"""Tests for MQTT forwarding functionality."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.wit_901_wifi.const import (
    CONF_DEVICE_ID,
    CONF_MQTT_ENABLED,
    CONF_MQTT_INTERVAL,
    CONF_MQTT_INTERVAL_CUSTOM,
    CONF_MQTT_QOS,
    CONF_MQTT_SENSORS,
    CONF_MQTT_TOPIC_PREFIX,
    DEFAULT_MQTT_ENABLED,
    DEFAULT_MQTT_INTERVAL,
    DEFAULT_MQTT_QOS,
    DEFAULT_MQTT_TOPIC_PREFIX,
    MIN_MQTT_INTERVAL_S,
    MQTT_FORWARDABLE_SENSORS,
    MQTT_INTERVAL_PRESETS,
)
from custom_components.wit_901_wifi.coordinator import WitDataCoordinator


# ---------------------------------------------------------------------------
# _resolve_mqtt_interval
# ---------------------------------------------------------------------------


def test_resolve_mqtt_interval_presets():
    """All preset keys resolve to their expected value."""
    resolve = WitDataCoordinator._resolve_mqtt_interval
    for key, expected in MQTT_INTERVAL_PRESETS.items():
        assert resolve({"mqtt_interval": key}) == expected


def test_resolve_mqtt_interval_custom():
    """Custom value is resolved correctly."""
    result = WitDataCoordinator._resolve_mqtt_interval({
        "mqtt_interval": "custom",
        "mqtt_interval_custom": 42.5,
    })
    assert result == 42.5


def test_resolve_mqtt_interval_custom_minimum():
    """Custom value below minimum is clamped."""
    result = WitDataCoordinator._resolve_mqtt_interval({
        "mqtt_interval": "custom",
        "mqtt_interval_custom": 0.05,
    })
    assert result == MIN_MQTT_INTERVAL_S


def test_resolve_mqtt_interval_default():
    """Missing config defaults to 0 (live)."""
    assert WitDataCoordinator._resolve_mqtt_interval({}) == 0


# ---------------------------------------------------------------------------
# MQTT_FORWARDABLE_SENSORS consistency
# ---------------------------------------------------------------------------


def test_forwardable_sensors_not_empty():
    """Forwardable sensors dict must contain entries."""
    assert len(MQTT_FORWARDABLE_SENSORS) > 0


def test_forwardable_sensors_keys_are_strings():
    """All keys and labels must be strings."""
    for key, label in MQTT_FORWARDABLE_SENSORS.items():
        assert isinstance(key, str), f"Key {key!r} is not a string"
        assert isinstance(label, str), f"Label {label!r} is not a string"


def test_forwardable_sensors_contain_core_values():
    """Core sensor value keys must be present."""
    core_keys = {"roll_deg", "pitch_deg", "yaw_deg", "temperature_c", "battery_percentage"}
    assert core_keys.issubset(MQTT_FORWARDABLE_SENSORS.keys())


# ---------------------------------------------------------------------------
# MQTT interval presets consistency
# ---------------------------------------------------------------------------


def test_mqtt_interval_presets_include_live():
    """'live' preset must exist and map to 0."""
    assert "live" in MQTT_INTERVAL_PRESETS
    assert MQTT_INTERVAL_PRESETS["live"] == 0


def test_mqtt_interval_presets_all_non_negative():
    """All preset values must be >= 0."""
    for key, val in MQTT_INTERVAL_PRESETS.items():
        assert val >= 0, f"Preset {key!r} has negative value {val}"


# ---------------------------------------------------------------------------
# Coordinator MQTT state initialization
# ---------------------------------------------------------------------------


def _make_coordinator(entry_data: dict) -> WitDataCoordinator:
    """Create a coordinator with a mocked hass and given entry_data."""
    base = {CONF_DEVICE_ID: "WT5500001234"}
    base.update(entry_data)
    hass = MagicMock()
    hass.loop = MagicMock()
    with patch.object(WitDataCoordinator, "__init__", lambda self, *a, **kw: None):
        coord = WitDataCoordinator.__new__(WitDataCoordinator)
    # Manually call real __init__ logic for MQTT fields
    coord.hass = hass
    coord.device_id = base[CONF_DEVICE_ID]
    coord._entry_data = base
    coord._mqtt_enabled = base.get(CONF_MQTT_ENABLED, DEFAULT_MQTT_ENABLED)
    coord._mqtt_topic_prefix = base.get(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX)
    coord._mqtt_sensors = base.get(CONF_MQTT_SENSORS, [])
    coord._mqtt_qos = int(base.get(CONF_MQTT_QOS, DEFAULT_MQTT_QOS))
    coord._mqtt_interval_s = WitDataCoordinator._resolve_mqtt_interval(base)
    coord._mqtt_warned = False
    coord._mqtt_publish_task = None
    coord._last_mqtt_publish_mono = 0.0
    return coord


def test_coordinator_mqtt_defaults():
    """Coordinator initializes MQTT state with defaults when not configured."""
    coord = _make_coordinator({})
    assert coord._mqtt_enabled is False
    assert coord._mqtt_topic_prefix == DEFAULT_MQTT_TOPIC_PREFIX
    assert coord._mqtt_sensors == []
    assert coord._mqtt_qos == DEFAULT_MQTT_QOS
    assert coord._mqtt_interval_s == 0  # live


def test_coordinator_mqtt_custom_config():
    """Coordinator picks up MQTT config from entry_data."""
    coord = _make_coordinator({
        CONF_MQTT_ENABLED: True,
        CONF_MQTT_TOPIC_PREFIX: "myprefix",
        CONF_MQTT_SENSORS: ["roll_deg", "pitch_deg"],
        CONF_MQTT_QOS: 2,
        CONF_MQTT_INTERVAL: "5s",
    })
    assert coord._mqtt_enabled is True
    assert coord._mqtt_topic_prefix == "myprefix"
    assert coord._mqtt_sensors == ["roll_deg", "pitch_deg"]
    assert coord._mqtt_qos == 2
    assert coord._mqtt_interval_s == 5.0


# ---------------------------------------------------------------------------
# _async_mqtt_publish
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mqtt_publish_sends_selected_sensors():
    """Publish sends topics for each selected sensor + availability."""
    coord = _make_coordinator({
        CONF_MQTT_ENABLED: True,
        CONF_MQTT_TOPIC_PREFIX: "test",
        CONF_MQTT_SENSORS: ["roll_deg", "temperature_c"],
        CONF_MQTT_QOS: 1,
    })

    mock_publish = AsyncMock()
    mock_mqtt = MagicMock()
    mock_mqtt.async_publish = mock_publish

    parsed = {"roll_deg": 2.15, "temperature_c": 23.4, "pitch_deg": -0.87}

    with patch.dict("sys.modules", {"homeassistant.components.mqtt": mock_mqtt}):
        await coord._async_mqtt_publish(parsed)

    # 2 sensor values + 1 availability = 3 calls
    assert mock_publish.call_count == 3

    calls = mock_publish.call_args_list
    # roll_deg
    assert calls[0].args[1] == "test/WT5500001234/roll_deg"
    assert calls[0].args[2] == "2.15"
    assert calls[0].kwargs["qos"] == 1
    assert calls[0].kwargs["retain"] is True
    # temperature_c
    assert calls[1].args[1] == "test/WT5500001234/temperature_c"
    assert calls[1].args[2] == "23.4"
    # availability
    assert calls[2].args[1] == "test/WT5500001234/availability"
    assert calls[2].args[2] == "online"
    assert calls[2].kwargs["qos"] == 1


@pytest.mark.asyncio
async def test_mqtt_publish_skips_missing_values():
    """Sensors not present in parsed data are silently skipped."""
    coord = _make_coordinator({
        CONF_MQTT_ENABLED: True,
        CONF_MQTT_TOPIC_PREFIX: "t",
        CONF_MQTT_SENSORS: ["roll_deg", "yaw_deg"],
    })

    mock_publish = AsyncMock()
    mock_mqtt = MagicMock()
    mock_mqtt.async_publish = mock_publish

    parsed = {"roll_deg": 1.0}  # yaw_deg not present

    with patch.dict("sys.modules", {"homeassistant.components.mqtt": mock_mqtt}):
        await coord._async_mqtt_publish(parsed)

    # 1 sensor + 1 availability = 2 calls (yaw_deg skipped)
    assert mock_publish.call_count == 2


@pytest.mark.asyncio
async def test_mqtt_publish_no_sensors_still_sends_availability():
    """With no sensors selected, only availability is published."""
    coord = _make_coordinator({
        CONF_MQTT_ENABLED: True,
        CONF_MQTT_TOPIC_PREFIX: "t",
        CONF_MQTT_SENSORS: [],
    })

    mock_publish = AsyncMock()
    mock_mqtt = MagicMock()
    mock_mqtt.async_publish = mock_publish

    parsed = {"roll_deg": 1.0}

    with patch.dict("sys.modules", {"homeassistant.components.mqtt": mock_mqtt}):
        await coord._async_mqtt_publish(parsed)

    assert mock_publish.call_count == 1
    assert "availability" in mock_publish.call_args_list[0].args[1]


@pytest.mark.asyncio
async def test_mqtt_publish_error_warns_once():
    """First publish error logs warning, subsequent ones are silent."""
    coord = _make_coordinator({
        CONF_MQTT_ENABLED: True,
        CONF_MQTT_SENSORS: ["roll_deg"],
    })

    mock_publish = AsyncMock(side_effect=RuntimeError("broker down"))
    mock_mqtt = MagicMock()
    mock_mqtt.async_publish = mock_publish

    parsed = {"roll_deg": 1.0}

    assert coord._mqtt_warned is False

    with patch.dict("sys.modules", {"homeassistant.components.mqtt": mock_mqtt}):
        await coord._async_mqtt_publish(parsed)
        assert coord._mqtt_warned is True

        # Second call should not raise and warned stays True
        await coord._async_mqtt_publish(parsed)
        assert coord._mqtt_warned is True


@pytest.mark.asyncio
async def test_mqtt_publish_availability_offline():
    """Availability publish sends the correct status string."""
    coord = _make_coordinator({
        CONF_MQTT_ENABLED: True,
        CONF_MQTT_TOPIC_PREFIX: "wit",
    })

    mock_publish = AsyncMock()
    mock_mqtt = MagicMock()
    mock_mqtt.async_publish = mock_publish

    with patch.dict("sys.modules", {"homeassistant.components.mqtt": mock_mqtt}):
        await coord._async_mqtt_publish_availability("offline")

    mock_publish.assert_called_once()
    assert mock_publish.call_args.args[1] == "wit/WT5500001234/availability"
    assert mock_publish.call_args.args[2] == "offline"
    assert mock_publish.call_args.kwargs["qos"] == 1
    assert mock_publish.call_args.kwargs["retain"] is True


# ---------------------------------------------------------------------------
# Options flow MQTT step validation
# ---------------------------------------------------------------------------


def test_valid_mqtt_intervals_include_custom():
    """VALID_MQTT_INTERVALS must include 'custom' alongside all presets."""
    from custom_components.wit_901_wifi.config_flow import VALID_MQTT_INTERVALS

    assert "custom" in VALID_MQTT_INTERVALS
    for preset_key in MQTT_INTERVAL_PRESETS:
        assert preset_key in VALID_MQTT_INTERVALS
