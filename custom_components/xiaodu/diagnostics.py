"""小度（Xiaodu）集成的诊断（diagnostics）支持。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.diagnostics import async_redact_data

from .const import (
    CONF_COOKIE,
    CONF_ROOM_MAPPING,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import XiaoduCoordinator

TO_REDACT = {
    CONF_COOKIE,
    "cookie",
    "secret_id",
    "secret_key",
    "bemfa_secret_id",
    "bemfa_secret_key",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """返回配置条目（config entry）的诊断信息。"""
    coordinator = cast("XiaoduCoordinator", entry.runtime_data)

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
        bemfa_data: dict[str, object] = {
            k: {
                "topic": v.bemfa_topic,
                "nickname": v.bemfa_nickname,
                "room": v.bemfa_room,
                "sync_status": v.sync_status,
                "sync_error": v.sync_error,
            }
            for k, v in mapping.items()
        }
        bemfa_data["mqtt_connected"] = coordinator.bemfa_sync_manager.mqtt_connected
        bemfa_data["api_version"] = coordinator.bemfa_sync_manager.api_version
        bemfa_data["unsupported_devices"] = (
            coordinator.bemfa_sync_manager.unsupported_devices
        )

    return {
        "config_entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "room_mapping": entry.options.get(CONF_ROOM_MAPPING, {}),
        "device_count": len(devices_data),
        "devices": devices_data,
        "bemfa": bemfa_data,
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
        },
    }
