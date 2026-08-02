"""下行闭环 e2e：巴法云下发 → HA 控制小度 → 回传状态。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.xiaodu.api.xiaodu_client import HOST
from custom_components.xiaodu.const import (
    CONF_COOKIE,
    CONF_HOUSE_ID,
    CONF_HOUSE_NAME,
    CONF_ROOM_MAPPING,
    DOMAIN,
)
from tests.conftest import MqttBrokerHandle, MqttProbe, load_json_fixture
from tests.const import (
    TEST_BEMFA_SECRET_ID,
    TEST_BEMFA_SECRET_KEY,
    TEST_BEMFA_UID,
    TEST_COOKIE,
    TEST_HOUSE_ID,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )


def _register_bemfa_endpoints(aioclient_mock: AiohttpClientMocker) -> None:
    """注册巴法云 HTTP 端点（本文件独立维护，避免依赖 e2e conftest）。"""
    from tests.conftest import register_bemfa_endpoints as _shared

    _shared(aioclient_mock)


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Xiaodu: Test Home",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: "Test Home",
        },
        options={
            CONF_ROOM_MAPPING: {"次卧": "次卧"},
            "bemfa": {
                "enabled": True,
                "uid": TEST_BEMFA_UID,
                "secret_id": TEST_BEMFA_SECRET_ID,
                "secret_key": TEST_BEMFA_SECRET_KEY,
                "sync_devices": True,
            },
        },
    )


async def test_mqtt_downlink_controls_device_and_reports_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    bemfa_mqtt_broker: MqttBrokerHandle,
    bemfa_mqtt_probe: MqttProbe,
    monkeypatch,
) -> None:
    """探针下发 on#80 → HA 控制小度 → 回传 {topic}/up。"""
    import custom_components.xiaodu as xiaodu_module

    monkeypatch.setattr(xiaodu_module, "BEMFA_BROKER", bemfa_mqtt_broker.host)
    monkeypatch.setattr(xiaodu_module, "BEMFA_TLS_PORT", bemfa_mqtt_broker.port)
    monkeypatch.setattr(xiaodu_module, "BEMFA_USE_TLS", False)

    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_ok.json"),
    )
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/multihouse",
        json=load_json_fixture("home_list.json"),
    )
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/appliance",
        json=load_json_fixture("device_list.json"),
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/appliancedetails",
        json=load_json_fixture("device_detail_light.json"),
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/directivesend",
        json=load_json_fixture("control_response_ok.json"),
    )
    _register_bemfa_endpoints(aioclient_mock)

    entry = _make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    mapping = coordinator.bemfa_sync_manager.device_mapping["appliance_test_light_001"]
    assert mapping.bemfa_topic is not None

    aioclient_mock.mock_calls.clear()
    bemfa_mqtt_probe.send(mapping.bemfa_topic, "on#80")

    # 等待 TurnOn 与 SetBrightness 两条控制指令都到达 Xiaodu HTTP。
    # coordinator 顺序执行两条指令，第二次请求可能晚几十毫秒到达——
    # 必须等齐再断言，否则在 CI 调度下会偶发失败。
    expected_commands = {"TurnOnRequest", "SetBrightnessPercentageRequest"}
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 3
    control_calls = []
    while loop.time() < deadline:
        control_calls = [
            c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
        ]
        if {c[2]["header"]["name"] for c in control_calls} >= expected_commands:
            break
        await asyncio.sleep(0.02)
    actual_commands = {c[2]["header"]["name"] for c in control_calls}
    assert actual_commands >= expected_commands, (
        f"控制指令未等齐，实际收到: {sorted(actual_commands)}"
    )
    body = control_calls[0][2]
    assert body["header"]["name"] == "TurnOnRequest"
    assert body["payload"]["parameters"]["attributeValue"] == "ON"

    # 亮度指令也已下发（fixture 的灯无 brightness 键，回传为 on）
    assert any(
        c[2]["header"]["name"] == "SetBrightnessPercentageRequest"
        and c[2]["payload"]["parameters"]["attributeValue"] == 80
        for c in control_calls
    )

    # 等待回传 /up（fixture 无亮度字段 → "on"）
    _up_topic, payload = await bemfa_mqtt_probe.wait_for(
        lambda t, p: t == f"{mapping.bemfa_topic}/up" and p == "on"
    )
    assert payload == "on"

    # 卸载：后台任务取消、MQTT 真实断开（broker 只剩探针会话）
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await asyncio.to_thread(_wait_for_sessions, bemfa_mqtt_broker, 1, 3.0)


def _wait_for_sessions(
    broker: MqttBrokerHandle, expected: int, timeout_seconds: float
) -> bool:
    """在线程中轮询 broker 会话数（避免 asyncio 轮询 lint）。"""
    import time

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if broker.sessions == expected:
            return True
        time.sleep(0.05)
    return False
