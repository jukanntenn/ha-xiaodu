"""巴法云（Bemfa）HTTP API 客户端。"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    BEMFA_CHANGE_GROUP_URL,
    BEMFA_CHANGE_ROOM_URL,
    BEMFA_CREATE_TOPIC_URL,
    BEMFA_DEVICE_CONTROL_URL,
    BEMFA_DEVICE_LIST_URL,
)

_LOGGER = logging.getLogger(__name__)


class BemfaAPIClient:
    """巴法云（Bemfa）的 HTTP API 客户端。"""

    def __init__(self, bemfa_uid: str, session: ClientSession) -> None:
        """初始化 API 客户端。

        Args:
            bemfa_uid: 巴法云（Bemfa）的 UID。
            session: aiohttp 客户端会话。
        """
        self._bemfa_uid = bemfa_uid
        self._session = session

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """发起 HTTP 请求。

        Args:
            method: HTTP 方法。
            url: 请求 URL。
            **kwargs: 额外参数。

        Returns:
            响应的 JSON 数据，失败时返回 None。
        """
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

    async def create_topic(self, topic: str, name: str) -> bool:
        """在巴法云上创建一个 topic（主题）。

        Args:
            topic: topic 名称。
            name: 设备昵称。

        Returns:
            成功返回 True。
        """
        data = await self._request(
            "post",
            BEMFA_CREATE_TOPIC_URL,
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
            _LOGGER.debug("Created Bemfa topic: %s", topic)
            return True
        _LOGGER.warning("Failed to create Bemfa topic %s: %s", topic, data.get("msg"))
        return False

    async def delete_topic(self, topic: str) -> bool:
        """从巴法云删除一个 topic（主题）。

        Args:
            topic: topic 名称。

        Returns:
            成功返回 True。
        """
        data = await self._request(
            "post",
            "https://pro.bemfa.com/v1/deleteTopic",
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
        """为 topic 设置所属房间。

        Args:
            topics: topic 名称列表。
            room: 房间名称。

        Returns:
            成功返回 True。
        """
        data = await self._request(
            "post",
            BEMFA_CHANGE_ROOM_URL,
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
        """为 topic 设置所属分组。

        Args:
            topics: topic 名称列表。
            group: 分组名称。

        Returns:
            成功返回 True。
        """
        data = await self._request(
            "post",
            BEMFA_CHANGE_GROUP_URL,
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

    async def control_device(self, topic: str, message: dict, device_type: int) -> bool:
        """向设备发送控制指令。

        Args:
            topic: 设备 topic。
            message: 控制消息。
            device_type: 设备类型代码。

        Returns:
            成功返回 True。
        """
        data = await self._request(
            "post",
            BEMFA_DEVICE_CONTROL_URL,
            json={
                "uid": self._bemfa_uid,
                "topic": topic,
                "type": device_type,
                "message": message,
            },
        )
        if not data:
            return False
        if data.get("code") == 0:
            _LOGGER.debug("Controlled Bemfa device %s: %s", topic, message)
            return True
        _LOGGER.warning("Failed to control Bemfa device %s: %s", topic, data.get("msg"))
        return False

    async def get_device_list(self) -> list[dict[str, Any]]:
        """从巴法云获取设备列表。

        Returns:
            设备字典列表。
        """
        data = await self._request(
            "get",
            BEMFA_DEVICE_LIST_URL,
            params={"openID": self._bemfa_uid},
        )
        if not data:
            return []
        if data.get("code") != 0:
            _LOGGER.warning("Failed to get Bemfa devices: %s", data.get("msg"))
            return []
        payload = data.get("data", {})
        if not isinstance(payload, dict):
            return []
        devices = payload.get("array", [])
        return [d for d in devices if isinstance(d, dict)]
