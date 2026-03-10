# WIT 901 WIFI – Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant Custom Integration für **WIT-Motion WT901WIFI** 9-Achsen-IMU-Sensoren.

Der Sensor streamt seine Daten per WiFi (UDP oder TCP) direkt an Home Assistant – ohne Cloud, ohne Polling.

## Features

- **Local Push** – HA lauscht auf einem konfigurierbaren Port, der Sensor sendet Frames
- **Sensoren**: Roll, Pitch, Yaw, Temperatur, Batteriespannung, Batteriestand, Signalstärke (RSSI)
- **Online-Status** als Binary Sensor (Connectivity)
- **WiFi-Provisionierung** direkt aus der HA-Oberfläche oder per CLI-Tool
- **Config Flow** mit automatischer Device-ID-Erkennung
- **Options Flow** zum Ändern aller Listener-Parameter im laufenden Betrieb
- **UDP und TCP** Protokoll
- **Diagnostics**-Support für Debugging
- **HACS-kompatibel**
- **Deutsch und Englisch** lokalisiert

## Installation

### HACS (empfohlen)

1. In HACS auf **Integrationen** → **Benutzerdefinierte Repositories** gehen
2. Repository-URL hinzufügen: `https://github.com/othorg/wit-901-wifi-ha-integration`
3. Kategorie: **Integration**
4. **WIT 901 WIFI** installieren und HA neu starten

### Manuell

1. `custom_components/wit_901_wifi/` in das HA `config/custom_components/` Verzeichnis kopieren
2. HA neu starten

## Sensor einrichten

### Voraussetzungen

- WT901WIFI Sensor (WIT-Motion)
- 2.4 GHz WiFi-Netzwerk (der Sensor unterstützt kein 5 GHz)
- Die IP-Adresse deines HA-Servers

### Schritt 1: Sensor ins WiFi bringen

Der Sensor startet im **AP-Modus** (eigenes WiFi-Netzwerk). Er muss zuerst in dein Heimnetzwerk eingebunden werden.

#### Option A: Über den HA Config Flow

1. **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen** → **WIT 901 WIFI**
2. Listener konfigurieren (Port, Protokoll, Host)
3. **Sensor einrichten** wählen (statt überspringen)
4. WiFi-SSID, Passwort, Sensor-IP (Standard: `192.168.4.1`) und Target-IP (dein HA-Server) eingeben
5. Der Sensor startet neu, verbindet sich mit dem WiFi und beginnt zu streamen
6. Die Device-ID wird automatisch erkannt

#### Option B: Über das CLI-Tool

Zuerst mit dem Sensor-AP verbinden (SSID des Sensors, z.B. `WT901WiFi_XXXX`), dann:

```bash
python tools/configure_sensor.py \
  --ssid "MeinWiFi" --password "MeinPasswort" \
  --target-ip 192.168.1.100 --target-port 1399 --protocol udp
```

Danach zurück ins Heimnetz wechseln und prüfen:

```bash
python tools/configure_sensor.py --discover --discover-port 1399
```

> **Tipp**: Wenn dein Rechner per Ethernet im selben Netz ist, musst du nur das WiFi umschalten – Ethernet bleibt verbunden.

### Schritt 2: Integration in HA konfigurieren

Falls noch nicht über den Config Flow geschehen:

1. **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen** → **WIT 901 WIFI**
2. Protokoll: `udp` (empfohlen)
3. Listen Host: `0.0.0.0` (alle Interfaces)
4. Listen Port: `1399` (muss mit dem Sensor-Target übereinstimmen)
5. Die Device-ID wird automatisch aus dem ersten empfangenen Frame erkannt

## CLI-Tool (`tools/configure_sensor.py`)

Standalone-Tool zur Sensor-Konfiguration, unabhängig von Home Assistant.

```bash
# Vollständige Provisionierung (WiFi + Streaming-Ziel)
python tools/configure_sensor.py \
  --ssid "MeinWiFi" --password "Passwort" \
  --target-ip 192.168.1.100 --target-port 1399 --protocol udp

# Nur prüfen ob Sensor erreichbar ist
python tools/configure_sensor.py --probe-only

# Auf Frames lauschen und Device-Info anzeigen
python tools/configure_sensor.py --discover --discover-port 1399

# Nur Streaming-Ziel ändern (Sensor bereits im Netz)
python tools/configure_sensor.py \
  --sensor-host 192.168.1.200 \
  --target-ip 192.168.1.100 --target-port 1399 --protocol udp \
  --target-only

# Sensor zurück in den AP-Modus setzen
python tools/configure_sensor.py --ap-mode
```

| Parameter | Standard | Beschreibung |
|-----------|----------|-------------|
| `--sensor-host` | `192.168.4.1` | IP des Sensors (AP-Modus) |
| `--sensor-port` | `9250` | LOCALPORT des Sensors |
| `--ssid` | – | WiFi-SSID (2.4 GHz) |
| `--password` | – | WiFi-Passwort |
| `--target-ip` | – | Ziel-IP (HA-Server) |
| `--target-port` | `1399` | Ziel-Port |
| `--protocol` | `udp` | `udp` oder `tcp` |

## HA-Service: `wit_901_wifi.configure_sensor`

Die Integration registriert einen Service zur WiFi-Provisionierung, aufrufbar über **Entwicklerwerkzeuge** → **Dienste**:

```yaml
service: wit_901_wifi.configure_sensor
data:
  sensor_host: "192.168.4.1"
  sensor_port: 9250
  wifi_ssid: "MeinWiFi"
  wifi_password: "Passwort"
  protocol: "udp"
  target_ip: "192.168.1.100"
  target_port: 1399
```

> **Sicherheit**: Das WiFi-Passwort wird ausschließlich für den UDP-Befehl verwendet und weder gespeichert noch geloggt.

## Entitäten

Nach erfolgreicher Einrichtung werden folgende Entitäten erstellt:

| Entität | Typ | Einheit | Beschreibung |
|---------|-----|---------|-------------|
| Roll | Sensor | ° | Rollwinkel |
| Pitch | Sensor | ° | Nickwinkel |
| Yaw | Sensor | ° | Gierwinkel |
| Temperatur | Sensor | °C | Sensortemperatur |
| Batteriespannung | Sensor | V | Batteriestand in Volt |
| Batteriestand | Sensor | % | Geschätzter Ladestand |
| Signalstärke | Sensor | dBm | WiFi RSSI |
| Online | Binary Sensor | – | Verbindungsstatus |

## Architektur

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
                              (push, kein Polling)
                                     │
                                     ▼
                              Sensor Entities
```

- **`protocol.py`** – Parser für 54-Byte WT55-Frames
- **`listener.py`** – UDP/TCP asyncio Listener mit Device-ID-Filter
- **`coordinator.py`** – DataUpdateCoordinator (push-basiert, `update_interval=None`), Offline-Erkennung, Throttling (max 5 Hz)
- **`config_flow.py`** – Multi-Step Config Flow mit optionaler WiFi-Provisionierung und Auto-Discovery
- **`wifi_setup.py`** – ASCII-Befehle für WiFi-Konfiguration (IPWIFI, UDPIP, TCPIP)

## Protokoll-Details

Der WT901WIFI sendet 54-Byte-Frames mit Header `0x57 0x54 0x35 0x35` ("WT55") und Footer `\r\n`:

| Offset | Länge | Inhalt |
|--------|-------|--------|
| 0–3 | 4 | Header `WT55` |
| 4–11 | 8 | Device-ID (ASCII) |
| 12–51 | 40 | Sensordaten (int16 LE) |
| 52–53 | 2 | Footer `\r\n` |

Sensordaten enthalten: Zeitstempel, Beschleunigung (3-Achsen), Gyroskop (3-Achsen), Magnetometer (3-Achsen), Euler-Winkel, Temperatur, Batterie, RSSI und Firmware-Version.

## Entwicklung

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

## Lizenz

Apache 2.0 – siehe [LICENSE](LICENSE)
