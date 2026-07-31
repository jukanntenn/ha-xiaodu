"""Xiaodu 集成的 Climate 平台。"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.xiaodu_types import Command
from .const import CLIMATE_TYPES
from .coordinator import XiaoduCoordinator
from .entity import XiaoduEntity

PARALLEL_UPDATES = 0

FAN_MODE_MAP: dict[int, str] = {
    1: FAN_LOW,
    2: FAN_MEDIUM,
    3: FAN_HIGH,
    4: FAN_AUTO,
}

XIAODU_MODE_MAP: dict[str, HVACMode] = {
    "auto": HVACMode.AUTO,
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "dehumidification": HVACMode.DRY,
    "fan": HVACMode.FAN_ONLY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """从配置项（config entry）设置 Xiaodu Climate。"""
    coordinator: XiaoduCoordinator = config_entry.runtime_data
    added_device_ids: set[str] = set()

    @callback
    def _async_discover_entities() -> None:
        """发现并添加新的 Climate 实体（entity）。"""
        if not coordinator.data:
            return

        new_entities = []
        for appliance_id, device in coordinator.data.items():
            if appliance_id in added_device_ids:
                continue
            if not any(t in CLIMATE_TYPES for t in device.appliance_types):
                continue
            new_entities.append(XiaoduClimate(coordinator, appliance_id))
            added_device_ids.add(appliance_id)

        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class XiaoduClimate(XiaoduEntity, ClimateEntity):
    """表示一个 Xiaodu Climate 设备。"""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 32
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
    )
    _attr_hvac_modes = (
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    )
    _attr_fan_modes = (FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO)

    @property
    def hvac_mode(self) -> HVACMode:
        """返回当前的 HVAC 模式（hvac_mode）。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return HVACMode.OFF
        turn_on = device.state_setting.get("turnOnState", {})
        if str(turn_on.get("value", "")).lower() != "on":
            return HVACMode.OFF
        mode_data = device.state_setting.get("mode", {})
        mode_value = str(mode_data.get("value", "cool")).lower()
        return XIAODU_MODE_MAP.get(mode_value, HVACMode.COOL)

    @property
    def current_temperature(self) -> float | None:
        """返回当前温度。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return None
        temp_data = device.state_setting.get("temperature", {})
        return temp_data.get("value")

    @property
    def target_temperature(self) -> float | None:
        """返回目标温度。"""
        return self.current_temperature

    @property
    def fan_mode(self) -> str | None:
        """返回风扇模式（fan mode）。"""
        device = self.coordinator.data.get(self._appliance_id)
        if not device:
            return None
        fan_data = device.state_setting.get("fanSpeed", {})
        speed = fan_data.get("value")
        if speed is None:
            return FAN_MEDIUM
        return FAN_MODE_MAP.get(int(speed), FAN_MEDIUM)

    async def async_turn_on(self) -> None:
        """打开实体。

        根据规范 03 §3.3，coordinator 编排完整流程：
        API → 乐观更新（optimistic update）→ 加锁 → Bemfa 发布 → 延迟刷新。
        """
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="turnOn"),
            optimistic_state={"turnOnState": "on"},
        )

    async def async_turn_off(self) -> None:
        """关闭实体。"""
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="turnOff"),
            optimistic_state={"turnOnState": "off"},
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """设置新的目标温度。

        根据规范 09 §4.4：Xiaodu API 仅支持温度上调/下调的步进，
        因此我们先发起 N 次直接 API 调用，再通过 ``apply_optimistic_state``
        应用一次乐观状态（optimistic state）。
        """
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        current = self.target_temperature or 26
        diff = int(temperature - current)
        if diff > 0:
            for _ in range(diff):
                await self.coordinator.api_client.control_device(
                    self._appliance_id,
                    Command(action="temperatureUp"),
                )
        elif diff < 0:
            for _ in range(-diff):
                await self.coordinator.api_client.control_device(
                    self._appliance_id,
                    Command(action="temperatureDown"),
                )
        await self.coordinator.apply_optimistic_state(
            self._appliance_id,
            {"temperature": int(temperature)},
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """设置新的 HVAC 模式。"""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return

        # 确保设备已开启
        device = self.coordinator.data.get(self._appliance_id)
        if device:
            turn_on = device.state_setting.get("turnOnState", {})
            if str(turn_on.get("value", "")).lower() != "on":
                await self.coordinator.control_device(
                    self._appliance_id,
                    Command(action="turnOn"),
                    optimistic_state={"turnOnState": "on"},
                )

        # 将 HVAC 模式映射为 xiaodu 的 mode 字符串
        mode_reverse = {v: k for k, v in XIAODU_MODE_MAP.items()}
        mode_str = mode_reverse.get(hvac_mode, "cool")
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="setMode", params={"mode": mode_str}),
            optimistic_state={"turnOnState": "on", "mode": mode_str},
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """设置新的风扇模式。"""
        fan_reverse = {v: k for k, v in FAN_MODE_MAP.items()}
        speed = fan_reverse.get(fan_mode, 2)
        await self.coordinator.control_device(
            self._appliance_id,
            Command(action="setFanSpeed", params={"speed": speed}),
            optimistic_state={"fanSpeed": speed},
        )
