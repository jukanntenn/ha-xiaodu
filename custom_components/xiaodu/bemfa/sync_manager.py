"""巴法云（Bemfa）设备同步管理器。"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from ..api.xiaodu_types import Device
from ..const import DEVICE_TYPE_SUFFIX_MAP
from .api_client import BemfaAPIClient
from .const import BEMFA_RETRY_INTERVAL_SECONDS
from .mqtt_client import BemfaMQTTClient
from .protocol import encode_state

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceMapping:
    """小度设备与巴法云 topic 之间的映射关系。"""

    xiaodu_appliance_id: str
    ha_unique_id: str = ""
    ha_entity_id: str = ""
    bemfa_topic: str | None = None
    bemfa_nickname: str | None = None
    bemfa_room: str | None = None
    device_type: str = ""
    friendly_name: str = ""
    room_name: str = ""
    last_sync_time: float = field(default_factory=time.time)
    sync_status: str = "pending"
    sync_error: str | None = None


class BemfaDeviceSyncManager:
    """管理与巴法云（Bemfa）的设备同步。"""

    def __init__(
        self,
        bemfa_uid: str,
        api_client: BemfaAPIClient,
        mqtt_client: BemfaMQTTClient,
    ) -> None:
        """初始化同步管理器。

        Args:
            bemfa_uid: 巴法云（Bemfa）的 UID。
            api_client: 巴法云 HTTP API 客户端。
            mqtt_client: 巴法云 MQTT 客户端。
        """
        self._bemfa_uid = bemfa_uid
        self._api_client = api_client
        self._mqtt_client = mqtt_client
        self._device_mapping: dict[str, DeviceMapping] = {}
        self._unsupported_devices: dict[str, list[str]] = {}

    @property
    def device_mapping(self) -> dict[str, DeviceMapping]:
        """返回设备映射。"""
        return dict(self._device_mapping)

    @property
    def api_client(self) -> BemfaAPIClient:
        """巴法云 HTTP API 客户端。"""
        return self._api_client

    @property
    def api_version(self) -> str:
        """当前生效的巴法云接口版本。"""
        return self._api_client.api_version

    @property
    def unsupported_devices(self) -> dict[str, list[str]]:
        """因类型不支持而未同步的设备（appliance_id -> types）。"""
        return dict(self._unsupported_devices)

    @property
    def mqtt_connected(self) -> bool:
        """MQTT 是否已连接。"""
        return self._mqtt_client.is_connected()

    def get_appliance_id_by_topic(self, topic: str) -> str | None:
        """按巴法云 topic 反查小度 appliance_id。"""
        for appliance_id, mapping in self._device_mapping.items():
            if mapping.bemfa_topic == topic:
                return appliance_id
        return None

    async def async_disconnect(self) -> None:
        """脱离事件循环断开底层 MQTT 客户端。

        即使 MQTT 从未连接过也可以安全调用。
        """
        await asyncio.to_thread(self._mqtt_client.disconnect)

    async def async_cleanup_all(self) -> None:
        """删除所有巴法云 topic 并断开连接。

        在集成卸载（unload）时调用，避免巴法云上出现孤立的 topic。
        topic 删除通过 HTTP API（aiohttp）完成，之后再断开 MQTT；
        单个 topic 删除失败仅记录日志，不会阻塞其余清理或 MQTT 断开。
        """
        for appliance_id in list(self._device_mapping.keys()):
            try:
                await self.remove_device(appliance_id)
            except Exception:
                _LOGGER.warning(
                    "Failed to remove Bemfa topic for %s", appliance_id, exc_info=True
                )
        await self.async_disconnect()

    def get_topic(self, appliance_id: str) -> str | None:
        """获取某设备的巴法云 topic。

        Args:
            appliance_id: 小度 appliance ID。

        Returns:
            巴法云 topic，若未建立映射则返回 None。
        """
        mapping = self._device_mapping.get(appliance_id)
        return mapping.bemfa_topic if mapping else None

    async def sync_devices(
        self,
        devices: list[Device],
        room_mapping: dict[str, str],
    ) -> None:
        """将设备列表与巴法云同步。

        检测新增和移除的设备，并相应地创建/删除 topic。

        Args:
            devices: 当前的小度设备列表。
            room_mapping: 房间映射 {xiaodu_room: ha_area}。
        """
        current_ids = {d.appliance_id for d in devices}
        self._unsupported_devices = {
            d.appliance_id: list(d.appliance_types)
            for d in devices
            if self._get_primary_type(d.appliance_types) is None
        }
        mapped_ids = set(self._device_mapping.keys())

        # 新增的设备 + 退避到期的失败设备
        new_ids = current_ids - mapped_ids
        retry_ids = set(new_ids)
        for appliance_id, mapping in self._device_mapping.items():
            if (
                mapping.sync_status == "error"
                and time.time() - mapping.last_sync_time
                >= BEMFA_RETRY_INTERVAL_SECONDS
            ):
                retry_ids.add(appliance_id)

        for device in devices:
            if device.appliance_id in retry_ids:
                await self._add_device(device, room_mapping)

        # 移除的设备
        removed_ids = mapped_ids - current_ids
        for appliance_id in removed_ids:
            await self.remove_device(appliance_id)

    async def _add_device(self, device: Device, room_mapping: dict[str, str]) -> None:
        """向巴法云添加一个新设备。

        Args:
            device: 小度设备。
            room_mapping: 房间映射。
        """
        device_type = self._get_primary_type(device.appliance_types)
        if not device_type:
            _LOGGER.debug(
                "Skipping device %s: no supported bemfa type",
                device.appliance_id,
            )
            return

        topic = self._generate_topic(device.appliance_id, device_type)
        mapped_room = room_mapping.get(device.room_name, device.room_name)
        nickname = self._generate_nickname(device, room_mapping)

        result = await self._api_client.create_topic(topic, nickname)
        created = result.success
        if created:
            await self._api_client.change_topic_room([topic], mapped_room)
            await self._api_client.change_topic_group([topic], mapped_room)
            self._mqtt_client.subscribe(topic)

        self._device_mapping[device.appliance_id] = DeviceMapping(
            xiaodu_appliance_id=device.appliance_id,
            ha_unique_id=f"xiaodu_{device.appliance_id}",
            ha_entity_id="",
            bemfa_topic=topic if created else None,
            bemfa_nickname=nickname,
            bemfa_room=mapped_room,
            device_type=device_type,
            friendly_name=device.friendly_name,
            room_name=device.room_name,
            last_sync_time=time.time(),
            sync_status=(
                "synced"
                if created
                else "permanent_error" if result.code == 40009 else "error"
            ),
            sync_error=result.error_msg,
        )
        _LOGGER.info("Added Bemfa device: %s -> %s", device.appliance_id, topic)

    async def remove_device(self, appliance_id: str) -> None:
        """从巴法云移除一个设备。

        Args:
            appliance_id: 小度 appliance ID。
        """
        mapping = self._device_mapping.get(appliance_id)
        if not mapping:
            return
        if mapping.bemfa_topic:
            await self._api_client.delete_topic(mapping.bemfa_topic)
            self._mqtt_client.unsubscribe(mapping.bemfa_topic)
        del self._device_mapping[appliance_id]
        _LOGGER.info("Removed Bemfa device: %s", appliance_id)

    async def update_device_state(self, appliance_id: str, state: dict) -> bool:
        """更新巴法云上的设备状态。

        Args:
            appliance_id: 小度 appliance ID。
            state: 新的状态字典。

        Returns:
            发布成功返回 True；未映射/未连接/无法编码返回 False。
        """
        mapping = self._device_mapping.get(appliance_id)
        if not mapping or not mapping.bemfa_topic or not mapping.device_type:
            return False
        payload = encode_state(mapping.device_type, state)
        if payload is None:
            return False
        published = await asyncio.to_thread(
            self._mqtt_client.publish, f"{mapping.bemfa_topic}/up", payload
        )
        if published:
            mapping.last_sync_time = time.time()
            mapping.sync_status = "synced"
        return published

    @staticmethod
    def _generate_topic(appliance_id: str, device_type: str) -> str:
        """根据 appliance ID 生成巴法云 topic。

        Rules:
            1. 去除 appliance_id 的前导零
            2. 将下划线 _ 替换为 U
            3. 追加索引 0
            4. 追加 3 位设备类型代码

        Args:
            appliance_id: 小度 appliance ID。
            device_type: 设备类型字符串（例如 "LIGHT"）。

        Returns:
            巴法云 topic 字符串。
        """
        # 去除前导零
        cleaned = appliance_id.lstrip("0") or "0"
        # 将下划线替换为 U
        cleaned = cleaned.replace("_", "U")
        # 获取类型后缀
        suffix = DEVICE_TYPE_SUFFIX_MAP.get(device_type, "006")
        return f"{cleaned}0{suffix}"

    @staticmethod
    def _generate_nickname(device: Device, room_mapping: dict[str, str]) -> str:
        """为设备生成巴法云昵称。

        格式：映射后的房间名 + 设备友好名称。

        Args:
            device: 小度设备。
            room_mapping: 房间映射。

        Returns:
            昵称字符串。
        """
        mapped_room = room_mapping.get(device.room_name, device.room_name)
        return f"{mapped_room}{device.friendly_name}"

    @staticmethod
    def _get_primary_type(appliance_types: list[str]) -> str | None:
        """获取用于巴法云同步的主设备类型。

        Args:
            appliance_types: appliance 类型字符串列表。

        Returns:
            主类型，若不支持则返回 None。
        """
        for app_type in appliance_types:
            if app_type in DEVICE_TYPE_SUFFIX_MAP:
                return app_type
        return None
