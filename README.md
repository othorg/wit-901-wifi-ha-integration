# WIT 901 WIFI – Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom integration for **WIT-Motion WT901WIFI** 9-axis IMU sensors.

The sensor streams data via WiFi (UDP or TCP) directly to Home Assistant – no cloud, no polling.

## Features

- **Local Push** – HA listens on a configurable port, the sensor pushes frames
- **Sensors**: Roll, Pitch, Yaw, Temperature, Battery Voltage, Battery Percentage, Signal Strength (RSSI)
- **Online status** as Binary Sensor (Connectivity)
- **WiFi provisioning** directly from the HA UI or via CLI tool
- **Config Flow** with automatic device ID detection
- **Options Flow** to change all listener parameters at runtime
- **UDP and TCP** protocol support
- **Diagnostics** support for debugging
- **HACS compatible**
- **English and German** translations

## Installation

### HACS (recommended)

1. In HACS go to **Integrations** → **Custom repositories**
2. Add repository URL: `https://github.com/othorg/wit-901-wifi-ha-integration`
3. Category: **Integration**
4. Install **WIT 901 WIFI** and restart HA

### Manual

1. Copy `custom_components/wit_901_wifi/` to your HA `config/custom_components/` directory
2. Restart HA

## Sensor Setup

### Prerequisites

- WT901WIFI sensor (WIT-Motion)
- 2.4 GHz WiFi network (the sensor does not support 5 GHz)
- The IP address of your HA server

### Step 1: Connect the sensor to your WiFi

The sensor starts in **AP mode** (its own WiFi network). It must first be provisioned onto your home network.

#### Option A: Via the HA Config Flow

1. **Settings** → **Devices & Services** → **Add Integration** → **WIT 901 WIFI**
2. Configure the listener (port, protocol, host)
3. Choose **Set up sensor** (instead of skip)
4. Enter WiFi SSID, password, sensor IP (default: `192.168.4.1`) and target IP (your HA server)
5. The sensor reboots, connects to WiFi and starts streaming
6. The device ID is detected automatically

#### Option B: Via the CLI tool

First connect to the sensor's AP (SSID e.g. `WT901WiFi_XXXX`), then:

```bash
python tools/configure_sensor.py \
  --ssid "MyWiFi" --password "MyPassword" \
  --target-ip 192.168.1.100 --target-port 1399 --protocol udp
```

Then switch back to your home network and verify:

```bash
python tools/configure_sensor.py --discover --discover-port 1399
```

> **Tip**: If your machine is connected via Ethernet to the same network, you only need to switch WiFi – Ethernet stays connected.

### Step 2: Configure the integration in HA

If not already done via the Config Flow:

1. **Settings** → **Devices & Services** → **Add Integration** → **WIT 901 WIFI**
2. Protocol: `udp` (recommended)
3. Listen host: `0.0.0.0` (all interfaces)
4. Listen port: `1399` (must match the sensor's target port)
5. The device ID is automatically detected from the first received frame

## CLI Tool (`tools/configure_sensor.py`)

Standalone tool for sensor configuration, independent of Home Assistant.

```bash
# Full provisioning (WiFi + streaming target)
python tools/configure_sensor.py \
  --ssid "MyWiFi" --password "MyPassword" \
  --target-ip 192.168.1.100 --target-port 1399 --protocol udp

# Probe only: check if sensor is reachable
python tools/configure_sensor.py --probe-only

# Listen for frames and display device info
python tools/configure_sensor.py --discover --discover-port 1399

# Change streaming target only (sensor already on network)
python tools/configure_sensor.py \
  --sensor-host 192.168.1.200 \
  --target-ip 192.168.1.100 --target-port 1399 --protocol udp \
  --target-only

# Switch sensor back to AP mode
python tools/configure_sensor.py --ap-mode
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--sensor-host` | `192.168.4.1` | Sensor IP (AP mode) |
| `--sensor-port` | `9250` | Sensor LOCALPORT |
| `--ssid` | – | WiFi SSID (2.4 GHz) |
| `--password` | – | WiFi password |
| `--target-ip` | – | Target IP (your HA server) |
| `--target-port` | `1399` | Target port |
| `--protocol` | `udp` | `udp` or `tcp` |

## HA Service: `wit_901_wifi.configure_sensor`

The integration registers a service for WiFi provisioning, callable via **Developer Tools** → **Services**:

```yaml
service: wit_901_wifi.configure_sensor
data:
  sensor_host: "192.168.4.1"
  sensor_port: 9250
  wifi_ssid: "MyWiFi"
  wifi_password: "MyPassword"
  protocol: "udp"
  target_ip: "192.168.1.100"
  target_port: 1399
```

> **Security**: The WiFi password is used exclusively for the UDP command payload and is never stored or logged.

## Entities

After successful setup, the following entities are created:

| Entity | Type | Unit | Description |
|--------|------|------|-------------|
| Roll | Sensor | ° | Roll angle |
| Pitch | Sensor | ° | Pitch angle |
| Yaw | Sensor | ° | Yaw angle |
| Temperature | Sensor | °C | Sensor temperature |
| Battery voltage | Sensor | V | Battery level in volts |
| Battery percentage | Sensor | % | Estimated charge level |
| Signal strength | Sensor | dBm | WiFi RSSI |
| Online | Binary Sensor | – | Connection status |

## Architecture

```
WT901WIFI Sensor  ──UDP/TCP──►  HA Listener (Port 1399)
                                     │
                                     ▼
                               WitListener (asyncio)
                                     │
                                     ▼
                              parse_streaming_frame()
                                     │
                                     ▼
                             WitDataCoordinator
                              (push, no polling)
                                     │
                                     ▼
                              Sensor Entities
```

- **`protocol.py`** – Parser for 54-byte WT55 frames
- **`listener.py`** – UDP/TCP asyncio listener with device ID filtering
- **`coordinator.py`** – DataUpdateCoordinator (push-based, `update_interval=None`), offline detection, throttling (max 5 Hz)
- **`config_flow.py`** – Multi-step config flow with optional WiFi provisioning and auto-discovery
- **`wifi_setup.py`** – ASCII commands for WiFi configuration (IPWIFI, UDPIP, TCPIP)

## Protocol Details

The WT901WIFI sends 54-byte frames with header `0x57 0x54 0x35 0x35` ("WT55") and footer `\r\n`:

| Offset | Length | Content |
|--------|--------|---------|
| 0–3 | 4 | Header `WT55` |
| 4–11 | 8 | Device ID (ASCII) |
| 12–51 | 40 | Sensor data (int16 LE) |
| 52–53 | 2 | Footer `\r\n` |

Sensor data contains: timestamp, acceleration (3-axis), gyroscope (3-axis), magnetometer (3-axis), Euler angles, temperature, battery, RSSI, and firmware version.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements_dev.txt
pytest
```

Linting:

```bash
ruff check custom_components/ tests/ tools/
```

## License

Apache 2.0 – see [LICENSE](LICENSE)
