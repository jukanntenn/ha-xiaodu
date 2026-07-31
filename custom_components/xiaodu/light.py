"""Xiaodu 集成的 Light 平台。"""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.xiaodu_types import Command
from .const import LIGHT_TYPES
from .coordinator import XiaoduCoordinator
from .entity import XiaoduEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """从配置项（config entry）设置 Xiaodu Light。"""
    coordinator: XiaoduCoordinator = config_entry.runtime_data
    added_device_ids: set[str] = set()

    @callback
    def _async_discover_entities() -> None:
        """发现并添加新的 Light 实体（entity）。"""
        if not coordinator.data:
            return

        new_entities = []
        for appliance_id, device in coordinator.data.items():
            if appliance_id in added_device_ids:
                continue
            if not any(t in LIGHT_TYPES for t in device.appliance_types):
                continue
            new_entities.append(XiaoduLight(coordinator, appliance_id))
            added_device_ids.add(appliance_id)

        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class XiaoduLight(XiaoduEntity, LightEntity):
    """表示一个 Xiaodu Light 实体。"""

    _attr_icon = "mdi:lightbulb"

    def __init__(self, coordinator: XiaoduCoordinator, appliance_id: str) -> None:
        """初始化 Light 实体。"""
        super().__init__(coordinator, appliance_id)
        self._color_mode: ColorMode = ColorMode.ONOFF
        self._effect_map: dict[str, str] = {}
        self._update_color_mode()

    @callback
    def _handle_coordinator_update(self) -> None:
        """处理来自 coordinator 的更新数据。"""
        self._update_color_mode()
        super()._handle_coordinator_update()

    def _update_color_mode(self) -> None:
        """根据设备能力更新颜色模式（color mode）。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return
        state = device.state_setting
        has_brightness = "brightness" in state
        has_color_temp = "colorTemperatureInKelvin" in state

        if has_brightness and has_color_temp:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._color_mode = ColorMode.COLOR_TEMP
        elif has_brightness:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._color_mode = ColorMode.ONOFF

        if "mode" in state:
            mode_data = state["mode"]
            value_range_map = mode_data.get("valueRangeMap", {})
            self._effect_map = value_range_map
            self._attr_effect_list = list(value_range_map.values())
            self._attr_supported_features = LightEntityFeature.EFFECT

    @property
    def is_on(self) -> bool:
        """Light 开启时返回 True。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return False
        turn_on = device.state_setting.get("turnOnState", {})
        return str(turn_on.get("value", "")).lower() == "on"

    @property
    def brightness(self) -> int | None:
        """返回亮度（0-255）。"""
        if self._color_mode == ColorMode.ONOFF:
            return None
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return None
        brightness_data = device.state_setting.get("brightness", {})
        value = brightness_data.get("value")
        if value is None:
            return None
        return round(int(value) / 100 * 255)

    @property
    def color_temp_kelvin(self) -> int | None:
        """返回色温（单位：开尔文）。"""
        if self._color_mode != ColorMode.COLOR_TEMP:
            return None
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return None
        ct_data = device.state_setting.get("colorTemperatureInKelvin", {})
        value = ct_data.get("value")
        range_map = ct_data.get("valueKelvinRangeMap", {})
        if value is None or not range_map:
            return None
        ct_min = range_map.get("min", 2000)
        ct_max = range_map.get("max", 6535)
        ct_range = ct_max - ct_min
        return round(int(value) / 100 * ct_range) + ct_min

    @property
    def min_color_temp_kelvin(self) -> int:
        """返回最低色温。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return 2000
        ct_data = device.state_setting.get("colorTemperatureInKelvin", {})
        range_map = ct_data.get("valueKelvinRangeMap", {})
        return range_map.get("min", 2000)

    @property
    def max_color_temp_kelvin(self) -> int:
        """返回最高色温。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return 6535
        ct_data = device.state_setting.get("colorTemperatureInKelvin", {})
        range_map = ct_data.get("valueKelvinRangeMap", {})
        return range_map.get("max", 6535)

    @property
    def effect(self) -> str | None:
        """返回当前效果（effect）。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device or not self._effect_map:
            return None
        mode_data = device.state_setting.get("mode", {})
        value = mode_data.get("value")
        return self._effect_map.get(value)

    @property
    def color_mode(self) -> ColorMode:
        """返回颜色模式。"""
        return self._color_mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """打开 Light。

        根据规范 03 §3.3，coordinator 编排完整流程：
        API → 乐观更新（optimistic update）→ 加锁 → Bemfa 发布 → 延迟刷新。
        """
        if ATTR_BRIGHTNESS in kwargs:
            brightness = round(int(kwargs[ATTR_BRIGHTNESS]) / 255 * 100)
            await self.coordinator.control_device(
                self._appliance_id,
                Command(
                    action="setBrightness",
                    params={"attributeValue": brightness},
                ),
                optimistic_state={"turnOnState": "on", "brightness": brightness},
            )
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp = kwargs[ATTR_COLOR_TEMP_KELVIN]
            ct_min = self.min_color_temp_kelvin
            ct_max = self.max_color_temp_kelvin
            ct_range = ct_max - ct_min
            value = round((color_temp - ct_min) / ct_range * 100)
            await self.coordinator.control_device(
                self._appliance_id,
                Command(
                    action="setColorTemperatureInKelvin",
                    params={"attributeValue": value},
                ),
                optimistic_state={
                    "turnOnState": "on",
                    "colorTemperatureInKelvin": value,
                },
            )
        elif ATTR_EFFECT in kwargs:
            effect_name = kwargs[ATTR_EFFECT]
            mode_key = None
            for key, val in self._effect_map.items():
                if val == effect_name:
                    mode_key = key
                    break
            if mode_key:
                await self.coordinator.control_device(
                    self._appliance_id,
                    Command(
                        action="lightSetMode",
                        params={"mode": mode_key},
                    ),
                    optimistic_state={"turnOnState": "on", "mode": mode_key},
                )
        else:
            await self.coordinator.control_device(
                self._appliance_id,
                Command(action="turnOn"),
                optimistic_state={"turnOnState": "on"},
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关闭 Light。"""
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="turnOff"),
            optimistic_state={"turnOnState": "off"},
        )
