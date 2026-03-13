"""Push coordinator for WIT 901 WIFI."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    AUTO_REBOOT_PRESETS,
    CONF_AUTO_REBOOT_CUSTOM,
    CONF_AUTO_REBOOT_INTERVAL,
    CONF_DEVICE_ID,
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
    DEFAULT_LISTEN_PORT,
    DEFAULT_MQTT_ENABLED,
    DEFAULT_MQTT_INTERVAL,
    DEFAULT_MQTT_QOS,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_PROTOCOL,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MIN_AUTO_REBOOT_S,
    MIN_MQTT_INTERVAL_S,
    MIN_UPDATE_INTERVAL_S,
    MQTT_INTERVAL_PRESETS,
    REBOOT_GRACE_PERIOD_S,
    UPDATE_INTERVAL_PRESETS,
)

_LOGGER = logging.getLogger(__name__)


class WitDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that receives push updates from the WIT listener."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.device_id: str = entry_data[CONF_DEVICE_ID]
        self._entry_data = entry_data
        self._timeout: int = entry_data.get(CONF_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS)
        self._cancel_timeout: Callable[[], None] | None = None
        self._last_update_mono: float = 0.0
        self._update_interval_s: float = self._resolve_update_interval(entry_data)

        # Watchdog state
        self._went_offline_at: float | None = None
        self._is_offline: bool = True  # start offline until first frame

        # Source IP tracking
        self._last_source_ip: str | None = None

        # Reboot state
        self._reboot_lock = asyncio.Lock()
        self._reboot_in_progress: bool = False
        self._reboot_grace_until: float = 0.0

        # Auto-reboot timer
        self._auto_reboot_interval_s: int = self._resolve_auto_reboot_interval(entry_data)
        self._cancel_auto_reboot: Callable[[], None] | None = None

        # MQTT forwarding state
        self._mqtt_enabled: bool = entry_data.get(CONF_MQTT_ENABLED, DEFAULT_MQTT_ENABLED)
        self._mqtt_topic_prefix: str = entry_data.get(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX)
        self._mqtt_sensors: list[str] = entry_data.get(CONF_MQTT_SENSORS, [])
        self._mqtt_qos: int = int(entry_data.get(CONF_MQTT_QOS, DEFAULT_MQTT_QOS))
        self._mqtt_interval_s: float = self._resolve_mqtt_interval(entry_data)
        self._mqtt_warned: bool = False
        self._mqtt_publish_task: asyncio.Task[None] | None = None
        self._last_mqtt_publish_mono: float = 0.0

    @property
    def last_source_ip(self) -> str | None:
        """Return the last known sensor source IP."""
        return self._last_source_ip

    @staticmethod
    def _resolve_update_interval(entry_data: dict[str, Any]) -> float:
        """Resolve the effective update interval in seconds."""
        preset = entry_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        if preset in UPDATE_INTERVAL_PRESETS:
            return UPDATE_INTERVAL_PRESETS[preset]
        custom = entry_data.get(CONF_UPDATE_INTERVAL_CUSTOM)
        if custom is not None:
            return max(MIN_UPDATE_INTERVAL_S, float(custom))
        return MIN_UPDATE_INTERVAL_S

    @staticmethod
    def _resolve_auto_reboot_interval(entry_data: dict[str, Any]) -> int:
        """Resolve the auto-reboot interval in seconds (0 = disabled)."""
        preset = entry_data.get(CONF_AUTO_REBOOT_INTERVAL, DEFAULT_AUTO_REBOOT_INTERVAL)
        if preset in AUTO_REBOOT_PRESETS:
            return AUTO_REBOOT_PRESETS[preset]
        custom = entry_data.get(CONF_AUTO_REBOOT_CUSTOM)
        if custom is not None:
            return max(MIN_AUTO_REBOOT_S, int(custom))
        return 0

    @staticmethod
    def _resolve_mqtt_interval(entry_data: dict[str, Any]) -> float:
        """Resolve MQTT publish interval in seconds (0 = same as entity throttle)."""
        preset = entry_data.get(CONF_MQTT_INTERVAL, DEFAULT_MQTT_INTERVAL)
        if preset in MQTT_INTERVAL_PRESETS:
            return MQTT_INTERVAL_PRESETS[preset]
        custom = entry_data.get(CONF_MQTT_INTERVAL_CUSTOM)
        if custom is not None:
            return max(MIN_MQTT_INTERVAL_S, float(custom))
        return 0

    async def _async_update_data(self) -> dict[str, Any]:
        """Not used — data is pushed via handle_frame."""
        return self.data or {}

    @callback
    def handle_frame(self, parsed: dict[str, Any]) -> None:
        """Process a parsed frame from the listener."""
        # Track source IP
        if "source_ip" in parsed:
            self._last_source_ip = parsed["source_ip"]

        # Watchdog: log recovery (debounced — only on first frame after offline)
        if self._is_offline:
            if self._went_offline_at is not None:
                duration = time.monotonic() - self._went_offline_at
                _LOGGER.info(
                    "Sensor %s back online after %.0f seconds",
                    self.device_id,
                    duration,
                )
            self._went_offline_at = None
            self._is_offline = False
            self._reboot_in_progress = False

        self._schedule_offline_timer()
        now = time.monotonic()
        if now - self._last_update_mono < self._update_interval_s:
            return
        self._last_update_mono = now
        self.async_set_updated_data({**parsed, "online": True})

        # MQTT forwarding — own throttle + serialized (max 1 task)
        if self._mqtt_enabled:
            mqtt_ok = (
                self._mqtt_interval_s <= 0
                or (now - self._last_mqtt_publish_mono >= self._mqtt_interval_s)
            )
            if mqtt_ok and (self._mqtt_publish_task is None or self._mqtt_publish_task.done()):
                self._last_mqtt_publish_mono = now
                self._mqtt_publish_task = self.hass.async_create_task(
                    self._async_mqtt_publish(parsed)
                )

    def _schedule_offline_timer(self) -> None:
        """Reset the offline timeout timer."""
        if self._cancel_timeout is not None:
            self._cancel_timeout()
        self._cancel_timeout = async_call_later(
            self.hass, self._timeout, self._mark_offline
        )

    @callback
    def _mark_offline(self, _now: Any) -> None:
        """Mark device as offline after timeout (debounced — WARNING only once)."""
        if self._is_offline:
            return  # already offline, no duplicate warning

        # Suppress warning during grace period after deliberate reboot
        if self._reboot_in_progress and time.monotonic() < self._reboot_grace_until:
            _LOGGER.debug(
                "Sensor %s offline during reboot grace period, suppressing warning",
                self.device_id,
            )
            # Schedule a deferred check after grace period expires
            remaining = self._reboot_grace_until - time.monotonic()
            async_call_later(
                self.hass, max(1.0, remaining), self._deferred_offline_warning
            )
        else:
            self._went_offline_at = time.monotonic()
            _LOGGER.warning(
                "Sensor %s stopped sending frames (offline since %s)",
                self.device_id,
                datetime.now().isoformat(timespec="seconds"),
            )

        self._is_offline = True
        if self.data:
            self.async_set_updated_data({**self.data, "online": False})
        if self._mqtt_enabled:
            self.hass.async_create_task(self._async_mqtt_publish_availability("offline"))

    @callback
    def _deferred_offline_warning(self, _now: Any) -> None:
        """Emit offline WARNING after grace period if sensor never came back."""
        if not self._is_offline or self._went_offline_at is not None:
            return  # came back online, or warning already emitted
        self._went_offline_at = time.monotonic()
        _LOGGER.warning(
            "Sensor %s did not recover after reboot (offline since %s)",
            self.device_id,
            datetime.now().isoformat(timespec="seconds"),
        )

    @callback
    def start_auto_reboot(self) -> None:
        """Start the periodic auto-reboot timer if configured."""
        if self._auto_reboot_interval_s <= 0:
            return
        self._cancel_auto_reboot = async_track_time_interval(
            self.hass,
            self._perform_auto_reboot,
            timedelta(seconds=self._auto_reboot_interval_s),
        )
        _LOGGER.info(
            "Auto-reboot enabled for %s every %ds",
            self.device_id,
            self._auto_reboot_interval_s,
        )

    async def _perform_auto_reboot(self, _now: Any) -> None:
        """Execute a scheduled reboot."""
        try:
            await self.async_reboot()
        except HomeAssistantError as err:
            _LOGGER.warning("Scheduled auto-reboot failed for %s: %s", self.device_id, err)

    async def async_reboot(self) -> None:
        """Reboot the sensor by re-sending its current target config.

        Raises HomeAssistantError if sensor IP is unknown.
        """
        if not self._last_source_ip:
            raise HomeAssistantError(
                f"Cannot reboot sensor {self.device_id}: no known sensor IP. "
                "Wait for the sensor to send at least one frame."
            )

        target_ip = self._entry_data.get(CONF_TARGET_IP)
        if not target_ip:
            raise HomeAssistantError(
                f"Cannot reboot sensor {self.device_id}: no target IP configured. "
                "Set 'Target IP' in integration options."
            )

        async with self._reboot_lock:
            from .wifi_setup import async_reboot_sensor  # noqa: PLC0415

            self._reboot_in_progress = True
            self._reboot_grace_until = time.monotonic() + REBOOT_GRACE_PERIOD_S

            protocol = self._entry_data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
            listen_port = self._entry_data.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT)

            _LOGGER.info(
                "Rebooting sensor %s at %s (target=%s:%s, protocol=%s)",
                self.device_id,
                self._last_source_ip,
                target_ip,
                listen_port,
                protocol,
            )

            try:
                await async_reboot_sensor(
                    sensor_host=self._last_source_ip,
                    sensor_port=9250,
                    protocol=protocol,
                    target_ip=target_ip,
                    target_port=listen_port,
                )
            except OSError as err:
                self._reboot_in_progress = False
                raise HomeAssistantError(
                    f"Reboot command failed for {self.device_id}: {err}"
                ) from err

    async def _async_mqtt_publish(self, parsed: dict[str, Any]) -> None:
        """Publish selected sensor values to MQTT."""
        try:
            from homeassistant.components import mqtt  # noqa: PLC0415
        except ImportError:
            if not self._mqtt_warned:
                _LOGGER.warning("MQTT forwarding enabled but MQTT integration not available")
                self._mqtt_warned = True
            return

        try:
            prefix = self._mqtt_topic_prefix
            device_id = self.device_id
            for value_key in self._mqtt_sensors:
                value = parsed.get(value_key)
                if value is not None:
                    topic = f"{prefix}/{device_id}/{value_key}"
                    await mqtt.async_publish(
                        self.hass, topic, str(value),
                        qos=self._mqtt_qos, retain=True,
                    )
            await mqtt.async_publish(
                self.hass,
                f"{prefix}/{device_id}/availability",
                "online", qos=1, retain=True,
            )
        except Exception:  # noqa: BLE001
            if not self._mqtt_warned:
                _LOGGER.warning(
                    "MQTT publish failed for %s — check MQTT integration",
                    self.device_id,
                )
                self._mqtt_warned = True

    async def _async_mqtt_publish_availability(self, status: str) -> None:
        """Publish availability status to MQTT (best-effort)."""
        try:
            from homeassistant.components import mqtt  # noqa: PLC0415

            await mqtt.async_publish(
                self.hass,
                f"{self._mqtt_topic_prefix}/{self.device_id}/availability",
                status, qos=1, retain=True,
            )
        except Exception:  # noqa: BLE001
            pass

    @callback
    def async_shutdown(self) -> None:
        """Cancel any pending timers."""
        if self._cancel_timeout is not None:
            self._cancel_timeout()
            self._cancel_timeout = None
        if self._cancel_auto_reboot is not None:
            self._cancel_auto_reboot()
            self._cancel_auto_reboot = None
