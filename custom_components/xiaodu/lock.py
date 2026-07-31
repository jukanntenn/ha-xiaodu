"""Xiaodu 集成的 Lock 平台。"""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.xiaodu_types import Command
from .const import LOCK_TYPES
from .coordinator import XiaoduCoordinator
from .entity import XiaoduEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """从配置项（config entry）设置 Xiaodu Lock。"""
    coordinator: XiaoduCoordinator = config_entry.runtime_data
    added_device_ids: set[str] = set()

    @callback
    def _async_discover_entities() -> None:
        """发现并添加新的 Lock 实体（entity）。"""
        if not coordinator.data:
            return

        new_entities = []
        for appliance_id, device in coordinator.data.items():
            if appliance_id in added_device_ids:
                continue
            if not any(t in LOCK_TYPES for t in device.appliance_types):
                continue
            new_entities.append(XiaoduLock(coordinator, appliance_id))
            added_device_ids.add(appliance_id)

        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class XiaoduLock(XiaoduEntity, LockEntity):
    """表示一个 Xiaodu Lock 实体。"""

    @property
    def is_locked(self) -> bool:
        """Lock 上锁时返回 True。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return True
        state = device.state_setting
        # 先检查 lockState，再检查 turnOnState
        if "lockState" in state:
            lock_val = str(state["lockState"].get("value", "")).lower()
            return lock_val != "unlocked"
        turn_on = state.get("turnOnState", {})
        return str(turn_on.get("value", "")).lower() != "on"

    async def async_lock(self, **kwargs: Any) -> None:
        """为设备上锁。

        根据规范 03 §3.3，coordinator 编排完整流程：
        API → 乐观更新（optimistic update）→ 加锁 → Bemfa 发布 → 延迟刷新。
        """
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="turnOff"),
            optimistic_state={"turnOnState": "off"},
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """为设备解锁。"""
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="turnOn"),
            optimistic_state={"turnOnState": "on"},
        )
