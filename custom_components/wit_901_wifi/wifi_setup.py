"""WiFi provisioning for WT901WIFI sensors via ASCII commands.

Protocol reference: WT901WIFI protocol PDF, section 2.2.1 (ASCII setting format).

Commands are sent as UDP datagrams to the sensor's LOCALPORT (default 9250).
The combined IPWIFI command is used to atomically set WiFi credentials and
streaming target in a single packet, as recommended by the protocol spec.
"""

from __future__ import annotations

import asyncio
import logging
import socket

from .const import PROTOCOL_TCP, PROTOCOL_UDP

_LOGGER = logging.getLogger(__name__)

DEFAULT_SENSOR_PORT = 9250
PROBE_TIMEOUT_S = 3.0


def _build_ipwifi_command(
    wifi_ssid: str,
    wifi_password: str,
    protocol: str,
    target_ip: str,
    target_port: int,
) -> bytes:
    """Build a combined IPWIFI ASCII command.

    Format (UDP): IPWIFI:"<ssid>","<password>";UDP<ip>,<port>\\r\\n
    Format (TCP): IPWIFI:"<ssid>","<password>";TCP<ip>,<port>\\r\\n
    """
    proto_tag = "TCP" if protocol == PROTOCOL_TCP else "UDP"
    cmd = f'IPWIFI:"{wifi_ssid}","{wifi_password}";{proto_tag}{target_ip},{target_port}\r\n'
    return cmd.encode("ascii")


def _build_single_ip_command(
    protocol: str,
    target_ip: str,
    target_port: int,
) -> bytes:
    """Build a standalone IP target command (no WiFi change).

    Format: UDPIP:<ip>,<port>\\r\\n  or  TCPIP:<ip>,<port>\\r\\n
    """
    if protocol == PROTOCOL_TCP:
        cmd = f"TCPIP:{target_ip},{target_port}\r\n"
    else:
        cmd = f"UDPIP:{target_ip},{target_port}\r\n"
    return cmd.encode("ascii")


def _probe_sensor_sync(host: str, port: int) -> bool:
    """Send a zero-byte UDP probe and check socket reachability.

    This does NOT guarantee the sensor will respond; it only confirms
    that the network path allows sending a UDP datagram to the target.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(PROBE_TIMEOUT_S)
            sock.sendto(b"", (host, port))
            return True
    except OSError:
        return False


def _send_udp_command_sync(host: str, port: int, payload: bytes) -> None:
    """Send a single UDP datagram containing an ASCII command."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload, (host, port))


async def async_probe_sensor(
    host: str,
    port: int = DEFAULT_SENSOR_PORT,
    loop: asyncio.AbstractEventLoop | None = None,
) -> bool:
    """Check whether the sensor is reachable via UDP.

    Returns True if a UDP datagram can be sent to host:port without OSError.
    This is a best-effort check — UDP is connectionless, so True does not
    guarantee the sensor is actually listening.
    """
    _loop = loop or asyncio.get_running_loop()
    return await _loop.run_in_executor(None, _probe_sensor_sync, host, port)


async def async_send_ipwifi_command(
    sensor_host: str,
    sensor_port: int,
    wifi_ssid: str,
    wifi_password: str,
    protocol: str,
    target_ip: str,
    target_port: int,
    loop: asyncio.AbstractEventLoop | None = None,
) -> None:
    """Send a combined IPWIFI command to provision the sensor's WiFi and target.

    The sensor will reboot after receiving this command, connect to the
    specified WiFi network, and start streaming to target_ip:target_port.

    Security: wifi_password is used only for building the UDP command payload.
    It is never logged, stored, or returned.
    """
    if protocol not in {PROTOCOL_UDP, PROTOCOL_TCP}:
        raise ValueError(f"Unsupported protocol: {protocol}")

    payload = _build_ipwifi_command(
        wifi_ssid=wifi_ssid,
        wifi_password=wifi_password,
        protocol=protocol,
        target_ip=target_ip,
        target_port=target_port,
    )

    _LOGGER.info(
        "Sending IPWIFI command to %s:%s (target=%s:%s, protocol=%s, ssid=%s)",
        sensor_host,
        sensor_port,
        target_ip,
        target_port,
        protocol,
        wifi_ssid,
        # NOTE: wifi_password intentionally omitted from log
    )

    _loop = loop or asyncio.get_running_loop()
    await _loop.run_in_executor(
        None, _send_udp_command_sync, sensor_host, sensor_port, payload
    )


async def async_send_target_command(
    sensor_host: str,
    sensor_port: int,
    protocol: str,
    target_ip: str,
    target_port: int,
    loop: asyncio.AbstractEventLoop | None = None,
) -> None:
    """Send a standalone IP target command (without changing WiFi).

    Useful for reconfiguring a sensor that is already on the network.
    """
    if protocol not in {PROTOCOL_UDP, PROTOCOL_TCP}:
        raise ValueError(f"Unsupported protocol: {protocol}")

    payload = _build_single_ip_command(
        protocol=protocol,
        target_ip=target_ip,
        target_port=target_port,
    )

    _LOGGER.info(
        "Sending target command to %s:%s (target=%s:%s, protocol=%s)",
        sensor_host,
        sensor_port,
        target_ip,
        target_port,
        protocol,
    )

    _loop = loop or asyncio.get_running_loop()
    await _loop.run_in_executor(
        None, _send_udp_command_sync, sensor_host, sensor_port, payload
    )


async def async_reboot_sensor(
    sensor_host: str,
    sensor_port: int,
    protocol: str,
    target_ip: str,
    target_port: int,
) -> None:
    """Reboot sensor by re-sending its current target config.

    The WT901WIFI reboots on any UDPIP/TCPIP config command,
    even if the values are unchanged.
    """
    _LOGGER.info("Rebooting sensor at %s:%s", sensor_host, sensor_port)
    await async_send_target_command(
        sensor_host=sensor_host,
        sensor_port=sensor_port,
        protocol=protocol,
        target_ip=target_ip,
        target_port=target_port,
    )
