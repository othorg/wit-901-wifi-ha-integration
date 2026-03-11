"""Tests for reboot functionality."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.wit_901_wifi.coordinator import WitDataCoordinator
from custom_components.wit_901_wifi.wifi_setup import async_reboot_sensor


@pytest.mark.asyncio
async def test_async_reboot_sensor_calls_target_command():
    """async_reboot_sensor delegates to async_send_target_command."""
    with patch(
        "custom_components.wit_901_wifi.wifi_setup.async_send_target_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await async_reboot_sensor(
            sensor_host="192.168.1.200",
            sensor_port=9250,
            protocol="udp",
            target_ip="192.168.1.100",
            target_port=1399,
        )
        mock_send.assert_called_once_with(
            sensor_host="192.168.1.200",
            sensor_port=9250,
            protocol="udp",
            target_ip="192.168.1.100",
            target_port=1399,
        )


def test_resolve_auto_reboot_interval_presets():
    """Preset values are resolved correctly."""
    resolve = WitDataCoordinator._resolve_auto_reboot_interval
    assert resolve({"auto_reboot_interval": "disabled"}) == 0
    assert resolve({"auto_reboot_interval": "6h"}) == 21600
    assert resolve({"auto_reboot_interval": "12h"}) == 43200
    assert resolve({"auto_reboot_interval": "24h"}) == 86400


def test_resolve_auto_reboot_interval_custom():
    """Custom value is resolved with minimum 1h enforcement."""
    result = WitDataCoordinator._resolve_auto_reboot_interval({
        "auto_reboot_interval": "custom",
        "auto_reboot_custom": 7200,
    })
    assert result == 7200


def test_resolve_auto_reboot_interval_custom_minimum():
    """Custom value below minimum is clamped to 3600s."""
    result = WitDataCoordinator._resolve_auto_reboot_interval({
        "auto_reboot_interval": "custom",
        "auto_reboot_custom": 600,
    })
    assert result == 3600


def test_resolve_auto_reboot_interval_default():
    """Missing config defaults to disabled (0)."""
    assert WitDataCoordinator._resolve_auto_reboot_interval({}) == 0
