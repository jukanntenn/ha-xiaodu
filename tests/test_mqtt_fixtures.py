"""MQTT 测试基建冒烟：真实 broker + 探针回环。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.conftest import MqttProbe


async def test_broker_and_probe_roundtrip(bemfa_mqtt_probe: MqttProbe) -> None:
    """探针发布的消息能被探针自己（订阅 #）收到。"""
    bemfa_mqtt_probe.send("smoke/up", "on#80")
    topic, payload = await bemfa_mqtt_probe.wait_for(lambda t, p: t == "smoke/up")
    assert topic == "smoke/up"
    assert payload == "on#80"


async def test_broker_sessions_empty_when_only_probe(
    bemfa_mqtt_broker,
    bemfa_mqtt_probe: MqttProbe,
) -> None:
    """只有探针连接时 broker 会话数为 1。"""
    assert bemfa_mqtt_broker.sessions == 1


async def test_broker_restart_reconnects_probe(
    bemfa_mqtt_broker,
    bemfa_mqtt_probe: MqttProbe,
) -> None:
    """broker 重启后探针 paho 自动重连并恢复订阅。"""
    await bemfa_mqtt_broker.restart()
    # 重连完成的判据是订阅恢复登记（隐含会话已建立），只等会话数会在
    # SUBSCRIBE 尚未处理完时抢跑 publish，消息路由给空。
    await bemfa_mqtt_broker.wait_for_subscription("mqtt-probe", "#")
    bemfa_mqtt_probe.send("smoke/after-restart", "on")
    await bemfa_mqtt_probe.wait_for(lambda t, p: t == "smoke/after-restart")
