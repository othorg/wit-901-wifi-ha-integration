"""WIT 901 WIFI integration package."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    CONF_DEVICE_ID,
    CONF_LISTEN_HOST,
    CONF_LISTEN_PORT,
    CONF_PROTOCOL,
    DEFAULT_LISTEN_HOST,
    DEFAULT_LISTEN_PORT,
    DEFAULT_PROTOCOL,
    DOMAIN,
    PLATFORMS,
    PROTOCOL_TCP,
    PROTOCOL_UDP,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_CONFIGURE_SENSOR = "configure_sensor"
CONF_SENSOR_HOST = "sensor_host"
CONF_SENSOR_PORT = "sensor_port"
CONF_WIFI_SSID = "wifi_ssid"
CONF_WIFI_PASSWORD = "wifi_password"
CONF_TARGET_IP = "target_ip"
CONF_TARGET_PORT = "target_port"


def _entry_config(entry: ConfigEntry) -> dict[str, Any]:
    """Return effective entry config with options overriding data."""
    merged = dict(entry.data)
    merged.update(entry.options)
    return merged


def _build_service_schema() -> Any:
    """Build the voluptuous schema for the configure_sensor service."""
    import voluptuous as vol  # noqa: PLC0415

    return vol.Schema(
        {
            vol.Required(CONF_SENSOR_HOST): str,
            vol.Optional(CONF_SENSOR_PORT, default=9250): vol.All(
                int, vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_WIFI_SSID): str,
            vol.Required(CONF_WIFI_PASSWORD): str,
            vol.Required(CONF_PROTOCOL, default=PROTOCOL_UDP): vol.In(
                [PROTOCOL_UDP, PROTOCOL_TCP]
            ),
            vol.Required(CONF_TARGET_IP): str,
            vol.Required(CONF_TARGET_PORT, default=1399): vol.All(
                int, vol.Range(min=1024, max=65535)
            ),
        }
    )


async def _async_handle_configure_sensor(call: ServiceCall) -> None:
    """Handle the configure_sensor service call."""
    from .wifi_setup import async_send_ipwifi_command  # noqa: PLC0415

    await async_send_ipwifi_command(
        sensor_host=call.data[CONF_SENSOR_HOST],
        sensor_port=call.data[CONF_SENSOR_PORT],
        wifi_ssid=call.data[CONF_WIFI_SSID],
        wifi_password=call.data[CONF_WIFI_PASSWORD],
        protocol=call.data[CONF_PROTOCOL],
        target_ip=call.data[CONF_TARGET_IP],
        target_port=call.data[CONF_TARGET_PORT],
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WIT 901 WIFI from a config entry."""
    from .coordinator import WitDataCoordinator  # noqa: PLC0415
    from .listener import WitListener  # noqa: PLC0415

    if not hass.services.has_service(DOMAIN, SERVICE_CONFIGURE_SENSOR):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CONFIGURE_SENSOR,
            _async_handle_configure_sensor,
            schema=_build_service_schema(),
        )

    config = _entry_config(entry)
    coordinator = WitDataCoordinator(hass, config)

    protocol = config.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
    host = config.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST)
    port = config.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT)
    device_id = config[CONF_DEVICE_ID]

    listener = WitListener(
        loop=hass.loop,
        protocol_type=protocol,
        host=host,
        port=port,
        device_id=device_id,
        on_frame=coordinator.handle_frame,
    )
    await listener.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "listener": listener,
    }
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await listener.async_stop()
        coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        listener: Any = entry_data.get("listener")
        coordinator: Any = entry_data.get("coordinator")
        if listener:
            await listener.async_stop()
        if coordinator:
            coordinator.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options are changed via UI."""
    effective = _entry_config(entry)
    new_device_id = effective.get(CONF_DEVICE_ID)
    if new_device_id and entry.unique_id != new_device_id:
        hass.config_entries.async_update_entry(entry, unique_id=new_device_id)
    await hass.config_entries.async_reload(entry.entry_id)
