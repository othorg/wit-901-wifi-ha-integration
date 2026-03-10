"""Diagnostics for WIT 901 WIFI."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = dict(entry.data)
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
    coordinator_data = dict(coordinator.data) if coordinator and coordinator.data else {}
    return {
        "config_entry": entry_data,
        "coordinator_data": coordinator_data,
    }
