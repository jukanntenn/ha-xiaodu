"""小度（Xiaodu）集成的数据更新协调器（DataUpdateCoordinator）。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.exceptions import XiaoduApiError, XiaoduAuthError, XiaoduNetworkError
from .api.xiaodu_types import Command, Device
from .const import CONF_ROOM_MAPPING, DOMAIN, SCAN_INTERVAL

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api.xiaodu_client import XiaoduAPI
    from .bemfa.sync_manager import BemfaDeviceSyncManager

_LOGGER = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]


class XiaoduCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """小度设备的协调器（coordinator）。"""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: XiaoduAPI,
        bemfa_sync_manager: BemfaDeviceSyncManager | None = None,
    ) -> None:
        """初始化协调器（coordinator）。"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )
        self.api_client = api_client
        self.bemfa_sync_manager = bemfa_sync_manager
        self._house_id: str = config_entry.data.get("house_id", "")
        self._locked_devices: dict[str, float] = {}
        self._device_lock_duration = 5
        self._manual_refresh_cooldown = 8
        self._last_manual_refresh = 0.0
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def _async_setup(self) -> None:
        """设置协调器（在首次刷新时调用一次）。"""

    async def _async_update_data(self) -> dict[str, Device]:
        """带重试逻辑地拉取最新设备数据。

        Returns:
            将 appliance_id 映射到 Device 的字典。

        Raises:
            ConfigEntryAuthFailed: 认证失败时抛出。
            UpdateFailed: 重试后 API 调用仍失败时抛出。
        """
        # 若最近刚发生过手动刷新，则跳过本次更新
        if (
            time.time() - self._last_manual_refresh < self._manual_refresh_cooldown
            and self.data
        ):
            return self.data

        # API 调用的重试逻辑
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                devices = await self.api_client.get_device_list(self._house_id)
                break
            except XiaoduAuthError as err:
                raise ConfigEntryAuthFailed from err
            except (XiaoduApiError, XiaoduNetworkError) as err:
                last_error = err
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
        else:
            raise UpdateFailed(f"Failed after {MAX_RETRIES} attempts: {last_error}")

        new_data = {d.appliance_id: d for d in devices}

        # 将设备列表变更同步到 Bemfa（巴法云）
        if self.bemfa_sync_manager:
            await self._handle_bemfa_sync(devices)

        # 将已存在设备的状态变更发布到 Bemfa
        if self.bemfa_sync_manager and self.data:
            await self._publish_state_changes(new_data)

        # 处理被锁定（locked）的设备——保留其本地状态
        current_time = time.time()
        self._locked_devices = {
            did: end_time
            for did, end_time in self._locked_devices.items()
            if end_time > current_time
        }

        if self.data and self._locked_devices:
            for device_id in new_data:
                if device_id in self._locked_devices:
                    old_device = self.data.get(device_id)
                    if old_device:
                        new_data[device_id] = old_device

        return new_data

    async def _handle_bemfa_sync(self, devices: list[Device]) -> None:
        """处理 Bemfa（巴法云）设备列表同步。"""
        if not self.bemfa_sync_manager:
            return
        room_mapping = self.config_entry.options.get(CONF_ROOM_MAPPING, {})
        try:
            await self.bemfa_sync_manager.sync_devices(devices, room_mapping)
        except Exception:
            _LOGGER.exception("Failed to sync devices with Bemfa")

    async def _publish_state_changes(self, new_data: dict[str, Device]) -> None:
        """将已存在设备的状态变更发布到 Bemfa（巴法云）。"""
        if not self.bemfa_sync_manager or not self.data:
            return
        for device_id, new_device in new_data.items():
            old_device = self.data.get(device_id)
            if old_device and old_device.state_setting != new_device.state_setting:
                try:
                    _ = await self.bemfa_sync_manager.update_device_state(
                        device_id, new_device.state_setting
                    )
                except Exception:  # noqa: BLE001 - Bemfa 发布失败仅记日志，不阻断控制流程
                    _LOGGER.debug("Failed to publish state change for %s", device_id)

    async def control_device(
        self,
        appliance_id: str,
        command: Command,
        optimistic_state: dict[str, Any] | None = None,
    ) -> bool:
        """控制设备，并编排完整的控制数据流（data flow）。

        按规范 03 §3.3 实现控制数据流：
            API 调用 → 乐观更新（optimistic update）→ 锁定 5 秒 → 发布到 Bemfa（新状态）
            → 延迟刷新（3 秒）。

        Args:
            appliance_id: 设备的 appliance ID。
            command: 控制命令（command）。
            optimistic_state: 在轮询确认前本地应用的乐观状态
                （例如 ``{"turnOnState": "on"}``）。

        Returns:
            API 调用成功时返回 True。
        """
        result = await self.api_client.control_device(appliance_id, command)

        if optimistic_state is not None:
            await self.apply_optimistic_state(appliance_id, optimistic_state)
        else:
            # 仍需调度一次延迟刷新，以确认命令已生效
            self._background_tasks.add(
                asyncio.create_task(self.async_request_refresh_after_delay(3.0))
            )

        return result

    async def handle_bemfa_command(
        self, appliance_id: str, commands: list[Command]
    ) -> None:
        """执行巴法云下行指令；setTemperature 由本地温度循环逼近。"""
        if not commands:
            return
        for command in commands:
            if command.action == "setTemperature":
                if not command.params:
                    _LOGGER.warning(
                        "setTemperature 指令缺少参数，已跳过: %s", command.action
                    )
                    continue
                await self._adjust_temperature(
                    appliance_id, cast("int", command.params["target"])
                )
            else:
                _ = await self.control_device(
                    appliance_id,
                    command,
                    optimistic_state=self._optimistic_state(command),
                )

    @staticmethod
    def _optimistic_state(command: Command) -> dict[str, Any] | None:
        """把下行指令映射为乐观状态（用于立即回传 /up）。"""
        action = command.action
        if action == "turnOn":
            return {"turnOnState": "on"}
        if action == "turnOff":
            return {"turnOnState": "off"}
        if action == "setBrightness":
            params = command.params
            if params is None:
                return None
            return {"turnOnState": "on", "brightness": params["attributeValue"]}
        if action == "setMode":
            params = command.params
            if params is None:
                return None
            return {"mode": params["mode"]}
        if action == "setFanSpeed":
            params = command.params
            if params is None:
                return None
            return {"fanSpeed": params["speed"]}
        return None

    async def _adjust_temperature(self, appliance_id: str, target: int) -> None:
        """用 temperatureUp/Down 循环逼近目标温度（上限 16 步）。"""
        device = self.data.get(appliance_id)
        if not device:
            return
        current = device.state_setting.get("temperature", {}).get("value")
        if current is None:
            return
        delta = target - int(current)
        if delta == 0:
            return
        action = "temperatureUp" if delta > 0 else "temperatureDown"
        for _ in range(min(abs(delta), 16)):
            _ = await self.control_device(appliance_id, Command(action=action))

    async def apply_optimistic_state(
        self,
        appliance_id: str,
        optimistic_state: dict[str, Any],
    ) -> None:
        """应用乐观状态（optimistic state），同步到 Bemfa，并调度一次延迟刷新。

        供 ``control_device`` 以及在应用单个乐观状态前发起多次直接
        API 调用的实体使用（例如按规范 09 §4.4 的空调温度升/降循环）。

        执行顺序：乐观更新 + 锁定（5 秒）→ 发布到 Bemfa（新状态）
        → 延迟刷新（3 秒）。
        """
        # 乐观更新 + 锁定（5 秒）——就地更新 self.data
        self.update_device_state_immediately(appliance_id, optimistic_state)

        # 如已启用，将新状态发布到 Bemfa
        if self.bemfa_sync_manager and self.data:
            device = self.data.get(appliance_id)
            if device:
                try:
                    _ = await self.bemfa_sync_manager.update_device_state(
                        appliance_id, device.state_setting
                    )
                except Exception:  # noqa: BLE001 - Bemfa 发布失败仅记日志，不阻断控制流程
                    _LOGGER.debug(
                        "Failed to sync control to Bemfa for %s", appliance_id
                    )

        # 调度一次延迟刷新（3 秒）以确认状态——即发即忘（fire and forget）
        self._background_tasks.add(
            asyncio.create_task(self.async_request_refresh_after_delay(3.0))
        )

    def update_device_state_immediately(
        self, device_id: str, new_state: dict[str, Any]
    ) -> None:
        """立即更新设备状态并对其加锁。"""
        if not self.data:
            return

        self._locked_devices[device_id] = time.time() + self._device_lock_duration

        device = self.data.get(device_id)
        if device:
            for key, value in new_state.items():
                if key in device.state_setting:
                    if isinstance(device.state_setting[key], dict):
                        device.state_setting[key]["value"] = value
                    else:
                        device.state_setting[key] = value
            self.async_update_listeners()

    async def async_request_refresh_after_delay(self, delay: float = 3.0) -> None:
        """在延迟后请求一次刷新。"""
        await asyncio.sleep(delay)
        self._last_manual_refresh = time.time()
        await self.async_request_refresh()

    @property
    def room_mapping(self) -> dict[str, str]:
        """返回配置选项（config options）中的房间映射（room mapping）。"""
        return self.config_entry.options.get(CONF_ROOM_MAPPING, {})

    @property
    def room_tokens(self) -> set[str]:
        """返回小度侧的全部房间名集合。

        实时取自当前设备数据，作为设备名房间 token 剥离的锚点全集，
        可跟随用户在小度 App 里的房间增删/改名。首次刷新前为空集。
        """
        return {d.room_name for d in (self.data or {}).values() if d.room_name}

    @property
    def devices(self) -> dict[str, Device]:
        """返回当前的设备数据。"""
        return self.data or {}

    async def async_cancel_background_tasks(self) -> None:
        """取消延迟刷新等后台任务（卸载时调用）。"""
        for task in self._background_tasks:
            _ = task.cancel()
        self._background_tasks.clear()
