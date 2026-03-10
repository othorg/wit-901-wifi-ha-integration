# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- No changes yet.

## [0.1.5] - 2026-03-10

### Fixed
- Config-flow await-frame progress now tracks the actual discovery task (`progress_task`), preventing setup from hanging on "waiting for first frame" while frames are already received.
- Added defensive error handling/logging when temporary discovery listener fails, with fallback to manual device-id step.

## [0.1.4] - 2026-03-10

### Changed
- Version bump for HACS redeploy.

## [0.1.3] - 2026-03-10

### Added
- Bundled `docs/` and `tools/` into `custom_components/wit_901_wifi/` so they are included in HACS integration installs.
- Added packaged copies:
  - `custom_components/wit_901_wifi/docs/WT901WIFI protocol.pdf`
  - `custom_components/wit_901_wifi/tools/configure_sensor.py`

## [0.1.2] - 2026-03-10

### Fixed
- Config-flow await-frame cleanup: discovery listener task is cancelled when the flow is aborted/closed.
- Await-frame timeout is now bounded to 30-90 seconds to avoid long-lived temporary listener binds.
- Config-flow progress handling aligned to `async_show_progress_done(...)` pattern.

## [0.1.1] - 2026-03-10

### Added
- Initial repository scaffold with CI pipeline (ruff + pytest).
- Home Assistant integration skeleton for `wit_901_wifi` (manifest, const, platforms).
- WT901WIFI 54-byte streaming frame parser (`protocol.py`) with unit tests.
- UDP and TCP asyncio listener (`listener.py`) with device-ID filtering and stream buffering.
- Push-based `DataUpdateCoordinator` (`coordinator.py`) with monotonic throttling (max 5 Hz) and offline detection via `async_call_later` timer.
- 7 sensor entities: roll, pitch, yaw, temperature, battery voltage, battery percentage, RSSI.
- Online binary sensor (connectivity device class).
- Diagnostics support (`diagnostics.py`).
- Multi-step config flow with validation:
  - Step 1: Listener config (protocol, host, port, timeout) with port-bind check and conflict detection.
  - Step 2: Optional WiFi sensor provisioning via IPWIFI command.
  - Step 3: Auto-discovery of device-ID from first received frame, with manual fallback.
- Options flow to edit protocol, host, port, device-ID, and timeout at runtime (auto-reload on change).
- WiFi provisioning module (`wifi_setup.py`) with ASCII commands: IPWIFI (combined), UDPIP/TCPIP (target-only).
- HA service `wit_901_wifi.configure_sensor` for WiFi provisioning from Developer Tools.
- Standalone CLI tool (`tools/configure_sensor.py`) for sensor provisioning outside HA:
  - Full provisioning, probe-only, discover, target-only, AP-mode reset.
- Translations: English and German (with proper UTF-8 umlauts).
- HACS compatibility (`hacs.json`).

### Security
- WiFi password is never stored in config entry data, options, or diagnostics.
- WiFi password is never written to log output.
- CLI tool does not print raw command payload (password masking).

### Fixed
- Listener leak protection: cleanup on platform forwarding failure.
- Lazy imports in `__init__.py` to avoid import crashes in dev/test environments.
- Config flow import and validation fixes (host, port, device-ID, timeout).
- Wildcard-aware listener conflict detection (`0.0.0.0` / `::`).
