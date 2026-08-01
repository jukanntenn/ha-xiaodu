"""巴法云（Bemfa）MQTT 客户端。"""

from __future__ import annotations

import asyncio
import logging
import ssl
import threading
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

from .const import BEMFA_BROKER, BEMFA_TLS_PORT, BEMFA_USE_TLS

_LOGGER = logging.getLogger(__name__)

MessageCallback = Callable[[str, str], None]


class BemfaMQTTClient:
    """巴法云（Bemfa）的 MQTT 客户端。"""

    def __init__(
        self,
        bemfa_uid: str,
        host: str = BEMFA_BROKER,
        port: int = BEMFA_TLS_PORT,
        use_tls: bool = BEMFA_USE_TLS,
    ) -> None:
        self._bemfa_uid: str = bemfa_uid
        self._host: str = host
        self._port: int = port
        self._use_tls: bool = use_tls
        self._client: mqtt.Client | None = None
        self._connected: bool = False
        self._connect_event: threading.Event = threading.Event()
        self._subscribed_topics: set[str] = set()
        self._on_message_callback: MessageCallback | None = None

    async def async_connect(self, timeout_seconds: float = 5.0) -> bool:
        """连接 broker 并等待 CONNACK；超时返回 False，不抛异常。"""
        if self._client is None:
            try:
                self._client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id=self._bemfa_uid,
                )
                self._client.on_connect = self._on_connect
                self._client.on_disconnect = self._on_disconnect
                self._client.on_message = self._on_message
                if self._use_tls:
                    self._client.tls_set(cert_reqs=ssl.CERT_NONE)
                    self._client.tls_insecure_set(True)
                _LOGGER.debug(
                    "Connecting to Bemfa MQTT broker at %s:%s (tls=%s)",
                    self._host,
                    self._port,
                    self._use_tls,
                )
                _ = self._client.connect_async(self._host, self._port, keepalive=60)
                _ = self._client.loop_start()
            except Exception:
                _LOGGER.exception("Failed to start Bemfa MQTT client")
                self._client = None
                return False
        await asyncio.to_thread(self._connect_event.wait, timeout_seconds)
        if not self._connected:
            _LOGGER.warning(
                "MQTT broker %s:%s unreachable (uid=%s)",
                self._host,
                self._port,
                self._bemfa_uid,
            )
        return self._connected

    def disconnect(self) -> None:
        """断开连接；未连接/重复调用安全。"""
        if self._client is None:
            return
        _LOGGER.debug("Disconnecting from Bemfa MQTT broker")
        # 先 disconnect() 触发 socket 关闭，paho 网络循环的 select 会立即返回，
        # 随后 loop_stop() 才能干净地 join 线程。顺序颠倒会让 loop_stop() 阻塞
        # 在线程 join 上等待一个永远不会自行结束的 select 循环（直至超时）。
        _ = self._client.disconnect()
        _ = self._client.loop_stop()
        self._client = None
        self._connected = False
        self._connect_event.clear()

    def subscribe(self, topic: str, qos: int = 1) -> None:
        """记录订阅并在已连接时实际订阅。"""
        self._subscribed_topics.add(topic)
        if self._client and self._connected:
            _LOGGER.debug("Subscribing to topic: %s", topic)
            _ = self._client.subscribe(topic, qos=qos)

    def unsubscribe(self, topic: str) -> None:
        """取消订阅并从记录中移除。"""
        self._subscribed_topics.discard(topic)
        if self._client and self._connected:
            _LOGGER.debug("Unsubscribing from topic: %s", topic)
            _ = self._client.unsubscribe(topic)

    def publish(self, topic: str, payload: str) -> bool:
        """发布状态（QoS1）。未连接返回 False，不静默丢弃语义。"""
        if self._client and self._connected:
            _LOGGER.debug("Publishing to %s: %s", topic, payload)
            _ = self._client.publish(topic, payload, qos=1)
            return True
        _LOGGER.debug("MQTT not connected, dropping publish to %s", topic)
        return False

    def is_connected(self) -> bool:
        """是否已连接。"""
        return self._connected

    def set_on_message_callback(self, callback: MessageCallback) -> None:
        """设置下行消息回调（paho 线程中调用，调用方负责切回事件循环）。"""
        self._on_message_callback = callback

    @property
    def subscribed_topics(self) -> frozenset[str]:
        """当前记录的订阅集合（断线重连后自动恢复）。"""
        return frozenset(self._subscribed_topics)

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        connect_flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Any,
    ) -> None:
        if reason_code == 0:
            _LOGGER.info("Connected to Bemfa MQTT broker")
            self._connected = True
            self._connect_event.set()
            for topic in self._subscribed_topics:
                _ = client.subscribe(topic, qos=1)
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
        _LOGGER.info("Disconnected from Bemfa MQTT broker: %s", reason_code)
        self._connected = False
        self._connect_event.clear()

    def _on_message(
        self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage
    ) -> None:
        payload = msg.payload.decode("utf-8", errors="replace")
        _LOGGER.debug("Received message on %s: %s", msg.topic, payload)
        if self._on_message_callback:
            self._on_message_callback(msg.topic, payload)
