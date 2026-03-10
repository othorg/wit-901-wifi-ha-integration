"""Push coordinator for WIT 901 WIFI."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_DEVICE_ID,
    CONF_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    DOMAIN,
    MIN_UPDATE_INTERVAL_S,
)

_LOGGER = logging.getLogger(__name__)


class WitDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that receives push updates from the WIT listener."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.device_id: str = entry_data[CONF_DEVICE_ID]
        self._timeout: int = entry_data.get(CONF_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS)
        self._cancel_timeout: Callable[[], None] | None = None
        self._last_update_mono: float = 0.0

    async def _async_update_data(self) -> dict[str, Any]:
        """Not used — data is pushed via handle_frame."""
        return self.data or {}

    @callback
    def handle_frame(self, parsed: dict[str, Any]) -> None:
        """Process a parsed frame from the listener."""
        self._schedule_offline_timer()
        now = time.monotonic()
        if now - self._last_update_mono < MIN_UPDATE_INTERVAL_S:
            return
        self._last_update_mono = now
        self.async_set_updated_data({**parsed, "online": True})

    def _schedule_offline_timer(self) -> None:
        """Reset the offline timeout timer."""
        if self._cancel_timeout is not None:
            self._cancel_timeout()
        self._cancel_timeout = async_call_later(
            self.hass, self._timeout, self._mark_offline
        )

    @callback
    def _mark_offline(self, _now: Any) -> None:
        """Mark device as offline after timeout."""
        if self.data:
            self.async_set_updated_data({**self.data, "online": False})

    @callback
    def async_shutdown(self) -> None:
        """Cancel any pending timers."""
        if self._cancel_timeout is not None:
            self._cancel_timeout()
            self._cancel_timeout = None
