"""巴法云（Bemfa）设备同步管理器。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr

from ..const import DEVICE_TYPE_SUFFIX_MAP, DOMAIN
from ..naming import strip_room
from .const import (
    BEMFA_RETRY_INTERVAL_SECONDS,
    BEMFA_TOPIC_HASH_LENGTH,
    BEMFA_TOPIC_PREFIX,
)
from .protocol import encode_state

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry

    from ..api.xiaodu_types import Device
    from .api_client import BemfaAPIClient
    from .mqtt_client import BemfaMQTTClient

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

    _hass: HomeAssistant

    def __init__(
        self,
        hass: HomeAssistant,
        bemfa_uid: str,
        api_client: BemfaAPIClient,
        mqtt_client: BemfaMQTTClient,
    ) -> None:
        """初始化同步管理器。

        Args:
            hass: Home Assistant 实例，用于访问 device/area registry，
                让巴法云昵称与房间跟随用户在 HA 的实际分配。
            bemfa_uid: 巴法云（Bemfa）的 UID。
            api_client: 巴法云 HTTP API 客户端。
            mqtt_client: 巴法云 MQTT 客户端。
        """
        self._hass = hass
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

        # 小度侧的全部房间名——作为设备名房间 token 剥离的锚点全集。
        # 实时取自当前设备列表，可跟随用户在小度 App 里的房间改动。
        room_tokens = {d.room_name for d in devices if d.room_name}

        # 首次同步时检测并清理巴法云上的孤儿 topic（前缀匹配但不在当前映射中）
        if not mapped_ids:
            await self._cleanup_orphans()

        # 新增的设备 + 退避到期的失败设备
        new_ids = current_ids - mapped_ids
        retry_ids = set(new_ids)
        for appliance_id, mapping in self._device_mapping.items():
            if (
                mapping.sync_status == "error"
                and time.time() - mapping.last_sync_time >= BEMFA_RETRY_INTERVAL_SECONDS
            ):
                retry_ids.add(appliance_id)

        for device in devices:
            if device.appliance_id in retry_ids:
                await self._add_device(device, room_mapping, room_tokens)

        # 移除的设备
        removed_ids = mapped_ids - current_ids
        for appliance_id in removed_ids:
            await self.remove_device(appliance_id)

        # 昵称跟随：期望昵称与实际不一致时更新（映射变更 / 百度改名）
        await self._sync_nicknames(devices, room_mapping, room_tokens)

    async def _cleanup_orphans(self) -> None:
        """删除巴法云上带集成前缀但不在当前映射中的孤儿 topic。

        仅在首次同步（无映射）时调用，尽力而为：任何失败仅记录日志，
        绝不阻塞设备创建主流程。
        """
        try:
            topics = await self._api_client.list_topics()
        except Exception:
            _LOGGER.warning("Bemfa orphan scan failed", exc_info=True)
            return
        if topics is None:
            return
        managed = {
            mapping.bemfa_topic
            for mapping in self._device_mapping.values()
            if mapping.bemfa_topic
        }
        for topic in topics:
            if self.is_integration_topic(topic) and topic not in managed:
                _LOGGER.warning("Deleting orphan Bemfa topic: %s", topic)
                try:
                    _ = await self._api_client.delete_topic(topic)
                except Exception:
                    _LOGGER.warning(
                        "Failed to delete orphan topic %s", topic, exc_info=True
                    )

    async def _sync_nicknames(
        self,
        devices: list[Device],
        room_mapping: dict[str, str],
        room_tokens: set[str],
    ) -> None:
        """同步期望昵称到巴法云（modifyName），仅在昵称变化时调用。"""
        for device in devices:
            mapping = self._device_mapping.get(device.appliance_id)
            if not mapping or not mapping.bemfa_topic:
                continue
            expected = self._generate_nickname(device, room_mapping, room_tokens)
            if mapping.bemfa_nickname == expected:
                continue
            try:
                ok = await self._api_client.modify_name(mapping.bemfa_topic, expected)
            except Exception:
                _LOGGER.warning(
                    "Failed to update nickname for %s",
                    device.appliance_id,
                    exc_info=True,
                )
                continue
            if ok:
                mapping.bemfa_nickname = expected

    async def _add_device(
        self,
        device: Device,
        room_mapping: dict[str, str],
        room_tokens: set[str],
    ) -> None:
        """向巴法云添加一个新设备。

        Args:
            device: 小度设备。
            room_mapping: 房间映射。
            room_tokens: 小度侧全部房间名，用于设备名房间 token 剥离。
        """
        device_type = self._get_primary_type(device.appliance_types)
        if not device_type:
            _LOGGER.debug(
                "Skipping device %s: no supported bemfa type",
                device.appliance_id,
            )
            return

        topic = self._generate_topic(device.appliance_id, device_type)
        mapped_room = self._resolve_room_for_topic(device, room_mapping)
        nickname = self._generate_nickname(device, room_mapping, room_tokens)

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
                else "permanent_error"
                if result.code == 40009
                else "error"
            ),
            sync_error=result.error_msg,
        )
        _LOGGER.info("Added Bemfa device: %s -> %s", device.appliance_id, topic)

    async def remove_device(self, appliance_id: str) -> None:
        """从巴法云移除一个设备。

        防御性校验：仅删除带集成前缀的 topic，绝不触碰用户自建设备。

        Args:
            appliance_id: 小度 appliance ID。
        """
        mapping = self._device_mapping.get(appliance_id)
        if not mapping:
            return
        if mapping.bemfa_topic:
            if not self.is_integration_topic(mapping.bemfa_topic):
                _LOGGER.warning(
                    "Refusing to delete non-integration topic %s",
                    mapping.bemfa_topic,
                )
            else:
                _ = await self._api_client.delete_topic(mapping.bemfa_topic)
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

        格式：{前缀}{md5(appliance_id) 前 12 位}{3 位设备类型代码}。

        规则：
            1. 前缀标识集成归属（删除/操作前据此过滤）
            2. 哈希由 appliance_id 确定性生成——改名/改昵称不影响关联
            3. 后缀用于巴法云设备类型识别（末尾 3 位）

        Args:
            appliance_id: 小度 appliance ID。
            device_type: 设备类型字符串（例如 "LIGHT"）。

        Returns:
            巴法云 topic 字符串。
        """
        # S324: md5 仅作确定性混淆（非安全用途），社区同款
        digest = hashlib.md5(  # noqa: S324
            appliance_id.encode("utf-8")
        ).hexdigest()[:BEMFA_TOPIC_HASH_LENGTH]
        suffix = DEVICE_TYPE_SUFFIX_MAP.get(device_type, "006")
        return f"{BEMFA_TOPIC_PREFIX}{digest}{suffix}"

    @staticmethod
    def is_integration_topic(topic: str) -> bool:
        """判断 topic 是否为本集成创建的（带集成前缀）。"""
        return topic.startswith(BEMFA_TOPIC_PREFIX)

    def _resolve_ha_device(self, appliance_id: str) -> DeviceEntry | None:
        """通过 appliance_id 反查 HA device registry 里的设备条目。

        设备 identifiers 为 ``{(DOMAIN, appliance_id)}``（见 entity.py）。
        首次同步时设备尚未建立（forward_entry_setups 晚于首刷），返回 None，
        由调用方走 room_mapping fallback。

        Args:
            appliance_id: 小度 appliance ID。

        Returns:
            DeviceEntry；设备未建立时返回 None。
        """
        registry = dr.async_get(self._hass)
        return registry.async_get_device(identifiers={(DOMAIN, appliance_id)})

    def _resolve_ha_area_name(self, device_entry: DeviceEntry | None) -> str:
        """从 device_entry 的 area_id 反查 HA 区域名。

        Args:
            device_entry: HA 设备条目。

        Returns:
            区域名；未分配区域或 device_entry 为 None 时返回空串。
        """
        if device_entry is None or not device_entry.area_id:
            return ""
        area = ar.async_get(self._hass).async_get_area(device_entry.area_id)
        return area.name if area is not None else ""

    def _resolve_ha_device_name(
        self,
        device_entry: DeviceEntry | None,
        device: Device,
        room_tokens: set[str],
    ) -> str:
        """解析设备的实际显示名并剥离房间词。

        优先用用户在 HA 改的 ``name_by_user``；否则回退到 device.name
        （由 entity.py 的 device_info 设为已剥离房间前缀的值，二次剥离幂等）；
        device_entry 为 None（首刷）时回退到小度原始 friendly_name。

        无论哪个来源，都过一遍 strip_room——用户改名可能重新带入房间词，
        而原始名必然含房间前缀。

        Args:
            device_entry: HA 设备条目（可能为 None）。
            device: 小度设备（用于 fallback 到原始 friendly_name/room_name）。
            room_tokens: 小度侧全部房间名，剥离锚点。

        Returns:
            剥离房间词后的设备显示名。
        """
        if device_entry is not None:
            raw_name = device_entry.name_by_user or device_entry.name or ""
        else:
            raw_name = device.friendly_name
        room_name = device.room_name
        mapped_room = self._resolve_ha_area_name(device_entry) or room_name
        return strip_room(raw_name, room_name, mapped_room, room_tokens)

    def _generate_nickname(
        self,
        device: Device,
        room_mapping: dict[str, str],
        room_tokens: set[str],
    ) -> str:
        """为设备生成巴法云昵称。

        优先跟随 HA device 的实际区域与显示名（让用户在「命名与分配」
        步骤或 HA 设备页的改动反映到巴法云）；device_entry 尚未建立时
        （首次同步，早于 forward_entry_setups）回退到 room_mapping 派生。

        格式：区域名 + 剥离房间 token 后的设备名。

        Args:
            device: 小度设备。
            room_mapping: 房间映射（首刷 fallback 用）。
            room_tokens: 小度侧全部房间名，用于剥离设备名中嵌套的
                他人房间词（如设备在「主卧」却叫「主卫灯带」）。

        Returns:
            昵称字符串。
        """
        device_entry = self._resolve_ha_device(device.appliance_id)
        if device_entry is not None:
            area_name = self._resolve_ha_area_name(device_entry)
            name = self._resolve_ha_device_name(device_entry, device, room_tokens)
            return f"{area_name}{name}"
        # 首刷 fallback：device_entry 未建立，用 room_mapping 派生
        mapped_room = room_mapping.get(device.room_name, device.room_name)
        stripped = strip_room(
            device.friendly_name, device.room_name, mapped_room, room_tokens
        )
        return f"{mapped_room}{stripped}"

    def _resolve_room_for_topic(
        self,
        device: Device,
        room_mapping: dict[str, str],
    ) -> str:
        """解析巴法云 topic 的 room 字段值。

        优先用 HA device 的实际区域名（跟随用户分配）；device_entry 未建立
        时回退到 room_mapping（首次同步）。

        Args:
            device: 小度设备。
            room_mapping: 房间映射（首刷 fallback 用）。

        Returns:
            区域名（用于巴法云 room/group 字段）。
        """
        device_entry = self._resolve_ha_device(device.appliance_id)
        if device_entry is not None:
            area_name = self._resolve_ha_area_name(device_entry)
            if area_name:
                return area_name
        return room_mapping.get(device.room_name, device.room_name)

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
