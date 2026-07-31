"""Xiaodu 集成的 Button 平台。"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.xiaodu_types import Command
from .const import BUTTON_TYPES
from .coordinator import XiaoduCoordinator
from .entity import XiaoduEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """从配置项（config entry）设置 Xiaodu Button。"""
    coordinator: XiaoduCoordinator = config_entry.runtime_data
    added_device_ids: set[str] = set()

    @callback
    def _async_discover_entities() -> None:
        """发现并添加新的 Button 实体（entity）。"""
        if not coordinator.data:
            return

        new_entities = []
        for appliance_id, device in coordinator.data.items():
            if appliance_id in added_device_ids:
                continue
            if not any(t in BUTTON_TYPES for t in device.appliance_types):
                continue
            new_entities.append(XiaoduButton(coordinator, appliance_id))
            added_device_ids.add(appliance_id)

        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class XiaoduButton(XiaoduEntity, ButtonEntity):
    """表示一个 Xiaodu Button 实体。"""

    _attr_icon = "mdi:gesture-tap-button"
    _attr_should_poll = False

    async def async_press(self) -> None:
        """处理按钮按下事件。

        根据规范 03 §3.3，coordinator 编排完整流程。
        Button 没有持久状态，因此不传入 optimistic_state。
        """
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="turnOn"),
        )
