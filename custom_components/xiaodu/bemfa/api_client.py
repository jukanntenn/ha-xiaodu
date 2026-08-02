"""巴法云（Bemfa）HTTP API 客户端。"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, cast

from aiohttp import ClientError, ClientSession

from .const import (
    BEMFA_ALL_TOPIC_URL,
    BEMFA_CHANGE_GROUP_URL,
    BEMFA_CHANGE_ROOM_URL,
    BEMFA_CREATE_TOPIC_URL,
    BEMFA_CREATE_TOPIC_V1_URL,
    BEMFA_DELETE_TOPIC_URL,
    BEMFA_DEVICE_CONTROL_URL,
    BEMFA_DEVICE_LIST_URL,
    BEMFA_MODIFY_NAME_URL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CreateTopicResult:
    """createTopic 结果。"""

    success: bool
    error_msg: str | None = None
    code: int | None = None


@dataclass
class BemfaDevice:
    """巴法云设备（/vb/ha/v1/device 列表项）。"""

    topic: str
    device_type: str = ""
    name: str = ""


class BemfaAPIClient:
    """巴法云（Bemfa）的 HTTP API 客户端。"""

    def __init__(
        self,
        bemfa_uid: str,
        session: ClientSession,
        secret_id: str = "",
        secret_key: str = "",
        *,
        create_topic_url: str = BEMFA_CREATE_TOPIC_URL,
        create_topic_v1_url: str = BEMFA_CREATE_TOPIC_V1_URL,
        delete_topic_url: str = BEMFA_DELETE_TOPIC_URL,
        change_room_url: str = BEMFA_CHANGE_ROOM_URL,
        change_group_url: str = BEMFA_CHANGE_GROUP_URL,
        modify_name_url: str = BEMFA_MODIFY_NAME_URL,
        all_topic_url: str = BEMFA_ALL_TOPIC_URL,
        device_list_url: str = BEMFA_DEVICE_LIST_URL,
        device_control_url: str = BEMFA_DEVICE_CONTROL_URL,
    ) -> None:
        """初始化 API 客户端。

        Args:
            bemfa_uid: 巴法云（Bemfa）的 UID。
            session: aiohttp 客户端会话。
            secret_id: 巴法云 API 密钥对之 secretID（v2 接口创建/删除 topic 必填）。
            secret_key: 巴法云 API 密钥对之 secretKey（v2 接口创建/删除 topic 必填）。
            create_topic_url: v2 createTopic 端点（默认生产地址，可注入测试）。
            create_topic_v1_url: v1 createTopic 端点（默认生产地址，可注入测试）。
            delete_topic_url: deleteTopic 端点（默认生产地址，可注入测试）。
            change_room_url: 修改房间端点（默认生产地址，可注入测试）。
            change_group_url: 修改分组端点（默认生产地址，可注入测试）。
        """
        self._bemfa_uid: str = bemfa_uid
        self._session: ClientSession = session
        self._secret_id: str = secret_id
        self._secret_key: str = secret_key
        self._create_topic_url: str = create_topic_url
        self._create_topic_v1_url: str = create_topic_v1_url
        self._delete_topic_url: str = delete_topic_url
        self._change_room_url: str = change_room_url
        self._change_group_url: str = change_group_url
        self._modify_name_url: str = modify_name_url
        self._all_topic_url: str = all_topic_url
        self._device_list_url: str = device_list_url
        self._device_control_url: str = device_control_url

    @property
    def api_version(self) -> str:
        """当前生效的接口版本。"""
        return "v2" if self._secret_id and self._secret_key else "v1"

    @property
    def _encoded_open_id(self) -> str:
        """/vb/ha/v1 系列接口的 openID：base64 编码的用户私钥。

        事实依据：behome api.py `_encoded_private_key`。
        """
        return base64.b64encode(self._bemfa_uid.encode("utf-8")).decode("utf-8")

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """发起 HTTP 请求。"""
        try:
            async with self._session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
                if not isinstance(data, dict):
                    _LOGGER.warning("Bemfa API response is not a dict")
                    return None
                return data
        except ClientError as err:
            _LOGGER.warning("Bemfa API request failed: %s", err)
            return None
        except (TimeoutError, ValueError) as err:
            _LOGGER.warning("Bemfa API response error: %s", err)
            return None

    async def create_topic(self, topic: str, name: str) -> CreateTopicResult:
        """创建主题；无 secret 走 v1，有 secret 走 v2。"""
        if self.api_version == "v2":
            url = self._create_topic_url
            payload = {
                "uid": self._bemfa_uid,
                "topic": topic,
                "type": 1,
                "name": name,
                "secretID": self._secret_id,
                "secretKey": self._secret_key,
            }
        else:
            url = self._create_topic_v1_url
            payload = {
                "uid": self._bemfa_uid,
                "topic": topic,
                "type": 1,
                "name": name,
            }
        data = await self._request("post", url, json=payload)
        if not data:
            return CreateTopicResult(success=False, error_msg="无响应或请求异常")
        code = data.get("code")
        if code in (0, 40006):
            _LOGGER.debug("Created Bemfa topic: %s (code=%s)", topic, code)
            return CreateTopicResult(success=True, code=code)
        msg = str(data.get("msg") or f"code={code}")
        _LOGGER.warning("Failed to create Bemfa topic %s: %s", topic, msg)
        return CreateTopicResult(success=False, error_msg=msg, code=code)

    async def delete_topic(self, topic: str) -> bool:
        """从巴法云删除一个 topic（主题）。"""
        data = await self._request(
            "post",
            self._delete_topic_url,
            json={
                "uid": self._bemfa_uid,
                "topic": topic,
                "type": 1,
            },
        )
        if not data:
            return False
        if data.get("code") == 0:
            _LOGGER.debug("Deleted Bemfa topic: %s", topic)
            return True
        _LOGGER.warning("Failed to delete Bemfa topic %s: %s", topic, data.get("msg"))
        return False

    async def change_topic_room(self, topics: list[str], room: str) -> bool:
        """为 topic 设置所属房间。"""
        data = await self._request(
            "post",
            self._change_room_url,
            json={
                "openID": self._bemfa_uid,
                "topicIDs": topics,
                "type": 1,
                "room": room,
            },
        )
        if not data:
            return False
        if data.get("code") == 0:
            _LOGGER.debug("Changed room for topics %s to %s", topics, room)
            return True
        _LOGGER.warning("Failed to change room: %s", data.get("msg"))
        return False

    async def change_topic_group(self, topics: list[str], group: str) -> bool:
        """为 topic 设置所属分组。"""
        data = await self._request(
            "post",
            self._change_group_url,
            json={
                "openID": self._bemfa_uid,
                "topicIDs": topics,
                "type": 1,
                "group": group,
            },
        )
        if not data:
            return False
        if data.get("code") == 0:
            _LOGGER.debug("Changed group for topics %s to %s", topics, group)
            return True
        _LOGGER.warning("Failed to change group: %s", data.get("msg"))
        return False

    async def modify_name(self, topic: str, name: str) -> bool:
        """修改主题昵称。"""
        data = await self._request(
            "post",
            self._modify_name_url,
            json={
                "uid": self._bemfa_uid,
                "topic": topic,
                "type": 1,
                "name": name,
            },
        )
        if not data:
            return False
        if data.get("code") == 0:
            _LOGGER.debug("Modified name for topic %s to %s", topic, name)
            return True
        _LOGGER.warning("Failed to modify name: %s", data.get("msg"))
        return False

    async def list_topics(self) -> list[str] | None:
        """列出账号下全部 MQTT topic；请求失败返回 None。"""
        data = await self._request(
            "get",
            f"{self._all_topic_url}?openID={self._bemfa_uid}&type=1",
        )
        if not data:
            return None
        if data.get("code") != 0:
            _LOGGER.warning("Failed to list topics: %s", data.get("msg"))
            return None
        topics_data = data.get("data")
        if not isinstance(topics_data, list):
            _LOGGER.warning("Unexpected allTopic response shape")
            return None
        topics: list[str] = []
        for item in cast("list[dict[str, object]]", topics_data):
            raw_topic = item.get("topic")
            if isinstance(raw_topic, str):
                topics.append(raw_topic)
        return topics

    async def get_device_list(self) -> list[BemfaDevice]:
        """获取巴法云设备列表（GET /vb/ha/v1/device）。

        事实依据：behome api.py `get_devices()`（openID 参数 + data.array 结构）。
        请求失败或响应异常时返回空列表。
        """
        data = await self._request(
            "get",
            self._device_list_url,
            params={"openID": self._encoded_open_id},
        )
        if not data:
            return []
        if data.get("code") != 0:
            _LOGGER.warning("Bemfa device list failed: %s", data.get("msg"))
            return []
        payload = data.get("data")
        if not isinstance(payload, dict):
            return []
        payload = cast("dict[str, object]", payload)
        devices = payload.get("array")
        if not isinstance(devices, list):
            return []
        devices = cast("list[dict[str, object]]", devices)
        return [
            BemfaDevice(
                topic=str(item.get("topic", "")),
                device_type=str(item.get("type", "")),
                name=str(item.get("name", "")),
            )
            for item in devices
        ]

    async def control_device(
        self, topic: str, message: dict[str, object], device_type: int
    ) -> bool:
        """控制设备（POST /vb/ha/v1/postMassage）。

        事实依据：behome api.py `control_device()` + 规范 08 §3.6 消息格式。
        message 为设备控制消息（如灯光 {"on": true} / {"on": true, "bri": 80}）。
        """
        data = await self._request(
            "post",
            self._device_control_url,
            json={
                "openID": self._encoded_open_id,
                "topicID": topic,
                "type": device_type,
                "message": message,
            },
        )
        if not data:
            return False
        if data.get("code") != 0:
            _LOGGER.warning("Bemfa control failed for %s: %s", topic, data.get("msg"))
            return False
        return True
