"""巴法云（Bemfa）状态发布器。"""

from __future__ import annotations

import logging
from typing import Any

from .mqtt_client import BemfaMQTTClient

_LOGGER = logging.getLogger(__name__)


class BemfaStatePublisher:
    """通过 MQTT 将设备状态发布到巴法云（Bemfa）。"""

    def __init__(self, mqtt_client: BemfaMQTTClient) -> None:
        """初始化状态发布器。

        Args:
            mqtt_client: 用于发布消息的 MQTT 客户端。
        """
        self._mqtt_client = mqtt_client

    def publish_device_state(self, topic: str, state: dict) -> None:
        """向巴法云发布设备状态。

        发布到 {topic}/up，该 topic 只会更新云端数据，
        不会推送给其他订阅者。

        Args:
            topic: 设备 topic。
            state: 要发布的状态字典。
        """
        publish_topic = f"{topic}/up"
        _LOGGER.debug("Publishing state to %s: %s", publish_topic, state)
        self._mqtt_client.publish(publish_topic, state)

    def publish_light_state(
        self,
        topic: str,
        on: bool,
        brightness: int | None = None,
    ) -> None:
        """发布灯的状态。

        Args:
            topic: 设备 topic。
            on: 灯是否打开。
            brightness: 亮度值（0-100）。
        """
        state: dict[str, Any] = {"on": on}
        if on and brightness is not None:
            state["bri"] = brightness
        self.publish_device_state(topic, state)

    def publish_switch_state(self, topic: str, on: bool) -> None:
        """发布开关的状态。

        Args:
            topic: 设备 topic。
            on: 开关是否打开。
        """
        self.publish_device_state(topic, {"on": on})
