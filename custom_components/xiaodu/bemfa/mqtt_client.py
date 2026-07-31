"""巴法云（Bemfa）MQTT 客户端。"""

from __future__ import annotations

import json
import logging
import ssl
from typing import Any

import paho.mqtt.client as mqtt

from .const import BEMFA_BROKER, BEMFA_TLS_PORT

_LOGGER = logging.getLogger(__name__)


class BemfaMQTTClient:
    """巴法云（Bemfa）的 MQTT 客户端。"""

    def __init__(self, bemfa_uid: str, port: int = BEMFA_TLS_PORT) -> None:
        """初始化 MQTT 客户端。

        Args:
            bemfa_uid: 巴法云（Bemfa）的 UID（用作 client ID）。
            port: MQTT 端口。默认为 9503（TLS）。
        """
        self._bemfa_uid = bemfa_uid
        self._port = port
        self._client: mqtt.Client | None = None
        self._connected = False
        self._on_message_callback: Any = None

    def connect(self) -> None:
        """连接到巴法云 MQTT broker。"""
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._bemfa_uid,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        if self._port == BEMFA_TLS_PORT:
            self._client.tls_set(cert_reqs=ssl.CERT_NONE)
            self._client.tls_insecure_set(True)

        _LOGGER.debug(
            "Connecting to Bemfa MQTT broker at %s:%s",
            BEMFA_BROKER,
            self._port,
        )
        self._client.connect_async(BEMFA_BROKER, self._port, keepalive=60)
        self._client.loop_start()

    def disconnect(self) -> None:
        """断开与 MQTT broker 的连接。"""
        if self._client:
            _LOGGER.debug("Disconnecting from Bemfa MQTT broker")
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected = False

    def subscribe(self, topic: str) -> None:
        """订阅 MQTT topic。

        Args:
            topic: 要订阅的 topic。
        """
        if self._client and self._connected:
            _LOGGER.debug("Subscribing to topic: %s", topic)
            self._client.subscribe(topic, qos=0)

    def unsubscribe(self, topic: str) -> None:
        """取消订阅 MQTT topic。

        Args:
            topic: 要取消订阅的 topic。
        """
        if self._client and self._connected:
            _LOGGER.debug("Unsubscribing from topic: %s", topic)
            self._client.unsubscribe(topic)

    def publish(self, topic: str, payload: dict) -> None:
        """向 MQTT topic 发布消息。

        Args:
            topic: 要发布到的 topic。
            payload: 消息负载（将被 JSON 序列化）。
        """
        if self._client and self._connected:
            message = json.dumps(payload)
            _LOGGER.debug("Publishing to %s: %s", topic, message)
            self._client.publish(topic, message, qos=0)

    def is_connected(self) -> bool:
        """检查客户端是否已连接。

        Returns:
            已连接返回 True。
        """
        return self._connected

    def set_on_message_callback(self, callback: Any) -> None:
        """设置接收消息的回调函数。

        Args:
            callback: 回调函数。
        """
        self._on_message_callback = callback

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        connect_flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Any,
    ) -> None:
        """处理连接建立事件。"""
        if reason_code == 0:
            _LOGGER.info("Connected to Bemfa MQTT broker")
            self._connected = True
        else:
            _LOGGER.error("Failed to connect to Bemfa MQTT broker: %s", reason_code)
            self._connected = False

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Any,
    ) -> None:
        """处理断开连接事件。"""
        _LOGGER.info("Disconnected from Bemfa MQTT broker: %s", reason_code)
        self._connected = False

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        """处理接收到的消息。"""
        _LOGGER.debug("Received message on %s: %s", msg.topic, msg.payload)
        if self._on_message_callback:
            try:
                payload = json.loads(msg.payload)
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = msg.payload
            self._on_message_callback(msg.topic, payload)
