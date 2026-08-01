"""Bemfa 同步管理 + v1/v2 HTTP 路由用例。"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.xiaodu.api.xiaodu_types import Device
from custom_components.xiaodu.bemfa.api_client import BemfaAPIClient
from custom_components.xiaodu.bemfa.const import (
    BEMFA_CHANGE_GROUP_URL,
    BEMFA_CHANGE_ROOM_URL,
    BEMFA_CREATE_TOPIC_URL,
    BEMFA_CREATE_TOPIC_V1_URL,
    BEMFA_DELETE_TOPIC_URL,
)
from custom_components.xiaodu.bemfa.mqtt_client import BemfaMQTTClient
from custom_components.xiaodu.bemfa.sync_manager import BemfaDeviceSyncManager
from tests.conftest import MqttBrokerHandle, MqttProbe
from tests.const import (
    TEST_BEMFA_SECRET_ID,
    TEST_BEMFA_SECRET_KEY,
    TEST_BEMFA_UID,
)


def _device(appliance_id: str = "appliance_test_light_001") -> Device:
    return Device(
        appliance_id=appliance_id,
        friendly_name="Test Light",
        room_name="次卧",
        appliance_types=["LIGHT"],
    )


def _manager(
    hass: HomeAssistant,
    *,
    secret_id: str = "",
    secret_key: str = "",
) -> BemfaDeviceSyncManager:
    session = async_get_clientsession(hass)
    api = BemfaAPIClient(
        TEST_BEMFA_UID,
        session,
        secret_id=secret_id,
        secret_key=secret_key,
    )
    mqtt_client = BemfaMQTTClient(TEST_BEMFA_UID, use_tls=False)
    return BemfaDeviceSyncManager(TEST_BEMFA_UID, api, mqtt_client)


async def test_create_topic_v1_route(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """无 secret 时走 v1 createTopic，请求体为 uid/topic/type/name。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager(hass)
    await manager.sync_devices([_device()], {"次卧": "次卧"})
    calls = [c for c in aioclient_mock.mock_calls if "v1/createTopic" in str(c[1])]
    assert len(calls) == 1
    body = calls[0][2]
    assert body["uid"] == TEST_BEMFA_UID
    assert body["topic"].endswith("002")
    assert body["type"] == 1
    assert body["name"] == "次卧Test Light"
    mapping = manager.device_mapping["appliance_test_light_001"]
    assert mapping.sync_status == "synced"
    assert mapping.bemfa_topic is not None


async def test_create_topic_v2_route(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """有 secret 时走 v2 createTopic，请求体追加 secretID/secretKey。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager(
        hass,
        secret_id=TEST_BEMFA_SECRET_ID,
        secret_key=TEST_BEMFA_SECRET_KEY,
    )
    await manager.sync_devices([_device()], {"次卧": "次卧"})
    calls = [c for c in aioclient_mock.mock_calls if "/v2/createTopic" in str(c[1])]
    assert len(calls) == 1
    body = calls[0][2]
    assert body["secretID"] == TEST_BEMFA_SECRET_ID
    assert body["secretKey"] == TEST_BEMFA_SECRET_KEY
    assert manager.api_client.api_version == "v2"


async def test_create_topic_exists_is_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 40006})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager(hass)
    await manager.sync_devices([_device()], {})
    assert manager.device_mapping["appliance_test_light_001"].sync_status == "synced"


async def test_create_topic_failure_retries_after_backoff(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """失败写入 error mapping（无 topic），退避到期后自动重试成功。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 40000})
    manager = _manager(hass)
    await manager.sync_devices([_device()], {})
    mapping = manager.device_mapping["appliance_test_light_001"]
    assert mapping.sync_status == "error"
    assert mapping.bemfa_topic is None

    # 模拟退避到期
    mapping.last_sync_time = 0
    aioclient_mock.clear_requests()
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    await manager.sync_devices([_device()], {})
    mapping = manager.device_mapping["appliance_test_light_001"]
    assert mapping.sync_status == "synced"
    assert mapping.bemfa_topic is not None


async def test_create_topic_permanent_error_not_retried(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """40009 标记 permanent_error，退避到期也不重试。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 40009})
    manager = _manager(hass)
    await manager.sync_devices([_device()], {})
    mapping = manager.device_mapping["appliance_test_light_001"]
    assert mapping.sync_status == "permanent_error"
    mapping.last_sync_time = 0
    aioclient_mock.clear_requests()
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    await manager.sync_devices([_device()], {})
    assert manager.device_mapping["appliance_test_light_001"].sync_status == (
        "permanent_error"
    )


async def test_remove_device_skips_delete_without_topic(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """失败设备（无 topic）移除时不发 deleteTopic。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 40000})
    manager = _manager(hass)
    await manager.sync_devices([_device()], {})
    aioclient_mock.mock_calls.clear()
    await manager.remove_device("appliance_test_light_001")
    assert not any("deleteTopic" in str(c[1]) for c in aioclient_mock.mock_calls)


async def test_sync_removes_missing_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_DELETE_TOPIC_URL, json={"code": 0})
    manager = _manager(hass)
    await manager.sync_devices([_device("dev_a")], {})
    await manager.sync_devices([], {})
    assert manager.device_mapping == {}


def _manager_with_broker(
    hass: HomeAssistant,
    bemfa_mqtt_broker: MqttBrokerHandle,
) -> BemfaDeviceSyncManager:
    """把 manager 的 MQTT 客户端指向本地 broker 并连接。"""
    manager = _manager(hass)
    manager._mqtt_client._host = bemfa_mqtt_broker.host
    manager._mqtt_client._port = bemfa_mqtt_broker.port
    manager._mqtt_client._use_tls = False
    return manager


async def test_add_device_subscribes_topic(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    bemfa_mqtt_broker: MqttBrokerHandle,
) -> None:
    """创建成功 → 客户端记录订阅；失败不订阅。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager_with_broker(hass, bemfa_mqtt_broker)
    await manager._mqtt_client.async_connect(timeout_seconds=2.0)
    await manager.sync_devices([_device()], {})
    topic = manager.device_mapping["appliance_test_light_001"].bemfa_topic
    assert topic in manager._mqtt_client.subscribed_topics
    manager._mqtt_client.disconnect()


async def test_remove_device_unsubscribes_topic(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    bemfa_mqtt_broker: MqttBrokerHandle,
) -> None:
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_DELETE_TOPIC_URL, json={"code": 0})
    manager = _manager_with_broker(hass, bemfa_mqtt_broker)
    await manager._mqtt_client.async_connect(timeout_seconds=2.0)
    await manager.sync_devices([_device()], {})
    topic = manager.device_mapping["appliance_test_light_001"].bemfa_topic
    await manager.remove_device("appliance_test_light_001")
    assert topic not in manager._mqtt_client.subscribed_topics
    manager._mqtt_client.disconnect()


async def test_update_device_state_publishes_encoded_wire(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    bemfa_mqtt_broker: MqttBrokerHandle,
    bemfa_mqtt_probe: MqttProbe,
) -> None:
    """状态上报编码为 # 文本并真实到达 broker。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager_with_broker(hass, bemfa_mqtt_broker)
    await manager._mqtt_client.async_connect(timeout_seconds=2.0)
    await manager.sync_devices([_device()], {})
    mapping = manager.device_mapping["appliance_test_light_001"]
    published = await manager.update_device_state(
        "appliance_test_light_001",
        {"turnOnState": {"value": "ON"}, "brightness": {"value": 80}},
    )
    assert published is True
    _topic, payload = await bemfa_mqtt_probe.wait_for(
        lambda t, p: t == f"{mapping.bemfa_topic}/up"
    )
    assert payload == "on#80"
    manager._mqtt_client.disconnect()


async def test_update_device_state_returns_false_when_not_connected(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager(hass)
    await manager.sync_devices([_device()], {})
    assert (
        await manager.update_device_state(
            "appliance_test_light_001",
            {"turnOnState": {"value": "ON"}},
        )
        is False
    )


async def test_get_appliance_id_by_topic(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager(hass)
    await manager.sync_devices([_device()], {})
    topic = manager.device_mapping["appliance_test_light_001"].bemfa_topic
    assert manager.get_appliance_id_by_topic(topic) == "appliance_test_light_001"
    assert manager.get_appliance_id_by_topic("unknown") is None


async def test_unsupported_devices_tracked(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    manager = _manager(hass)
    await manager.sync_devices(
        [
            Device(
                appliance_id="dev_lock",
                friendly_name="Lock",
                room_name="次卧",
                appliance_types=["DOOR_LOCK"],
            )
        ],
        {},
    )
    assert manager.unsupported_devices == {"dev_lock": ["DOOR_LOCK"]}
