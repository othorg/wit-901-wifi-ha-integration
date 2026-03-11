# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- No changes yet.

## [0.4.3] - 2026-03-11

### Fixed
- Config flow frame discovery is now robust against real-world UDP payloads:
  - discovery now binds UDP with `SO_REUSEADDR` (same bind behavior as runtime listener)
  - payload scanning now supports prefixed/concatenated frame data and extracts the first valid WT frame
- This resolves cases where CLI discovery succeeded but HA config-flow `await_frame` timed out.

### Added
- New regression tests for config-flow discovery payload extraction:
  - exact frame payload
  - prefixed payload
  - multi-frame payload
  - invalid payload fallback
- Restored top-level `requirements.txt` for reproducible local HA test environment setup.

## [0.4.2] - 2026-03-11

### Changed
- Updated GitHub Actions workflows to Node-24-ready `actions/checkout@v5`:
  - `.github/workflows/ci.yml`
  - `.github/workflows/version-bump-release.yml`

## [0.4.1] - 2026-03-11

### Added
- Added HACS default-submission checklist for maintainers: `docs/HACS_DEFAULT_SUBMISSION.md`.

### Changed
- CI now includes:
  - HACS validation (`hacs/action`, `category: integration`)
  - Hassfest validation (`home-assistant/actions/hassfest`)

## [0.4.0] - 2026-03-11

### Added
- **Reboot button** entity (`ButtonDeviceClass.RESTART`, `EntityCategory.CONFIG`) to manually reboot the sensor from the HA UI.
- **Reboot service** `wit_901_wifi.reboot_sensor` callable via Developer Tools with `entry_id` parameter.
- **Auto-reboot** with configurable interval (disabled, 6h, 12h, 24h, or custom) in both config flow and options flow.
- **Watchdog logging**: debounced WARNING on first offline transition, INFO on recovery with offline duration.
- **Reboot grace period** (15s) suppresses false offline warnings after deliberate reboot.
- **Source IP tracking** from incoming frames for reboot targeting.
- **Target IP** field in config/options flow (auto-detected default) for reboot command destination.
- `asyncio.Lock` serialization for reboot commands to prevent race conditions.
- Service lifecycle: services are deregistered when the last config entry is unloaded.
- Tests for reboot functionality (`test_reboot.py`) and button entity (`test_button.py`).
- English and German translations for all new config fields and the reboot button entity.

## [0.3.0] - 2026-03-11

### Added
- 10 new sensor entities exposing all available WT901WIFI data:
  - Acceleration X/Y/Z (g)
  - Gyroscope X/Y/Z (°/s)
  - Magnetometer X/Y/Z (µT)
  - Firmware version (diagnostic)
- All new sensors are **disabled by default** (`entity_registry_enabled_default=False`) to keep the default entity list clean.
- Firmware version sensor uses `EntityCategory.DIAGNOSTIC`.
- Entity tests (`tests/test_entities.py`) covering all new sensor descriptions.
- English and German translations for all new entities.
- README entities table updated with all 17 sensors + 1 binary sensor and "disabled by default" note.

## [0.2.3] - 2026-03-11

### Added
- Added full integration brand asset set under `custom_components/wit_901_wifi/brand/`:
  - `icon.png`, `icon@2x.png`
  - `dark_icon.png`, `dark_icon@2x.png`
  - `logo.png`, `logo@2x.png`
  - `dark_logo.png`, `dark_logo@2x.png`
- Assets are derived from `wit-ha-lovelace-card/assets/wit-icon.svg` with dark-mode optimized variants.

## [0.2.2] - 2026-03-10

### Added
- GitHub release automation workflow (`.github/workflows/release.yml`) for `v*` tags.

### Changed
- Explicit release/versioning flow aligned with the Lovelace card projects to improve HACS update detection.
- Version bump only; no functional runtime behavior changes.

## [0.2.1] - 2026-03-10

### Fixed
- Listener socket now uses `SO_REUSEADDR` (UDP) and `reuse_address=True` (TCP) to prevent "Address in use" errors during integration reload.
- Listener bind retries up to 3 times with 1s delay to handle port release race condition on options change.

## [0.2.0] - 2026-03-10

### Added
- Configurable update interval: presets Live (5 Hz), 10s, 1min, or custom value in seconds.
- New config/options fields: `update_interval` and `update_interval_custom`.
- English and German translations for update interval fields and error messages.

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
