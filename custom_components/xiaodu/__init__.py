"""小度（Xiaodu）集成。"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_validation import config_entry_only_config_schema
from homeassistant.helpers.device_registry import DeviceEntry

from .api.xiaodu_client import XiaoduAPI
from .bemfa import (
    BemfaAPIClient,
    BemfaDeviceSyncManager,
    BemfaMQTTClient,
    BemfaStatePublisher,
)
from .const import (
    CONF_COOKIE,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import XiaoduCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """设置小度组件。"""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """从配置条目（config entry）设置小度。"""
    cookie = entry.data[CONF_COOKIE]

    session = async_get_clientsession(hass)
    api_client = XiaoduAPI(cookie, session)

    # 如已启用，则创建 Bemfa（巴法云）相关组件
    bemfa_sync_manager: BemfaDeviceSyncManager | None = None
    bemfa_config = entry.options.get("bemfa", {})
    if bemfa_config.get("enabled"):
        bemfa_uid = bemfa_config.get("uid", "")
        if bemfa_uid:
            bemfa_api = BemfaAPIClient(bemfa_uid, session)
            bemfa_mqtt = BemfaMQTTClient(bemfa_uid)
            bemfa_publisher = BemfaStatePublisher(bemfa_mqtt)
            bemfa_sync_manager = BemfaDeviceSyncManager(
                bemfa_uid, bemfa_api, bemfa_mqtt, bemfa_publisher
            )
            try:
                await asyncio.to_thread(bemfa_mqtt.connect)
            except Exception:
                _LOGGER.exception("Failed to connect to Bemfa MQTT broker")

    coordinator = XiaoduCoordinator(hass, entry, api_client, bemfa_sync_manager)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置条目（config entry）。"""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: XiaoduCoordinator = entry.runtime_data
        if coordinator.bemfa_sync_manager:
            # 在事件循环之外删除 Bemfa 主题（topic）并断开 MQTT 连接。
            # 主题删除失败仅记录日志，不会阻塞卸载流程——
            # 此时 HA 实体（entity）已移除；遗留的 Bemfa 主题如有需要可手动清理。
            try:
                await coordinator.bemfa_sync_manager.async_cleanup_all()
            except Exception:
                _LOGGER.warning(
                    "Failed to clean up Bemfa topics on unload", exc_info=True
                )
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """从配置条目（config entry）中移除设备。"""
    coordinator: XiaoduCoordinator = config_entry.runtime_data
    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN and identifier[1] in coordinator.devices:
            return False
    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """处理选项（options）更新。"""
    await hass.config_entries.async_reload(entry.entry_id)
