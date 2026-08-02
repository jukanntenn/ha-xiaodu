"""小度（Xiaodu）集成。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_validation import config_entry_only_config_schema

from .api.xiaodu_client import HOST, XiaoduAPI
from .bemfa import (
    BemfaAPIClient,
    BemfaDeviceSyncManager,
    BemfaMQTTClient,
)
from .bemfa.const import (
    BEMFA_ALL_TOPIC_URL,
    BEMFA_BROKER,
    BEMFA_CHANGE_GROUP_URL,
    BEMFA_CHANGE_ROOM_URL,
    BEMFA_CREATE_TOPIC_URL,
    BEMFA_CREATE_TOPIC_V1_URL,
    BEMFA_DELETE_TOPIC_URL,
    BEMFA_MODIFY_NAME_URL,
    BEMFA_TLS_PORT,
    BEMFA_USE_TLS,
)
from .bemfa.protocol import parse_command
from .const import (
    CONF_COOKIE,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import XiaoduCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """设置小度组件。"""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """从配置条目（config entry）设置小度。"""
    cookie = entry.data[CONF_COOKIE]

    session = async_get_clientsession(hass)
    api_client = XiaoduAPI(cookie, session, host=HOST)

    # 如已启用，则创建 Bemfa（巴法云）相关组件
    bemfa_sync_manager: BemfaDeviceSyncManager | None = None
    bemfa_config: dict[str, Any] = entry.options.get("bemfa", {})
    if bemfa_config.get("enabled"):
        bemfa_uid: str = cast("str", bemfa_config.get("uid", ""))
        if bemfa_uid:
            secret_id = str(bemfa_config.get("secret_id", ""))
            secret_key = str(bemfa_config.get("secret_key", ""))
            bemfa_api = BemfaAPIClient(
                bemfa_uid,
                session,
                secret_id=secret_id,
                secret_key=secret_key,
                create_topic_url=BEMFA_CREATE_TOPIC_URL,
                create_topic_v1_url=BEMFA_CREATE_TOPIC_V1_URL,
                delete_topic_url=BEMFA_DELETE_TOPIC_URL,
                change_room_url=BEMFA_CHANGE_ROOM_URL,
                change_group_url=BEMFA_CHANGE_GROUP_URL,
                modify_name_url=BEMFA_MODIFY_NAME_URL,
                all_topic_url=BEMFA_ALL_TOPIC_URL,
            )
            bemfa_mqtt = BemfaMQTTClient(
                bemfa_uid,
                host=BEMFA_BROKER,
                port=BEMFA_TLS_PORT,
                use_tls=BEMFA_USE_TLS,
            )

            def _mqtt_message_received(topic: str, payload: str) -> None:
                """paho 线程回调：切回 HA 事件循环执行下行指令。"""

                async def _handle() -> None:
                    _LOGGER.debug(
                        "Bemfa MQTT downlink: topic=%s payload=%s", topic, payload
                    )
                    coordinator = cast("XiaoduCoordinator", entry.runtime_data)
                    if not coordinator.bemfa_sync_manager:
                        return
                    appliance_id = (
                        coordinator.bemfa_sync_manager.get_appliance_id_by_topic(topic)
                    )
                    if appliance_id is None:
                        _LOGGER.debug(
                            "Bemfa MQTT downlink ignored: no mapping for %s", topic
                        )
                        return
                    mapping = coordinator.bemfa_sync_manager.device_mapping[
                        appliance_id
                    ]
                    commands = parse_command(mapping.device_type, payload)
                    _LOGGER.debug("Bemfa MQTT downlink commands: %s", commands)
                    if commands:
                        await coordinator.handle_bemfa_command(appliance_id, commands)

                hass.loop.call_soon_threadsafe(
                    lambda: hass.async_create_task(_handle())
                )

            bemfa_mqtt.set_on_message_callback(_mqtt_message_received)
            bemfa_sync_manager = BemfaDeviceSyncManager(
                hass, bemfa_uid, bemfa_api, bemfa_mqtt
            )
            if not await bemfa_mqtt.async_connect(timeout_seconds=5.0):
                _LOGGER.warning(
                    "Bemfa MQTT unavailable; state reporting will be delayed"
                )

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
        await coordinator.async_cancel_background_tasks()
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
