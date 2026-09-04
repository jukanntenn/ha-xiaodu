"""Fixtures for testing the Xiaodu integration.

Follows the flo paradigm: aioclient_mock drives real XiaoduAPI/BemfaAPIClient
execution. No patching of API classes.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import paho.mqtt.client as mqtt
import pytest
from amqtt.broker import Broker
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.xiaodu.api.xiaodu_client import HOST
from custom_components.xiaodu.bemfa.const import (
    BEMFA_ALL_TOPIC_URL,
    BEMFA_CHANGE_GROUP_URL,
    BEMFA_CHANGE_ROOM_URL,
    BEMFA_CREATE_TOPIC_URL,
    BEMFA_MODIFY_NAME_URL,
)
from custom_components.xiaodu.const import (
    CONF_COOKIE,
    CONF_HOUSE_ID,
    CONF_HOUSE_NAME,
    CONF_ROOM_MAPPING,
    DOMAIN,
)
from tests.const import (
    TEST_BEMFA_SECRET_ID,
    TEST_BEMFA_SECRET_KEY,
    TEST_BEMFA_UID,
    TEST_COOKIE,
    TEST_HOUSE_ID,
    TEST_HOUSE_NAME,
    TEST_ROOM_NAME,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_json_fixture(filename: str, subdir: str = "xiaodu") -> dict[str, Any]:
    """Load a JSON fixture file."""
    return json.loads((FIXTURES_DIR / subdir / filename).read_text(encoding="utf-8"))


def register_xiaodu_device(
    hass: HomeAssistant,
    appliance_id: str,
    *,
    area_name: str | None = None,
    name_by_user: str | None = None,
    device_name: str | None = None,
    config_entry_id: str = "test",
) -> DeviceEntry:
    """在 device registry 注册一个小度设备，可选分配区域/改名。

    用于巴法云昵称跟随测试：模拟实体建立后 device_registry 里的状态，
    让 ``_resolve_ha_device`` 能反查到带 area_id/name_by_user 的设备条目。

    Args:
        hass: Home Assistant 实例。
        appliance_id: 小度 appliance ID。
        area_name: 若给定，创建/取回该区域并分配给设备。
        name_by_user: 若给定，设为设备的用户自定义名（HA 设备页改名）。
        device_name: 若给定，设为集成的设备名（entity.py device_info.name）。
        config_entry_id: 关联的 config entry id。

    Returns:
        创建/更新后的 DeviceEntry。
    """
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr

    # 确保 config entry 存在（device 必须关联到已知 config entry）
    if hass.config_entries.async_get_entry(config_entry_id) is None:
        entry = MockConfigEntry(domain=DOMAIN, entry_id=config_entry_id)
        entry.add_to_hass(hass)

    registry = dr.async_get(hass)
    device_entry = registry.async_get_or_create(
        config_entry_id=config_entry_id,
        connections={},
        identifiers={(DOMAIN, appliance_id)},
        name=device_name,
    )
    if name_by_user is not None:
        device_entry = registry.async_update_device(
            device_entry.id, name_by_user=name_by_user
        )
    if area_name:
        area_id = ar.async_get(hass).async_get_or_create(area_name).id
        device_entry = registry.async_update_device(device_entry.id, area_id=area_id)
    return device_entry


def register_bemfa_endpoints(aioclient_mock: AiohttpClientMocker) -> None:
    """Register all Bemfa HTTP API endpoints with fixture data."""
    aioclient_mock.post(
        BEMFA_CREATE_TOPIC_URL,
        json=load_json_fixture("create_topic_ok.json", "bemfa"),
    )
    aioclient_mock.post(
        "https://pro.bemfa.com/v1/deleteTopic",
        json=load_json_fixture("delete_topic_ok.json", "bemfa"),
    )
    aioclient_mock.post(
        BEMFA_CHANGE_ROOM_URL,
        json=load_json_fixture("change_topic_room_ok.json", "bemfa"),
    )
    aioclient_mock.post(
        BEMFA_CHANGE_GROUP_URL,
        json=load_json_fixture("change_topic_group_ok.json", "bemfa"),
    )
    aioclient_mock.get(
        BEMFA_ALL_TOPIC_URL,
        json=load_json_fixture("all_topic_empty.json", "bemfa"),
    )
    aioclient_mock.post(
        BEMFA_MODIFY_NAME_URL,
        json=load_json_fixture("modify_name_ok.json", "bemfa"),
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry without Bemfa."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Xiaodu: {TEST_HOUSE_NAME}",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={
            CONF_ROOM_MAPPING: {TEST_ROOM_NAME: TEST_ROOM_NAME},
        },
    )


@pytest.fixture
def mock_config_entry_with_bemfa() -> MockConfigEntry:
    """Mock config entry with Bemfa enabled."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Xiaodu: {TEST_HOUSE_NAME}",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={
            CONF_ROOM_MAPPING: {TEST_ROOM_NAME: TEST_ROOM_NAME},
            "bemfa": {
                "enabled": True,
                "uid": TEST_BEMFA_UID,
                "secret_id": TEST_BEMFA_SECRET_ID,
                "secret_key": TEST_BEMFA_SECRET_KEY,
                "sync_devices": True,
            },
        },
    )


async def _control_side_effect(
    method: str, url: str, data: dict[str, Any] | None
) -> AiohttpClientMockResponse:
    """Dynamic handler for directivesend: returns OK for any command."""
    return AiohttpClientMockResponse(
        method=method,
        url=url,
        status=200,
        json=load_json_fixture("control_response_ok.json"),
    )


@pytest.fixture
def aioclient_mock_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Register all Xiaodu API endpoints with fixture data.

    Follows the flo conftest pattern: registers all endpoints that the
    integration needs for setup + first refresh.
    """
    # check_session
    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_ok.json"),
    )
    # get_home_list
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/multihouse",
        json=load_json_fixture("home_list.json"),
    )
    # 首次拉取 device_list
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/appliance",
        json=load_json_fixture("device_list.json"),
    )
    # 拉取 light 设备详情
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/appliancedetails",
        json=load_json_fixture("device_detail_light.json"),
    )
    # control_device (directivesend) - uses side_effect for dynamic response
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/directivesend",
        side_effect=_control_side_effect,
    )
    # Bemfa HTTP endpoints (unused mocks are harmless for tests without Bemfa;
    # tests that enable Bemfa need these during setup, sync, and unload).
    register_bemfa_endpoints(aioclient_mock)


class MqttBrokerHandle:
    """测试用 amqtt broker 句柄。"""

    def __init__(self, host: str, port: int, broker: Broker) -> None:
        self.host = host
        self.port = port
        self._broker = broker

    @property
    def sessions(self) -> int:
        """当前 broker 上的会话数（探针 + 被测客户端）。"""
        return len(self._broker._sessions)

    async def restart(self) -> None:
        """在同一端口重启 broker（验证客户端自动重连）。"""
        await self._broker.shutdown()
        self._broker = Broker(
            config={
                "listeners": {
                    "default": {"type": "tcp", "bind": f"127.0.0.1:{self.port}"}
                },
                "plugins": {
                    "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                        "allow_anonymous": True
                    }
                },
            }
        )
        await self._broker.start()


class MqttProbe:
    """扮演巴法云侧的 paho 客户端：订阅 # 观察上行，向 {topic} 发下行。"""

    def __init__(self, client: mqtt.Client, received: list[tuple[str, str]]) -> None:
        self._client = client
        self._received = received

    def send(self, topic: str, payload: str, qos: int = 1) -> None:
        self._client.publish(topic, payload, qos=qos)

    def send_raw(self, topic: str, payload: bytes, qos: int = 1) -> None:
        self._client.publish(topic, payload, qos=qos)

    async def wait_for(
        self, predicate, timeout_seconds: float = 10.0
    ) -> tuple[str, str]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        while loop.time() < deadline:
            for topic, payload in self._received:
                if predicate(topic, payload):
                    return topic, payload
            await asyncio.sleep(0.02)
        raise AssertionError(
            f"No matching MQTT message within {timeout_seconds}s: {self._received!r}"
        )


@pytest.fixture
async def bemfa_mqtt_broker(
    socket_enabled: None,
) -> AsyncGenerator[MqttBrokerHandle]:
    """函数级真实 MQTT broker（amqtt，动态端口）。"""
    broker = Broker(
        config={
            "listeners": {
                "default": {
                    "type": "tcp",
                    "bind": "127.0.0.1:0",
                    "max_connections": 10,
                }
            },
            "plugins": {
                "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                    "allow_anonymous": True
                }
            },
        }
    )
    await broker.start()
    port = broker._servers["default"].instance.sockets[0].getsockname()[1]
    handle = MqttBrokerHandle("127.0.0.1", port, broker)
    yield handle
    if not handle._broker.transitions.is_stopped():
        await handle._broker.shutdown()


@pytest.fixture
async def bemfa_mqtt_probe(
    bemfa_mqtt_broker: MqttBrokerHandle,
) -> AsyncGenerator[MqttProbe]:
    """连接本地 broker 并订阅 # 的探针客户端。"""
    received: list[tuple[str, str]] = []
    connected = threading.Event()
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="mqtt-probe",
    )

    def _on_connect(c, u, flags, reason_code, properties=None) -> None:
        if reason_code == 0:
            client.subscribe("#", qos=1)
            connected.set()

    def _on_message(c, u, msg) -> None:
        received.append((msg.topic, msg.payload.decode("utf-8", errors="replace")))

    client.on_connect = _on_connect
    client.on_message = _on_message
    client.connect_async(bemfa_mqtt_broker.host, bemfa_mqtt_broker.port, keepalive=60)
    client.loop_start()
    # 预算放宽到 10s：CI 洪峰（多 PR 并行测试）下 paho+amqtt 的 TCP/CONNECT
    # 往返会偶发超过 5s；未连上就 publish 会被 paho 静默丢弃，表现为下游
    # 收不到消息的"假失败"（见 test_mqtt_client 的时序抖动）。
    if not await asyncio.to_thread(connected.wait, 10):
        raise AssertionError("MQTT probe 未能在 10s 内连上本地 broker")
    probe = MqttProbe(client, received)
    yield probe
    # paho 的 disconnect()/loop_stop() 是同步阻塞调用。直接在 event loop 线程
    # 执行会卡住 loop 调度，导致 amqtt broker 无法推进与 probe 的 DISCONNECT
    # 握手（broker 端在 await handler.stop()），形成死锁式等待直至超时。
    # 用 to_thread 把阻塞调用移到工作线程，保持 event loop 畅通。
    await asyncio.to_thread(client.disconnect)
    await asyncio.to_thread(client.loop_stop)


@pytest.fixture
def bemfa_mqtt_redirect(
    bemfa_mqtt_broker: MqttBrokerHandle,
    monkeypatch,
) -> MqttBrokerHandle:
    """把集成 MQTT 端点重定向到本地 broker。"""
    import custom_components.xiaodu as xiaodu_module

    monkeypatch.setattr(xiaodu_module, "BEMFA_BROKER", bemfa_mqtt_broker.host)
    monkeypatch.setattr(xiaodu_module, "BEMFA_TLS_PORT", bemfa_mqtt_broker.port)
    monkeypatch.setattr(xiaodu_module, "BEMFA_USE_TLS", False)
    return bemfa_mqtt_broker
