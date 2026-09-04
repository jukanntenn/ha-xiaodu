"""BemfaMQTTClient 真实 broker 用例。"""

from __future__ import annotations

import asyncio
import socket
import threading
from typing import TYPE_CHECKING

from custom_components.xiaodu.bemfa.mqtt_client import BemfaMQTTClient

if TYPE_CHECKING:
    from tests.conftest import MqttBrokerHandle, MqttProbe


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def test_async_connect_success(
    bemfa_mqtt_broker: MqttBrokerHandle,
) -> None:
    client = BemfaMQTTClient(
        "test-uid-connect",
        host=bemfa_mqtt_broker.host,
        port=bemfa_mqtt_broker.port,
        use_tls=False,
    )
    assert await client.async_connect(timeout_seconds=2.0) is True
    assert client.is_connected() is True
    client.disconnect()


async def test_async_connect_timeout_returns_false(socket_enabled: None) -> None:
    client = BemfaMQTTClient(
        "test-uid-timeout",
        host="127.0.0.1",
        port=_free_port(),
        use_tls=False,
    )
    assert await client.async_connect(timeout_seconds=1.0) is False
    assert client.is_connected() is False
    client.disconnect()


async def test_double_connect_keeps_single_client(
    bemfa_mqtt_broker: MqttBrokerHandle,
) -> None:
    client = BemfaMQTTClient(
        "test-uid-double",
        host=bemfa_mqtt_broker.host,
        port=bemfa_mqtt_broker.port,
        use_tls=False,
    )
    await client.async_connect(timeout_seconds=2.0)
    underlying = client._client
    await client.async_connect(timeout_seconds=2.0)
    assert client._client is underlying
    client.disconnect()


async def test_disconnect_is_idempotent(
    bemfa_mqtt_broker: MqttBrokerHandle,
) -> None:
    client = BemfaMQTTClient(
        "test-uid-disconnect",
        host=bemfa_mqtt_broker.host,
        port=bemfa_mqtt_broker.port,
        use_tls=False,
    )
    await client.async_connect(timeout_seconds=2.0)
    client.disconnect()
    client.disconnect()
    assert client.is_connected() is False


async def test_publish_returns_false_when_not_connected() -> None:
    client = BemfaMQTTClient("test-uid-notconnected", use_tls=False)
    assert client.publish("dev/up", "on") is False
    client.disconnect()


async def test_publish_reaches_probe(
    bemfa_mqtt_broker: MqttBrokerHandle,
    bemfa_mqtt_probe: MqttProbe,
) -> None:
    client = BemfaMQTTClient(
        "test-uid-pub",
        host=bemfa_mqtt_broker.host,
        port=bemfa_mqtt_broker.port,
        use_tls=False,
    )
    await client.async_connect(timeout_seconds=2.0)
    assert client.publish("dev/up", "on#80") is True
    _topic, payload = await bemfa_mqtt_probe.wait_for(lambda t, p: t == "dev/up")
    assert payload == "on#80"
    client.disconnect()


async def test_subscribe_receives_downlink(
    bemfa_mqtt_broker: MqttBrokerHandle,
    bemfa_mqtt_probe: MqttProbe,
) -> None:
    client = BemfaMQTTClient(
        "test-uid-sub",
        host=bemfa_mqtt_broker.host,
        port=bemfa_mqtt_broker.port,
        use_tls=False,
    )
    received: list[tuple[str, str]] = []
    got_message = threading.Event()

    def _on_message(topic: str, payload: str) -> None:
        received.append((topic, payload))
        got_message.set()

    client.set_on_message_callback(_on_message)
    await client.async_connect(timeout_seconds=2.0)
    client.subscribe("dev001")
    assert "dev001" in client.subscribed_topics
    bemfa_mqtt_probe.send("dev001", "on")
    assert await asyncio.to_thread(got_message.wait, 10) is True
    assert received == [("dev001", "on")]
    client.disconnect()


async def test_resubscribe_after_broker_restart(
    bemfa_mqtt_broker: MqttBrokerHandle,
    bemfa_mqtt_probe: MqttProbe,
) -> None:
    client = BemfaMQTTClient(
        "test-uid-reconnect",
        host=bemfa_mqtt_broker.host,
        port=bemfa_mqtt_broker.port,
        use_tls=False,
    )
    received: list[tuple[str, str]] = []
    got_message = threading.Event()

    def _on_message(topic: str, payload: str) -> None:
        received.append((topic, payload))
        got_message.set()

    client.set_on_message_callback(_on_message)
    await client.async_connect(timeout_seconds=2.0)
    client.subscribe("dev002")
    await bemfa_mqtt_broker.restart()
    assert await client.async_connect(timeout_seconds=5.0) is True
    bemfa_mqtt_probe.send("dev002", "off")
    assert await asyncio.to_thread(got_message.wait, 10) is True
    assert received == [("dev002", "off")]
    client.disconnect()


async def test_on_message_undecodable_payload(
    bemfa_mqtt_broker: MqttBrokerHandle,
    bemfa_mqtt_probe: MqttProbe,
) -> None:
    client = BemfaMQTTClient(
        "test-uid-decode",
        host=bemfa_mqtt_broker.host,
        port=bemfa_mqtt_broker.port,
        use_tls=False,
    )
    received: list[tuple[str, str]] = []
    got_message = threading.Event()

    def _on_message(topic: str, payload: str) -> None:
        received.append((topic, payload))
        got_message.set()

    client.set_on_message_callback(_on_message)
    await client.async_connect(timeout_seconds=2.0)
    client.subscribe("dev003")
    bemfa_mqtt_probe.send_raw("dev003", b"\xff\xfe")
    assert await asyncio.to_thread(got_message.wait, 10) is True
    assert received
    assert received[0][0] == "dev003"
    client.disconnect()


def test_client_id_is_bemfa_uid_for_auth() -> None:
    """client_id 必须等于巴法云 UID——它是 MQTT 主鉴权凭证。

    巴法云官方 MQTT 文档：用户私钥（UID）直接作 client_id，username/
    password 留空即通过鉴权。任何对 client_id 的改动（如追加实例段）都会
    使 broker 判定 client_id 不匹配 → 回退到 username/password 验证 →
    本集成不传这俩 → 连接被拒。故 client_id 不得注入任何额外信息；
    多实例隔离完全由 topic 命名空间（实例段）在应用层承担。
    """
    client = BemfaMQTTClient(
        "829af90951ca4fa2b5b92d10c9bdc189",
        host="127.0.0.1",
        port=1883,
        use_tls=False,
    )
    assert client._bemfa_uid == "829af90951ca4fa2b5b92d10c9bdc189"
