"""Tests for wifi_setup module — command building, probe, and send logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.wit_901_wifi.wifi_setup import (
    _build_ipwifi_command,
    _build_single_ip_command,
    _probe_sensor_sync,
    _send_udp_command_sync,
    async_probe_sensor,
    async_send_ipwifi_command,
    async_send_target_command,
)

# --- Command building ---


def test_build_ipwifi_command_udp() -> None:
    cmd = _build_ipwifi_command(
        wifi_ssid="MyNet",
        wifi_password="secret123",
        protocol="udp",
        target_ip="192.168.1.50",
        target_port=1399,
    )
    assert cmd == b'IPWIFI:"MyNet","secret123";UDP192.168.1.50,1399\r\n'


def test_build_ipwifi_command_tcp() -> None:
    cmd = _build_ipwifi_command(
        wifi_ssid="Home WiFi",
        wifi_password="p@ss",
        protocol="tcp",
        target_ip="10.0.0.1",
        target_port=5000,
    )
    assert cmd == b'IPWIFI:"Home WiFi","p@ss";TCP10.0.0.1,5000\r\n'


def test_build_single_ip_command_udp() -> None:
    cmd = _build_single_ip_command(
        protocol="udp",
        target_ip="192.168.1.50",
        target_port=1399,
    )
    assert cmd == b"UDPIP:192.168.1.50,1399\r\n"


def test_build_single_ip_command_tcp() -> None:
    cmd = _build_single_ip_command(
        protocol="tcp",
        target_ip="10.0.0.1",
        target_port=5000,
    )
    assert cmd == b"TCPIP:10.0.0.1,5000\r\n"


def test_ipwifi_command_contains_crlf() -> None:
    cmd = _build_ipwifi_command("s", "p", "udp", "1.2.3.4", 1399)
    assert cmd.endswith(b"\r\n")


def test_ipwifi_command_is_ascii() -> None:
    cmd = _build_ipwifi_command("net", "pass", "udp", "1.2.3.4", 1399)
    cmd.decode("ascii")  # should not raise


def test_password_not_in_log_output() -> None:
    """Verify the password value does not appear in the log format string."""
    # The _build function itself doesn't log, but the async wrapper does.
    # This test ensures the command payload contains the password (necessary)
    # but the module's log call does not.
    import inspect

    import custom_components.wit_901_wifi.wifi_setup as ws

    source = inspect.getsource(ws.async_send_ipwifi_command)
    # The log line should NOT contain wifi_password as a format arg
    assert "wifi_password" not in source.split("_LOGGER.info(")[1].split(")")[0]


# --- Probe ---


def test_probe_sync_success() -> None:
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)
        assert _probe_sensor_sync("192.168.4.1", 9250) is True
        mock_sock.sendto.assert_called_once_with(b"", ("192.168.4.1", 9250))


def test_probe_sync_failure() -> None:
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.sendto.side_effect = OSError("Network unreachable")
        mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)
        assert _probe_sensor_sync("192.168.4.1", 9250) is False


# --- Send ---


def test_send_udp_command_sync() -> None:
    payload = b"UDPIP:1.2.3.4,1399\r\n"
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)
        _send_udp_command_sync("192.168.4.1", 9250, payload)
        mock_sock.sendto.assert_called_once_with(payload, ("192.168.4.1", 9250))


# --- Async wrappers ---


@pytest.mark.asyncio
async def test_async_probe_sensor() -> None:
    with patch(
        "custom_components.wit_901_wifi.wifi_setup._probe_sensor_sync",
        return_value=True,
    ):
        result = await async_probe_sensor("192.168.4.1")
        assert result is True


@pytest.mark.asyncio
async def test_async_send_ipwifi_command() -> None:
    with patch(
        "custom_components.wit_901_wifi.wifi_setup._send_udp_command_sync"
    ) as mock_send:
        await async_send_ipwifi_command(
            sensor_host="192.168.4.1",
            sensor_port=9250,
            wifi_ssid="TestNet",
            wifi_password="TestPass",
            protocol="udp",
            target_ip="192.168.1.50",
            target_port=1399,
        )
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][2]
        assert payload == b'IPWIFI:"TestNet","TestPass";UDP192.168.1.50,1399\r\n'


@pytest.mark.asyncio
async def test_async_send_ipwifi_command_rejects_invalid_protocol() -> None:
    with pytest.raises(ValueError, match="Unsupported protocol"):
        await async_send_ipwifi_command(
            sensor_host="192.168.4.1",
            sensor_port=9250,
            wifi_ssid="X",
            wifi_password="Y",
            protocol="ftp",
            target_ip="1.2.3.4",
            target_port=1399,
        )


@pytest.mark.asyncio
async def test_async_send_target_command() -> None:
    with patch(
        "custom_components.wit_901_wifi.wifi_setup._send_udp_command_sync"
    ) as mock_send:
        await async_send_target_command(
            sensor_host="192.168.1.200",
            sensor_port=9250,
            protocol="tcp",
            target_ip="192.168.1.50",
            target_port=1399,
        )
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][2]
        assert payload == b"TCPIP:192.168.1.50,1399\r\n"


@pytest.mark.asyncio
async def test_async_send_target_command_rejects_invalid_protocol() -> None:
    with pytest.raises(ValueError, match="Unsupported protocol"):
        await async_send_target_command(
            sensor_host="1.2.3.4",
            sensor_port=9250,
            protocol="ws",
            target_ip="1.2.3.4",
            target_port=1399,
        )
