"""Constants for the WIT 901 WIFI integration."""

from __future__ import annotations

DOMAIN = "wit_901_wifi"
NAME = "WIT 901 WIFI"
VERSION = "0.1.5"

PLATFORMS: tuple[str, ...] = ("sensor", "binary_sensor")

DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 1399
DEFAULT_PROTOCOL = "udp"
DEFAULT_TIMEOUT_SECONDS = 10
MIN_UPDATE_INTERVAL_S = 0.2  # max ~5 state updates per second

CONF_PROTOCOL = "protocol"
CONF_LISTEN_HOST = "listen_host"
CONF_LISTEN_PORT = "listen_port"
CONF_DEVICE_ID = "device_id"
CONF_TIMEOUT_SECONDS = "timeout_seconds"

PROTOCOL_UDP = "udp"
PROTOCOL_TCP = "tcp"
VALID_PROTOCOLS = {PROTOCOL_UDP, PROTOCOL_TCP}

FRAME_LENGTH = 54
FRAME_HEADER = b"WT55"
FRAME_FOOTER = b"\r\n"

BATTERY_THRESHOLDS: tuple[tuple[int, int], ...] = (
    (393, 90),
    (387, 75),
    (382, 60),
    (379, 50),
    (377, 40),
    (373, 30),
    (370, 20),
    (368, 15),
    (350, 10),
    (340, 5),
)
