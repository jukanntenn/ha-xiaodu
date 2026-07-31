"""Xiaodu 集成的 Switch 平台。"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.xiaodu_types import Command
from .const import SOCKET_TYPES, SWITCH_TYPES
from .coordinator import XiaoduCoordinator
from .entity import XiaoduEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """从配置项（config entry）设置 Xiaodu Switch。"""
    coordinator: XiaoduCoordinator = config_entry.runtime_data
    added_device_ids: set[str] = set()

    @callback
    def _async_discover_entities() -> None:
        """发现并添加新的 Switch 实体（entity）。"""
        if not coordinator.data:
            return

        new_entities = []
        for appliance_id, device in coordinator.data.items():
            if appliance_id in added_device_ids:
                continue
            if not any(t in SWITCH_TYPES for t in device.appliance_types):
                continue
            new_entities.append(XiaoduSwitch(coordinator, appliance_id))
            added_device_ids.add(appliance_id)

        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class XiaoduSwitch(XiaoduEntity, SwitchEntity):
    """表示一个 Xiaodu Switch 实体。"""

    def __init__(self, coordinator: XiaoduCoordinator, appliance_id: str) -> None:
        """初始化 Switch 实体。"""
        super().__init__(coordinator, appliance_id)
        device = coordinator.data.get(appliance_id)
        if device and any(t in SOCKET_TYPES for t in device.appliance_types):
            self._attr_device_class = SwitchDeviceClass.OUTLET
        else:
            self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool:
        """Switch 开启时返回 True。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return False
        turn_on = device.state_setting.get("turnOnState", {})
        return str(turn_on.get("value", "")).lower() == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """打开 Switch。

        根据规范 03 §3.3，coordinator 编排完整流程：
        API → 乐观更新（optimistic update）→ 加锁 → Bemfa 发布 → 延迟刷新。
        """
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="turnOn"),
            optimistic_state={"turnOnState": "on"},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关闭 Switch。"""
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="turnOff"),
            optimistic_state={"turnOnState": "off"},
        )
