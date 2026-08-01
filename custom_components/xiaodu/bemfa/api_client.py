"""巴法云（Bemfa）HTTP API 客户端。"""

from __future__ import annotations

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
    BEMFA_MODIFY_NAME_URL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CreateTopicResult:
    """createTopic 结果。"""

    success: bool
    error_msg: str | None = None
    code: int | None = None


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

    @property
    def api_version(self) -> str:
        """当前生效的接口版本。"""
        return "v2" if self._secret_id and self._secret_key else "v1"

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
            return CreateTopicResult(False, "无响应或请求异常")
        code = data.get("code")
        if code in (0, 40006):
            _LOGGER.debug("Created Bemfa topic: %s (code=%s)", topic, code)
            return CreateTopicResult(True, None, code)
        msg = str(data.get("msg") or f"code={code}")
        _LOGGER.warning("Failed to create Bemfa topic %s: %s", topic, msg)
        return CreateTopicResult(False, msg, code)

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
        for item in cast(list[dict[str, object]], topics_data):
            raw_topic = item.get("topic")
            if isinstance(raw_topic, str):
                topics.append(raw_topic)
        return topics
