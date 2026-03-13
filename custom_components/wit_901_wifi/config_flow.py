"""Config flow for WIT 901 WIFI integration."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

import homeassistant.helpers.config_validation as cv

from .const import (
    AUTO_REBOOT_PRESETS,
    CONF_AUTO_REBOOT_CUSTOM,
    CONF_AUTO_REBOOT_INTERVAL,
    CONF_DEVICE_ID,
    CONF_LISTEN_HOST,
    CONF_LISTEN_PORT,
    CONF_MQTT_ENABLED,
    CONF_MQTT_INTERVAL,
    CONF_MQTT_INTERVAL_CUSTOM,
    CONF_MQTT_QOS,
    CONF_MQTT_SENSORS,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_PROTOCOL,
    CONF_TARGET_IP,
    CONF_TIMEOUT_SECONDS,
    CONF_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL_CUSTOM,
    DEFAULT_AUTO_REBOOT_INTERVAL,
    DEFAULT_LISTEN_HOST,
    DEFAULT_LISTEN_PORT,
    DEFAULT_MQTT_ENABLED,
    DEFAULT_MQTT_INTERVAL,
    DEFAULT_MQTT_QOS,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_PROTOCOL,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    FRAME_HEADER,
    FRAME_LENGTH,
    MIN_AUTO_REBOOT_S,
    MIN_MQTT_INTERVAL_S,
    MIN_UPDATE_INTERVAL_S,
    MQTT_FORWARDABLE_SENSORS,
    MQTT_INTERVAL_PRESETS,
    NAME,
    PROTOCOL_TCP,
    PROTOCOL_UDP,
    UPDATE_INTERVAL_PRESETS,
)
from .protocol import parse_streaming_frame
from .wifi_setup import async_probe_sensor, async_send_ipwifi_command

_LOGGER = logging.getLogger(__name__)

CONF_SENSOR_HOST = "sensor_host"
CONF_SENSOR_PORT = "sensor_port"
CONF_WIFI_SSID = "wifi_ssid"
CONF_WIFI_PASSWORD = "wifi_password"

DEFAULT_SENSOR_HOST = "192.168.4.1"
DEFAULT_SENSOR_PORT = 9250
DEFAULT_DISCOVERY_TIMEOUT = 45
MIN_DISCOVERY_TIMEOUT = 30
MAX_DISCOVERY_TIMEOUT = 90
WILDCARD_HOSTS = {"0.0.0.0", "::"}

VALID_UPDATE_INTERVALS = list(UPDATE_INTERVAL_PRESETS.keys()) + ["custom"]
VALID_AUTO_REBOOT_INTERVALS = list(AUTO_REBOOT_PRESETS.keys()) + ["custom"]


def _is_valid_ipv4(host: str) -> bool:
    """Return True if host is a valid IPv4 address."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.version == 4


def _is_valid_device_id(device_id: str) -> bool:
    """Validate WT device id format."""
    return len(device_id) == 12 and device_id.startswith("WT55") and device_id[4:].isdigit()


def _hosts_conflict(host_a: str, host_b: str) -> bool:
    """Return True when two bind hosts conflict for the same protocol+port."""
    if host_a == host_b:
        return True
    return host_a in WILDCARD_HOSTS or host_b in WILDCARD_HOSTS


def _can_bind_listener(host: str, port: int, protocol: str) -> bool:
    """Try binding a listener socket to validate that address is usable."""
    sock_type = socket.SOCK_DGRAM if protocol == PROTOCOL_UDP else socket.SOCK_STREAM
    try:
        with socket.socket(socket.AF_INET, sock_type) as sock:
            sock.bind((host, port))
            if protocol == PROTOCOL_TCP:
                sock.listen(1)
    except OSError:
        return False
    return True


def _guess_local_ipv4() -> str:
    """Best-effort local IPv4 detection for target_ip default."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except OSError:
        return ""


def _merge_entry_config(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Merge entry data and options with options taking precedence."""
    merged = dict(entry.data)
    merged.update(entry.options)
    return merged


def _compute_discovery_timeout(listener_timeout: int) -> int:
    """Compute bounded await-frame timeout in seconds."""
    return max(
        MIN_DISCOVERY_TIMEOUT,
        min(MAX_DISCOVERY_TIMEOUT, listener_timeout * 3),
    )


def _validate_auto_reboot(
    validated: dict[str, Any],
    errors: dict[str, str],
    current: dict[str, Any] | None = None,
) -> None:
    """Validate and normalize auto-reboot interval fields."""
    src = current or {}
    reboot_interval = str(
        validated.get(
            CONF_AUTO_REBOOT_INTERVAL,
            src.get(CONF_AUTO_REBOOT_INTERVAL, DEFAULT_AUTO_REBOOT_INTERVAL),
        )
    ).lower()
    try:
        reboot_custom = int(
            validated.get(
                CONF_AUTO_REBOOT_CUSTOM,
                src.get(CONF_AUTO_REBOOT_CUSTOM, 0),
            )
        )
    except (TypeError, ValueError):
        reboot_custom = 0

    validated[CONF_AUTO_REBOOT_INTERVAL] = reboot_interval
    validated[CONF_AUTO_REBOOT_CUSTOM] = reboot_custom

    if reboot_interval not in VALID_AUTO_REBOOT_INTERVALS:
        errors[CONF_AUTO_REBOOT_INTERVAL] = "invalid_auto_reboot_interval"
    elif reboot_interval == "custom" and reboot_custom < MIN_AUTO_REBOOT_S:
        errors[CONF_AUTO_REBOOT_CUSTOM] = "invalid_auto_reboot_custom"


class _CaptureUdpProtocol(asyncio.DatagramProtocol):
    """Capture first valid streaming frame over UDP."""

    def __init__(self, fut: asyncio.Future[str]) -> None:
        self._future = fut

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        device_id = _extract_device_id_from_payload(data)
        if device_id and not self._future.done():
            self._future.set_result(device_id)


def _extract_device_id_from_payload(payload: bytes) -> str | None:
    """Extract first valid device_id from raw UDP/TCP payload bytes.

    Handles:
    - exact one-frame payloads (54 bytes)
    - prefixed payloads (garbage before frame header)
    - payloads with multiple concatenated frames
    """
    if len(payload) < FRAME_LENGTH:
        return None

    if len(payload) == FRAME_LENGTH:
        parsed = parse_streaming_frame(payload)
        return parsed["device_id"] if parsed else None

    start = 0
    while True:
        idx = payload.find(FRAME_HEADER, start)
        if idx < 0:
            return None
        end = idx + FRAME_LENGTH
        if end <= len(payload):
            parsed = parse_streaming_frame(payload[idx:end])
            if parsed:
                return parsed["device_id"]
        start = idx + 1


class _CaptureTcpProtocol(asyncio.Protocol):
    """Capture first valid streaming frame over TCP."""

    def __init__(self, fut: asyncio.Future[str]) -> None:
        self._future = fut
        self._buffer = bytearray()

    def data_received(self, data: bytes) -> None:
        self._buffer.extend(data)
        while len(self._buffer) >= FRAME_LENGTH:
            idx = self._buffer.find(FRAME_HEADER)
            if idx < 0:
                self._buffer.clear()
                return
            if idx > 0:
                del self._buffer[:idx]
            if len(self._buffer) < FRAME_LENGTH:
                return
            frame = bytes(self._buffer[:FRAME_LENGTH])
            del self._buffer[:FRAME_LENGTH]
            parsed = parse_streaming_frame(frame)
            if parsed and not self._future.done():
                self._future.set_result(parsed["device_id"])
                return


async def _await_first_device_id(
    protocol: str,
    host: str,
    port: int,
    timeout_seconds: int,
) -> str | None:
    """Wait for first valid frame and return discovered device_id."""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[str] = loop.create_future()

    transport: asyncio.BaseTransport | None = None
    server: asyncio.AbstractServer | None = None
    try:
        if protocol == PROTOCOL_UDP:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setblocking(False)
            sock.bind((host, port))
            transport, _ = await loop.create_datagram_endpoint(
                lambda: _CaptureUdpProtocol(fut),
                sock=sock,
            )
        else:
            server = await loop.create_server(
                lambda: _CaptureTcpProtocol(fut),
                host,
                port,
            )

        return await asyncio.wait_for(fut, timeout=timeout_seconds)
    except TimeoutError:
        return None
    finally:
        if transport is not None:
            transport.close()
        if server is not None:
            server.close()
            await server.wait_closed()


class Wit901WifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WIT 901 WIFI."""

    VERSION = 1

    def __init__(self) -> None:
        self._pending: dict[str, Any] = {}
        self._discovery_task: asyncio.Task[str | None] | None = None
        self._discovered_device_id: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return Wit901WifiOptionsFlow(config_entry)

    async def async_step_user(self, user_input: Mapping[str, Any] | None = None):
        """Step 1: listener config."""
        errors: dict[str, str] = {}

        if user_input is not None:
            validated = dict(user_input)
            protocol = str(validated.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)).lower()
            host = str(validated.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST)).strip()

            try:
                port = int(validated.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT))
            except (TypeError, ValueError):
                port = -1

            try:
                timeout = int(validated.get(CONF_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS))
            except (TypeError, ValueError):
                timeout = -1

            update_interval = str(
                validated.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ).lower()
            try:
                update_custom = float(
                    validated.get(CONF_UPDATE_INTERVAL_CUSTOM, 0)
                )
            except (TypeError, ValueError):
                update_custom = 0.0

            target_ip = str(validated.get(CONF_TARGET_IP, "")).strip()

            validated[CONF_PROTOCOL] = protocol
            validated[CONF_LISTEN_HOST] = host
            validated[CONF_LISTEN_PORT] = port
            validated[CONF_TIMEOUT_SECONDS] = timeout
            validated[CONF_UPDATE_INTERVAL] = update_interval
            validated[CONF_UPDATE_INTERVAL_CUSTOM] = update_custom
            validated[CONF_TARGET_IP] = target_ip

            if protocol not in {PROTOCOL_UDP, PROTOCOL_TCP}:
                errors[CONF_PROTOCOL] = "invalid_protocol"
            if not _is_valid_ipv4(host):
                errors[CONF_LISTEN_HOST] = "invalid_host"
            if not 1024 <= port <= 65535:
                errors[CONF_LISTEN_PORT] = "invalid_port"
            if not 3 <= timeout <= 300:
                errors[CONF_TIMEOUT_SECONDS] = "invalid_timeout"
            if target_ip and not _is_valid_ipv4(target_ip):
                errors[CONF_TARGET_IP] = "invalid_host"
            if update_interval not in VALID_UPDATE_INTERVALS:
                errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
            elif update_interval == "custom" and update_custom < MIN_UPDATE_INTERVAL_S:
                errors[CONF_UPDATE_INTERVAL_CUSTOM] = "invalid_update_interval_custom"

            _validate_auto_reboot(validated, errors)

            if (
                not errors
                and self._has_existing_listener_conflict(protocol=protocol, host=host, port=port)
            ):
                errors["base"] = "address_in_use"

            if not errors:
                can_bind = await self.hass.async_add_executor_job(
                    _can_bind_listener,
                    host,
                    port,
                    protocol,
                )
                if not can_bind:
                    errors["base"] = "cannot_bind"

            if not errors:
                self._pending = validated
                return await self.async_step_sensor_setup_menu()

            user_input = validated

        guessed_ip = _guess_local_ipv4()
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=(user_input or {}).get(CONF_NAME, NAME)): str,
                vol.Required(
                    CONF_PROTOCOL,
                    default=(user_input or {}).get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
                ): vol.In([PROTOCOL_UDP, PROTOCOL_TCP]),
                vol.Required(
                    CONF_LISTEN_HOST,
                    default=(user_input or {}).get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST),
                ): str,
                vol.Required(
                    CONF_LISTEN_PORT,
                    default=(user_input or {}).get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT),
                ): int,
                vol.Optional(
                    CONF_TARGET_IP,
                    default=(user_input or {}).get(CONF_TARGET_IP, guessed_ip),
                ): str,
                vol.Required(
                    CONF_TIMEOUT_SECONDS,
                    default=(user_input or {}).get(CONF_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS),
                ): int,
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=(user_input or {}).get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): vol.In(VALID_UPDATE_INTERVALS),
                vol.Optional(
                    CONF_UPDATE_INTERVAL_CUSTOM,
                    default=(user_input or {}).get(CONF_UPDATE_INTERVAL_CUSTOM, 0),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_AUTO_REBOOT_INTERVAL,
                    default=(user_input or {}).get(
                        CONF_AUTO_REBOOT_INTERVAL, DEFAULT_AUTO_REBOOT_INTERVAL
                    ),
                ): vol.In(VALID_AUTO_REBOOT_INTERVALS),
                vol.Optional(
                    CONF_AUTO_REBOOT_CUSTOM,
                    default=(user_input or {}).get(CONF_AUTO_REBOOT_CUSTOM, 0),
                ): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_sensor_setup_menu(self, user_input: Mapping[str, Any] | None = None):
        """Step 2 menu: optional provisioning or skip directly to await_frame."""
        return self.async_show_menu(
            step_id="sensor_setup_menu",
            menu_options=["sensor_setup", "await_frame"],
        )

    async def async_step_sensor_setup(self, user_input: Mapping[str, Any] | None = None):
        """Optional sensor provisioning step using IPWIFI command."""
        if not self._pending:
            return self.async_abort(reason="missing_listener_config")

        errors: dict[str, str] = {}
        defaults = {
            CONF_SENSOR_HOST: DEFAULT_SENSOR_HOST,
            CONF_SENSOR_PORT: DEFAULT_SENSOR_PORT,
            CONF_TARGET_IP: self._pending.get(CONF_TARGET_IP) or _guess_local_ipv4(),
            CONF_WIFI_SSID: "",
            CONF_WIFI_PASSWORD: "",
        }
        if user_input is not None:
            data = dict(user_input)
            sensor_host = str(data.get(CONF_SENSOR_HOST, DEFAULT_SENSOR_HOST)).strip()
            target_ip = str(data.get(CONF_TARGET_IP, "")).strip()
            wifi_ssid = str(data.get(CONF_WIFI_SSID, "")).strip()
            wifi_password = str(data.get(CONF_WIFI_PASSWORD, ""))

            try:
                sensor_port = int(data.get(CONF_SENSOR_PORT, DEFAULT_SENSOR_PORT))
            except (TypeError, ValueError):
                sensor_port = -1

            if not _is_valid_ipv4(sensor_host):
                errors[CONF_SENSOR_HOST] = "invalid_host"
            if not 1 <= sensor_port <= 65535:
                errors[CONF_SENSOR_PORT] = "invalid_port"
            if not _is_valid_ipv4(target_ip):
                errors[CONF_TARGET_IP] = "invalid_host"
            if not wifi_ssid:
                errors[CONF_WIFI_SSID] = "required"
            if not wifi_password:
                errors[CONF_WIFI_PASSWORD] = "required"

            if not errors:
                reachable = await async_probe_sensor(sensor_host, sensor_port)
                if not reachable:
                    errors["base"] = "sensor_unreachable"

            if not errors:
                try:
                    await async_send_ipwifi_command(
                        sensor_host=sensor_host,
                        sensor_port=sensor_port,
                        wifi_ssid=wifi_ssid,
                        wifi_password=wifi_password,
                        protocol=self._pending[CONF_PROTOCOL],
                        target_ip=target_ip,
                        target_port=self._pending[CONF_LISTEN_PORT],
                    )
                except OSError:
                    errors["base"] = "cannot_send_command"

            if not errors:
                # Persist the target_ip from provisioning
                self._pending[CONF_TARGET_IP] = target_ip
                return await self.async_step_await_frame()

            defaults.update(data)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SENSOR_HOST,
                    default=defaults[CONF_SENSOR_HOST],
                ): str,
                vol.Required(
                    CONF_SENSOR_PORT,
                    default=defaults[CONF_SENSOR_PORT],
                ): int,
                vol.Required(
                    CONF_TARGET_IP,
                    default=defaults[CONF_TARGET_IP],
                ): str,
                vol.Required(
                    CONF_WIFI_SSID,
                    default=defaults[CONF_WIFI_SSID],
                ): str,
                vol.Required(
                    CONF_WIFI_PASSWORD,
                    default=defaults[CONF_WIFI_PASSWORD],
                ): str,
            }
        )
        return self.async_show_form(step_id="sensor_setup", data_schema=schema, errors=errors)

    async def async_step_await_frame(self, user_input: Mapping[str, Any] | None = None):
        """Step 3: wait for first frame and auto-detect device_id."""
        if not self._pending:
            return self.async_abort(reason="missing_listener_config")

        if self._discovery_task is None:
            listener_timeout = int(
                self._pending.get(CONF_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS)
            )
            timeout_seconds = _compute_discovery_timeout(listener_timeout)
            self._discovery_task = self.hass.async_create_task(
                _await_first_device_id(
                    protocol=self._pending[CONF_PROTOCOL],
                    host=self._pending[CONF_LISTEN_HOST],
                    port=self._pending[CONF_LISTEN_PORT],
                    timeout_seconds=timeout_seconds,
                )
            )
            return self.async_show_progress(
                step_id="await_frame",
                progress_action="waiting_for_frame",
                progress_task=self._discovery_task,
            )

        if not self._discovery_task.done():
            return self.async_show_progress(
                step_id="await_frame",
                progress_action="waiting_for_frame",
                progress_task=self._discovery_task,
            )

        try:
            discovered = self._discovery_task.result()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Await-frame discovery failed: %s", err)
            discovered = None
        self._discovery_task = None
        self._discovered_device_id = discovered

        if discovered:
            return self.async_show_progress_done(next_step_id="finish_discovery")

        return self.async_show_progress_done(next_step_id="manual_device_id")

    async def async_step_finish_discovery(
        self,
        user_input: Mapping[str, Any] | None = None,
    ):
        """Finalize entry after successful automatic discovery."""
        if self._discovered_device_id:
            return await self._create_entry(self._discovered_device_id)
        return await self.async_step_manual_device_id()

    async def async_step_manual_device_id(self, user_input: Mapping[str, Any] | None = None):
        """Fallback step when automatic discovery timed out."""
        errors: dict[str, str] = {}
        if user_input is None:
            errors["base"] = "frame_timeout"
        if user_input is not None:
            device_id = str(user_input.get(CONF_DEVICE_ID, "")).strip().upper()
            if not _is_valid_device_id(device_id):
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            else:
                return await self._create_entry(device_id)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICE_ID,
                    default=(user_input or {}).get(CONF_DEVICE_ID, ""),
                ): str
            }
        )
        return self.async_show_form(step_id="manual_device_id", data_schema=schema, errors=errors)

    async def _create_entry(self, device_id: str):
        """Finalize config entry with resolved device_id."""
        data = dict(self._pending)
        data[CONF_DEVICE_ID] = device_id
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates=data)
        title = str(data.get(CONF_NAME) or f"{NAME} {device_id}")
        return self.async_create_entry(title=title, data=data)

    async def async_remove(self) -> None:
        """Cleanup flow resources when setup flow is cancelled/removed."""
        if self._discovery_task is None:
            return
        self._discovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._discovery_task
        self._discovery_task = None

    def _has_existing_listener_conflict(self, protocol: str, host: str, port: int) -> bool:
        """Return True if another configured entry already occupies the same listener space."""
        for entry in self._async_current_entries():
            merged = _merge_entry_config(entry)
            entry_protocol = str(merged.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)).lower()
            entry_host = str(merged.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST))
            entry_port = int(merged.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT))
            if entry_protocol != protocol or entry_port != port:
                continue
            if _hosts_conflict(entry_host, host):
                return True
        return False


VALID_MQTT_INTERVALS = list(MQTT_INTERVAL_PRESETS.keys()) + ["custom"]


class Wit901WifiOptionsFlow(config_entries.OptionsFlow):
    """Handle WIT 901 WIFI options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: Mapping[str, Any] | None = None):
        """Show menu to choose between listener and MQTT settings."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["listener", "mqtt"],
        )

    async def async_step_listener(self, user_input: Mapping[str, Any] | None = None):
        """Manage listener and device options."""
        errors: dict[str, str] = {}
        current = _merge_entry_config(self._config_entry)

        if user_input is not None:
            validated = dict(user_input)
            protocol = str(
                validated.get(
                    CONF_PROTOCOL,
                    current.get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
                )
            ).lower()
            host = str(
                validated.get(
                    CONF_LISTEN_HOST,
                    current.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST),
                )
            ).strip()
            device_id = str(
                validated.get(
                    CONF_DEVICE_ID,
                    current.get(CONF_DEVICE_ID, ""),
                )
            ).strip().upper()
            target_ip = str(
                validated.get(
                    CONF_TARGET_IP,
                    current.get(CONF_TARGET_IP, ""),
                )
            ).strip()

            try:
                port = int(
                    validated.get(
                        CONF_LISTEN_PORT,
                        current.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT),
                    )
                )
            except (TypeError, ValueError):
                port = -1

            try:
                timeout = int(
                    validated.get(
                        CONF_TIMEOUT_SECONDS,
                        current.get(CONF_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS),
                    )
                )
            except (TypeError, ValueError):
                timeout = -1

            update_interval = str(
                validated.get(
                    CONF_UPDATE_INTERVAL,
                    current.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                )
            ).lower()
            try:
                update_custom = float(
                    validated.get(
                        CONF_UPDATE_INTERVAL_CUSTOM,
                        current.get(CONF_UPDATE_INTERVAL_CUSTOM, 0),
                    )
                )
            except (TypeError, ValueError):
                update_custom = 0.0

            validated[CONF_PROTOCOL] = protocol
            validated[CONF_LISTEN_HOST] = host
            validated[CONF_LISTEN_PORT] = port
            validated[CONF_DEVICE_ID] = device_id
            validated[CONF_TARGET_IP] = target_ip
            validated[CONF_TIMEOUT_SECONDS] = timeout
            validated[CONF_UPDATE_INTERVAL] = update_interval
            validated[CONF_UPDATE_INTERVAL_CUSTOM] = update_custom

            if protocol not in {PROTOCOL_UDP, PROTOCOL_TCP}:
                errors[CONF_PROTOCOL] = "invalid_protocol"
            if not _is_valid_ipv4(host):
                errors[CONF_LISTEN_HOST] = "invalid_host"
            if not 1024 <= port <= 65535:
                errors[CONF_LISTEN_PORT] = "invalid_port"
            if not _is_valid_device_id(device_id):
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            if target_ip and not _is_valid_ipv4(target_ip):
                errors[CONF_TARGET_IP] = "invalid_host"
            if not 3 <= timeout <= 300:
                errors[CONF_TIMEOUT_SECONDS] = "invalid_timeout"
            if update_interval not in VALID_UPDATE_INTERVALS:
                errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
            elif update_interval == "custom" and update_custom < MIN_UPDATE_INTERVAL_S:
                errors[CONF_UPDATE_INTERVAL_CUSTOM] = "invalid_update_interval_custom"

            _validate_auto_reboot(validated, errors, current)

            if (
                not errors
                and self._has_existing_listener_conflict(
                    protocol=protocol,
                    host=host,
                    port=port,
                    exclude_entry_id=self._config_entry.entry_id,
                )
            ):
                errors["base"] = "address_in_use"

            listen_changed = (
                protocol != str(current.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)).lower()
                or host != str(current.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST))
                or port != int(current.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT))
            )
            if not errors and listen_changed:
                can_bind = await self.hass.async_add_executor_job(
                    _can_bind_listener,
                    host,
                    port,
                    protocol,
                )
                if not can_bind:
                    errors["base"] = "cannot_bind"

            if not errors:
                # Merge with existing options to preserve MQTT settings
                merged = dict(current)
                merged.update(validated)
                return self.async_create_entry(title="", data=merged)

            user_input = validated

        guessed_ip = current.get(CONF_TARGET_IP) or _guess_local_ipv4()
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PROTOCOL,
                    default=(user_input or current).get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
                ): vol.In([PROTOCOL_UDP, PROTOCOL_TCP]),
                vol.Required(
                    CONF_LISTEN_HOST,
                    default=(user_input or current).get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST),
                ): str,
                vol.Required(
                    CONF_LISTEN_PORT,
                    default=(user_input or current).get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT),
                ): int,
                vol.Optional(
                    CONF_TARGET_IP,
                    default=(user_input or current).get(CONF_TARGET_IP, guessed_ip),
                ): str,
                vol.Required(
                    CONF_DEVICE_ID,
                    default=(user_input or current).get(CONF_DEVICE_ID, ""),
                ): str,
                vol.Required(
                    CONF_TIMEOUT_SECONDS,
                    default=(user_input or current).get(
                        CONF_TIMEOUT_SECONDS,
                        DEFAULT_TIMEOUT_SECONDS,
                    ),
                ): int,
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=(user_input or current).get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ): vol.In(VALID_UPDATE_INTERVALS),
                vol.Optional(
                    CONF_UPDATE_INTERVAL_CUSTOM,
                    default=(user_input or current).get(
                        CONF_UPDATE_INTERVAL_CUSTOM, 0
                    ),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_AUTO_REBOOT_INTERVAL,
                    default=(user_input or current).get(
                        CONF_AUTO_REBOOT_INTERVAL, DEFAULT_AUTO_REBOOT_INTERVAL
                    ),
                ): vol.In(VALID_AUTO_REBOOT_INTERVALS),
                vol.Optional(
                    CONF_AUTO_REBOOT_CUSTOM,
                    default=(user_input or current).get(
                        CONF_AUTO_REBOOT_CUSTOM, 0
                    ),
                ): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="listener", data_schema=schema, errors=errors)

    async def async_step_mqtt(
        self, user_input: Mapping[str, Any] | None = None,
    ):
        """Manage MQTT forwarding options."""
        errors: dict[str, str] = {}
        current = _merge_entry_config(self._config_entry)

        if user_input is not None:
            mqtt_enabled = user_input.get(CONF_MQTT_ENABLED, False)

            # Validate MQTT integration is loaded
            if mqtt_enabled and "mqtt" not in self.hass.config.components:
                errors["base"] = "mqtt_not_configured"

            # Validate topic prefix
            prefix = str(
                user_input.get(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX)
            ).strip().strip("/")
            if mqtt_enabled and (not prefix or "#" in prefix or "+" in prefix or "//" in prefix):
                errors[CONF_MQTT_TOPIC_PREFIX] = "invalid_mqtt_topic"

            # QoS: explicitly cast to int (UI may deliver string)
            try:
                qos = int(user_input.get(CONF_MQTT_QOS, DEFAULT_MQTT_QOS))
            except (TypeError, ValueError):
                qos = DEFAULT_MQTT_QOS

            # Validate MQTT interval
            mqtt_interval = str(
                user_input.get(CONF_MQTT_INTERVAL, DEFAULT_MQTT_INTERVAL)
            ).lower()
            try:
                mqtt_interval_custom = float(
                    user_input.get(CONF_MQTT_INTERVAL_CUSTOM, 0)
                )
            except (TypeError, ValueError):
                mqtt_interval_custom = 0.0

            if mqtt_enabled and mqtt_interval not in VALID_MQTT_INTERVALS:
                errors[CONF_MQTT_INTERVAL] = "invalid_mqtt_interval"
            elif (
                mqtt_enabled
                and mqtt_interval == "custom"
                and mqtt_interval_custom < MIN_MQTT_INTERVAL_S
            ):
                errors[CONF_MQTT_INTERVAL_CUSTOM] = "invalid_mqtt_interval_custom"

            if not errors:
                # Merge with existing options to preserve listener settings
                merged = dict(current)
                merged.update({
                    CONF_MQTT_ENABLED: mqtt_enabled,
                    CONF_MQTT_TOPIC_PREFIX: prefix,
                    CONF_MQTT_SENSORS: user_input.get(CONF_MQTT_SENSORS, []),
                    CONF_MQTT_INTERVAL: mqtt_interval,
                    CONF_MQTT_INTERVAL_CUSTOM: mqtt_interval_custom,
                    CONF_MQTT_QOS: qos,
                })
                return self.async_create_entry(title="", data=merged)

        # On validation error, re-use user_input as defaults so nothing is lost
        defaults = user_input if user_input is not None else current
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MQTT_ENABLED,
                    default=defaults.get(CONF_MQTT_ENABLED, DEFAULT_MQTT_ENABLED),
                ): bool,
                vol.Optional(
                    CONF_MQTT_TOPIC_PREFIX,
                    default=defaults.get(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX),
                ): str,
                vol.Optional(
                    CONF_MQTT_SENSORS,
                    default=defaults.get(CONF_MQTT_SENSORS, []),
                ): cv.multi_select(MQTT_FORWARDABLE_SENSORS),
                vol.Optional(
                    CONF_MQTT_INTERVAL,
                    default=defaults.get(CONF_MQTT_INTERVAL, DEFAULT_MQTT_INTERVAL),
                ): vol.In(VALID_MQTT_INTERVALS),
                vol.Optional(
                    CONF_MQTT_INTERVAL_CUSTOM,
                    default=defaults.get(CONF_MQTT_INTERVAL_CUSTOM, 0),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_MQTT_QOS,
                    default=defaults.get(CONF_MQTT_QOS, DEFAULT_MQTT_QOS),
                ): vol.In({0: "0", 1: "1", 2: "2"}),
            }
        )
        return self.async_show_form(step_id="mqtt", data_schema=schema, errors=errors)

    def _has_existing_listener_conflict(
        self,
        protocol: str,
        host: str,
        port: int,
        exclude_entry_id: str,
    ) -> bool:
        """Return True if another configured entry occupies the same listener space."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id == exclude_entry_id:
                continue

            merged = _merge_entry_config(entry)
            entry_protocol = str(merged.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)).lower()
            entry_host = str(merged.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST))
            entry_port = int(merged.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT))

            if entry_protocol != protocol or entry_port != port:
                continue
            if _hosts_conflict(entry_host, host):
                return True
        return False
