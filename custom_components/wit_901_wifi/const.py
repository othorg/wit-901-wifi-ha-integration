"""Constants for the WIT 901 WIFI integration."""

from __future__ import annotations

DOMAIN = "wit_901_wifi"
NAME = "WIT 901 WIFI"
VERSION = "0.5.2"

PLATFORMS: tuple[str, ...] = ("sensor", "binary_sensor", "button")

DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 1399
DEFAULT_PROTOCOL = "udp"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_SENSOR_PORT = 9250
MIN_UPDATE_INTERVAL_S = 0.2  # max ~5 state updates per second

CONF_UPDATE_INTERVAL = "update_interval"
DEFAULT_UPDATE_INTERVAL = "live"

# Preset keys → throttle interval in seconds
UPDATE_INTERVAL_PRESETS: dict[str, float] = {
    "live": MIN_UPDATE_INTERVAL_S,
    "10s": 10.0,
    "1min": 60.0,
}

CONF_UPDATE_INTERVAL_CUSTOM = "update_interval_custom"

CONF_PROTOCOL = "protocol"
CONF_LISTEN_HOST = "listen_host"
CONF_LISTEN_PORT = "listen_port"
CONF_DEVICE_ID = "device_id"
CONF_TIMEOUT_SECONDS = "timeout_seconds"
CONF_TARGET_IP = "target_ip"

# Auto-reboot configuration
CONF_AUTO_REBOOT_INTERVAL = "auto_reboot_interval"
DEFAULT_AUTO_REBOOT_INTERVAL = "disabled"
CONF_AUTO_REBOOT_CUSTOM = "auto_reboot_custom"
MIN_AUTO_REBOOT_S = 3600  # minimum 1 hour

AUTO_REBOOT_PRESETS: dict[str, int] = {
    "disabled": 0,
    "6h": 21600,
    "12h": 43200,
    "24h": 86400,
}

REBOOT_GRACE_PERIOD_S = 15.0  # suppress offline warning after deliberate reboot

PROTOCOL_UDP = "udp"
PROTOCOL_TCP = "tcp"
VALID_PROTOCOLS = {PROTOCOL_UDP, PROTOCOL_TCP}

FRAME_LENGTH = 54
FRAME_HEADER = b"WT55"
FRAME_FOOTER = b"\r\n"

# MQTT forwarding configuration
CONF_MQTT_ENABLED = "mqtt_enabled"
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"
CONF_MQTT_SENSORS = "mqtt_sensors"
CONF_MQTT_QOS = "mqtt_qos"
CONF_MQTT_INTERVAL = "mqtt_interval"
CONF_MQTT_INTERVAL_CUSTOM = "mqtt_interval_custom"

DEFAULT_MQTT_ENABLED = False
DEFAULT_MQTT_TOPIC_PREFIX = "wit901"
DEFAULT_MQTT_QOS = 0
DEFAULT_MQTT_INTERVAL = "live"
MIN_MQTT_INTERVAL_S = 0.2

MQTT_INTERVAL_PRESETS: dict[str, float] = {
    "live": 0,
    "1s": 1.0,
    "5s": 5.0,
    "10s": 10.0,
    "30s": 30.0,
    "1min": 60.0,
    "5min": 300.0,
    "15min": 900.0,
    "1h": 3600.0,
    "6h": 21600.0,
    "12h": 43200.0,
    "24h": 86400.0,
}

# Forwardable sensor value_keys (from protocol parser) → human label
MQTT_FORWARDABLE_SENSORS: dict[str, str] = {
    "roll_deg": "Roll (°)",
    "pitch_deg": "Pitch (°)",
    "yaw_deg": "Yaw (°)",
    "temperature_c": "Temperature (°C)",
    "battery_voltage_v": "Battery voltage (V)",
    "battery_percentage": "Battery (%)",
    "rssi_dbm": "Signal strength (dBm)",
    "acc_x_g": "Acceleration X (g)",
    "acc_y_g": "Acceleration Y (g)",
    "acc_z_g": "Acceleration Z (g)",
    "gyro_x_dps": "Gyroscope X (°/s)",
    "gyro_y_dps": "Gyroscope Y (°/s)",
    "gyro_z_dps": "Gyroscope Z (°/s)",
    "mag_x_ut": "Magnetometer X (µT)",
    "mag_y_ut": "Magnetometer Y (µT)",
    "mag_z_ut": "Magnetometer Z (µT)",
}

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
