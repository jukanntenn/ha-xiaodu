"""小度（Xiaodu）集成的诊断（diagnostics）支持。"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_COOKIE, CONF_ROOM_MAPPING

TO_REDACT = {CONF_COOKIE, "cookie"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """返回配置条目（config entry）的诊断信息。"""
    coordinator = entry.runtime_data

    devices_data = {}
    if coordinator.data:
        for device_id, device in coordinator.data.items():
            devices_data[device_id] = {
                "friendly_name": device.friendly_name,
                "room_name": device.room_name,
                "appliance_types": device.appliance_types,
            }

    bemfa_data = {}
    if coordinator.bemfa_sync_manager:
        mapping = coordinator.bemfa_sync_manager.device_mapping
        bemfa_data = {
            k: {
                "topic": v.bemfa_topic,
                "nickname": v.bemfa_nickname,
                "room": v.bemfa_room,
                "sync_status": v.sync_status,
            }
            for k, v in mapping.items()
        }

    return {
        "config_entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "room_mapping": entry.options.get(CONF_ROOM_MAPPING, {}),
        "device_count": len(devices_data),
        "devices": devices_data,
        "bemfa": bemfa_data,
    }
