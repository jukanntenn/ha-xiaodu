"""小度（Xiaodu）集成的基类实体（entity）。"""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XiaoduCoordinator


class XiaoduEntity(CoordinatorEntity[XiaoduCoordinator]):
    """小度设备的基类实体（entity）。"""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: XiaoduCoordinator,
        appliance_id: str,
    ) -> None:
        """初始化实体（entity）。

        Args:
            coordinator: 数据协调器（data coordinator）。
            appliance_id: 小度设备的 appliance ID。
        """
        super().__init__(coordinator)
        self._appliance_id = appliance_id
        self._attr_unique_id = f"{DOMAIN}_{appliance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """返回设备信息。"""
        device = self.coordinator.data.get(self._appliance_id)
        if device:
            mapped_room = self.coordinator.room_mapping.get(
                device.room_name, device.room_name
            )
            return DeviceInfo(
                identifiers={(DOMAIN, self._appliance_id)},
                name=device.friendly_name,
                manufacturer="Xiaodu",
                model=device.appliance_types[0] if device.appliance_types else None,
                suggested_area=mapped_room or None,
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self._appliance_id)},
            name=self._appliance_id,
            manufacturer="Xiaodu",
        )

    @property
    def appliance_id(self) -> str:
        """返回 appliance ID。"""
        return self._appliance_id

    @callback
    def _handle_coordinator_update(self) -> None:
        """处理来自协调器（coordinator）的更新数据。

        按规范 03 §2.5：从 ``coordinator.data[appliance_id]`` 刷新实体属性
        并写入新状态。子类可以重写此方法以更新额外属性
        （例如颜色模式（color mode））。
        """
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """返回实体是否可用。"""
        return super().available and self._appliance_id in (self.coordinator.data or {})
