"""Bemfa 同步管理 + v1/v2 HTTP 路由用例。"""

from __future__ import annotations

import base64
import copy
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.xiaodu.api.xiaodu_types import Device
from custom_components.xiaodu.bemfa.api_client import BemfaAPIClient
from custom_components.xiaodu.bemfa.const import (
    BEMFA_ALL_TOPIC_URL,
    BEMFA_CHANGE_GROUP_URL,
    BEMFA_CHANGE_ROOM_URL,
    BEMFA_CREATE_TOPIC_URL,
    BEMFA_CREATE_TOPIC_V1_URL,
    BEMFA_DELETE_TOPIC_URL,
    BEMFA_DEVICE_CONTROL_URL,
    BEMFA_DEVICE_LIST_URL,
    BEMFA_MODIFY_NAME_URL,
    BEMFA_TOPIC_PREFIX,
)
from custom_components.xiaodu.bemfa.mqtt_client import BemfaMQTTClient
from custom_components.xiaodu.bemfa.sync_manager import (
    BemfaDeviceSyncManager,
    DeviceMapping,
)
from tests.conftest import load_json_fixture, register_xiaodu_device
from tests.const import (
    TEST_BEMFA_SECRET_ID,
    TEST_BEMFA_SECRET_KEY,
    TEST_BEMFA_UID,
    TEST_INSTANCE_ID,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

    from tests.conftest import MqttBrokerHandle, MqttProbe


def _device(appliance_id: str = "appliance_test_light_001") -> Device:
    return Device(
        appliance_id=appliance_id,
        friendly_name="Test Light",
        room_name="次卧",
        appliance_types=["LIGHT"],
    )


@pytest.fixture(autouse=True)
def _bemfa_default_mocks(aioclient_mock: AiohttpClientMocker) -> None:
    """默认注册 allTopic（孤儿检测）与 modifyName（昵称跟随）端点。"""
    aioclient_mock.get(BEMFA_ALL_TOPIC_URL, json={"code": 0, "data": []})
    aioclient_mock.post(BEMFA_MODIFY_NAME_URL, json={"code": 0})


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
    return BemfaDeviceSyncManager(
        hass, TEST_BEMFA_UID, api, mqtt_client, TEST_INSTANCE_ID
    )


class _FakeCoordinator:
    """仅暴露 room_mapping / room_tokens / devices 的事件监听器用桩。"""

    def __init__(self, devices: dict[str, Device]) -> None:
        self.devices = devices
        self.room_mapping: dict[str, str] = {}
        self.room_tokens: set[str] = set()


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
    aioclient_mock.post(
        BEMFA_CREATE_TOPIC_V1_URL,
        json=load_json_fixture("create_topic_exists.json", "bemfa"),
    )
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


# ---------------------------------------------------------------------------
# topic 命名空间（前缀 + 稳定哈希）
# ---------------------------------------------------------------------------


async def test_generate_topic_uses_prefix_instance_and_hash(
    hass: HomeAssistant,
) -> None:
    """topic = xdu + instance_id[:8] + md5(appliance_id)[:12] + 3 位类型后缀。"""
    manager = _manager(hass)
    topic = manager._generate_topic("appliance_test_light_001", "LIGHT")
    instance_segment = TEST_INSTANCE_ID[:8]
    assert topic.startswith(f"{BEMFA_TOPIC_PREFIX}{instance_segment}")
    assert topic.endswith("002")
    assert len(topic) == len(BEMFA_TOPIC_PREFIX) + 8 + 12 + 3
    # 确定性：相同输入产生相同 topic
    assert manager._generate_topic("appliance_test_light_001", "LIGHT") == topic


async def test_generate_topic_isolates_instances(hass: HomeAssistant) -> None:
    """不同 HA 实例（不同 instance_id）对同一设备生成不同 topic。"""
    session = async_get_clientsession(hass)
    api = BemfaAPIClient(TEST_BEMFA_UID, session)
    mqtt_a = BemfaMQTTClient(TEST_BEMFA_UID, use_tls=False)
    mqtt_b = BemfaMQTTClient(TEST_BEMFA_UID, use_tls=False)
    manager_a = BemfaDeviceSyncManager(
        hass, TEST_BEMFA_UID, api, mqtt_a, TEST_INSTANCE_ID
    )
    manager_b = BemfaDeviceSyncManager(
        hass, TEST_BEMFA_UID, api, mqtt_b, "0123456789abcdef"
    )
    topic_a = manager_a._generate_topic("dev_same", "LIGHT")
    topic_b = manager_b._generate_topic("dev_same", "LIGHT")
    # 同一设备在两个实例下 topic 不同——实例隔离生效
    assert topic_a != topic_b
    # 但都带集成前缀
    assert topic_a.startswith(BEMFA_TOPIC_PREFIX)
    assert topic_b.startswith(BEMFA_TOPIC_PREFIX)


async def test_generate_topic_ignores_rename(hass: HomeAssistant) -> None:
    """topic 与名字无关——改名/改昵称不影响稳定关联。"""
    manager = _manager(hass)
    a = manager._generate_topic("dev_a", "LIGHT")
    b = manager._generate_topic("dev_b", "LIGHT")
    assert a != b
    assert manager._generate_topic("dev_a", "LIGHT") == a


def test_is_integration_topic() -> None:
    """前缀校验：只认本集成 topic（不含实例维度）。"""
    assert BemfaDeviceSyncManager.is_integration_topic(
        f"{BEMFA_TOPIC_PREFIX}a1b2c3d44f8e2c1a9b7d002"
    )
    # 旧格式（无实例段）仍属于本集成
    assert BemfaDeviceSyncManager.is_integration_topic(
        f"{BEMFA_TOPIC_PREFIX}4f8e2c1a9b7d002"
    )
    assert not BemfaDeviceSyncManager.is_integration_topic("haha001")
    assert not BemfaDeviceSyncManager.is_integration_topic("ha4f8e2c1a9b7d002")


async def test_is_owned_topic_distinguishes_instances(
    hass: HomeAssistant,
) -> None:
    """is_owned_topic 按 xdu+实例段 双段前缀判断本实例归属。"""
    manager = _manager(hass)
    instance_segment = TEST_INSTANCE_ID[:8]
    # 本实例创建的 topic → owned
    assert manager.is_owned_topic(
        f"{BEMFA_TOPIC_PREFIX}{instance_segment}4f8e2c1a9b7d002"
    )
    # 其他实例的 topic（不同实例段）→ 不 owned
    assert not manager.is_owned_topic(f"{BEMFA_TOPIC_PREFIX}deadbeef4f8e2c1a9b7d002")
    # 旧格式（无实例段）→ 不 owned（不属于任何新实例）
    assert not manager.is_owned_topic(f"{BEMFA_TOPIC_PREFIX}4f8e2c1a9b7d002")
    # 非集成 topic → 不 owned
    assert not manager.is_owned_topic("haha001")


async def test_remove_device_refuses_non_integration_topic(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """防御性校验：非集成前缀的 topic 拒绝删除（绝不误删用户设备）。"""
    manager = _manager(hass)
    manager._device_mapping["dev_user"] = DeviceMapping(
        xiaodu_appliance_id="dev_user",
        bemfa_topic="haha001",
        device_type="LIGHT",
    )
    aioclient_mock.post(BEMFA_DELETE_TOPIC_URL, json={"code": 0})
    await manager.remove_device("dev_user")
    assert not any("deleteTopic" in str(c[1]) for c in aioclient_mock.mock_calls)
    # 映射仍被移除（本地状态清理不受影响）
    assert "dev_user" not in manager.device_mapping


async def test_cleanup_orphans_deletes_only_owned_topics(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """孤儿检测：只删本实例创建且不在映射中的 topic。

    其他 HA 实例的 topic（不同实例段）、用户自建 topic 均保留——这是
    多实例隔离的清理边界。
    """
    instance_segment = TEST_INSTANCE_ID[:8]
    orphan = f"{BEMFA_TOPIC_PREFIX}{instance_segment}deadbeef1234002"
    other_instance_topic = f"{BEMFA_TOPIC_PREFIX}99999999aaaaaaaabbbb002"
    user_topic = "haha001"
    aioclient_mock.clear_requests()
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    aioclient_mock.get(
        BEMFA_ALL_TOPIC_URL,
        json={
            "code": 0,
            "data": [
                {"topic": orphan},
                {"topic": other_instance_topic},
                {"topic": user_topic},
            ],
        },
    )
    aioclient_mock.post(BEMFA_DELETE_TOPIC_URL, json={"code": 0})
    manager = _manager(hass)
    await manager.sync_devices([_device()], {})
    deleted = [c for c in aioclient_mock.mock_calls if "deleteTopic" in str(c[1])]
    # 只删本实例的孤儿；其他实例 topic 与用户自建 topic 保留
    assert len(deleted) == 1
    assert deleted[0][2]["topic"] == orphan


# ---------------------------------------------------------------------------
# 昵称标准化（房间 token 剥离 + modifyName 跟随）
# ---------------------------------------------------------------------------


async def test_generate_nickname_strips_room_prefix(
    hass: HomeAssistant,
) -> None:
    """首刷 fallback：设备名含房间前缀时剥离（device_entry 未建立）。"""
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_1",
        friendly_name="儿童房主灯",
        room_name="儿童房",
        appliance_types=["LIGHT"],
    )
    nickname = manager._generate_nickname(
        device, {"儿童房": "书房"}, {"儿童房", "书房"}, appliance_id="dev_1"
    )
    assert nickname == "书房主灯"


async def test_generate_nickname_strips_other_room_token(
    hass: HomeAssistant,
) -> None:
    """首刷 fallback：设备名嵌着他人房间词时也剥离（主卫灯带@主卧 → 主卧灯带）。

    回归用户报告的 BUG：设备在「主卧」房间却叫「主卫灯带」，
    旧实现只认「主卧」做锚点，残留「主卫」，拼接出「主卧主卫灯带」。
    传入小度侧全部房间名后，「主卫」也被识别为房间词并被剥掉。
    """
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_band",
        friendly_name="主卫灯带",
        room_name="主卧",
        appliance_types=["LIGHT"],
    )
    assert (
        manager._generate_nickname(
            device,
            {"主卧": "主卧"},
            {"主卧", "主卫", "客厅", "餐厅"},
            appliance_id="dev_band",
        )
        == "主卧灯带"
    )

    # 设备在「餐厅」却叫「客厅灯带」
    device_living = Device(
        appliance_id="dev_band2",
        friendly_name="客厅灯带",
        room_name="餐厅",
        appliance_types=["LIGHT"],
    )
    assert (
        manager._generate_nickname(
            device_living,
            {"餐厅": "餐厅"},
            {"主卧", "主卫", "客厅", "餐厅"},
            appliance_id="dev_band2",
        )
        == "餐厅灯带"
    )


async def test_generate_nickname_keeps_roomless_name(
    hass: HomeAssistant,
) -> None:
    """首刷 fallback：设备名不含房间 token 时原样拼接（电视墙射灯）。"""
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_2",
        friendly_name="电视墙射灯",
        room_name="客厅",
        appliance_types=["LIGHT"],
    )
    assert (
        manager._generate_nickname(
            device, {"客厅": "客厅"}, {"客厅", "主卧"}, appliance_id="dev_2"
        )
        == "客厅电视墙射灯"
    )


async def test_generate_nickname_follows_ha_area_and_name(
    hass: HomeAssistant,
) -> None:
    """device_entry 存在时，昵称跟随 HA 实际 area 和 name_by_user。

    覆盖功能点 3：用户在「命名与分配」改了区域/名后，巴法云昵称应跟随。
    device 名「主卧主灯」+ area「书房」+ name_by_user「书房主灯」时，
    昵称 = area(书房) + strip_room(name_by_user=书房主灯) = 书房主灯
    （name_by_user 含房间词「书房」，被 strip_room 剥掉，避免叠加）。
    """
    manager = _manager(hass)
    register_xiaodu_device(
        hass,
        "dev_follow",
        area_name="书房",
        name_by_user="书房主灯",
    )
    device = Device(
        appliance_id="dev_follow",
        friendly_name="主卧主灯",
        room_name="主卧",
        appliance_types=["LIGHT"],
    )
    assert (
        manager._generate_nickname(
            device, {"主卧": "主卧"}, {"主卧", "书房"}, appliance_id="dev_follow"
        )
        == "书房主灯"
    )


async def test_generate_nickname_uses_device_name_without_name_by_user(
    hass: HomeAssistant,
) -> None:
    """device_entry 无 name_by_user 时，回退到 device.name（集成设的剥离后名）。"""
    manager = _manager(hass)
    # 模拟实体建立：device_name 是 entity.py device_info.name 设的剥离后值
    register_xiaodu_device(hass, "dev_noname", area_name="客厅", device_name="吊灯")
    device = Device(
        appliance_id="dev_noname",
        friendly_name="客厅吊灯",
        room_name="客厅",
        appliance_types=["LIGHT"],
    )
    # area=客厅，name_by_user 空 → fallback device.name=吊灯（已剥离，二次剥离幂等）
    assert (
        manager._generate_nickname(
            device, {"客厅": "客厅"}, {"客厅"}, appliance_id="dev_noname"
        )
        == "客厅吊灯"
    )


async def test_nickname_follows_ha_area_change(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """用户改 area 后，_sync_nicknames 检测不一致并 modifyName。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_area",
        friendly_name="主灯",
        room_name="儿童房",
        appliance_types=["LIGHT"],
    )
    # 首刷：device_entry 未建立，昵称用 room_mapping（儿童房→书房）
    await manager.sync_devices([device], {"儿童房": "书房"})
    assert manager.device_mapping["dev_area"].bemfa_nickname == "书房主灯"
    aioclient_mock.mock_calls.clear()

    # 用户在 HA 给设备分配了区域「卧室」（实体已建立，device.name=主灯）
    register_xiaodu_device(hass, "dev_area", area_name="卧室", device_name="主灯")
    # 再次同步：device_entry 已建立，昵称应跟随 HA area
    await manager.sync_devices([device], {"儿童房": "书房"})
    calls = [c for c in aioclient_mock.mock_calls if "modifyName" in str(c[1])]
    assert len(calls) == 1
    assert calls[0][2]["name"] == "卧室主灯"
    assert manager.device_mapping["dev_area"].bemfa_nickname == "卧室主灯"


async def test_nickname_follows_mapping_change(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """映射变更后，期望昵称变化 → modifyName 更新并记录新昵称。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_1",
        friendly_name="儿童房主灯",
        room_name="儿童房",
        appliance_types=["LIGHT"],
    )
    await manager.sync_devices([device], {"儿童房": "书房"})
    mapping = manager.device_mapping["dev_1"]
    assert mapping.bemfa_nickname == "书房主灯"
    aioclient_mock.mock_calls.clear()

    # 修改映射 → 昵称应更新
    await manager.sync_devices([device], {"儿童房": "多功能室"})
    calls = [c for c in aioclient_mock.mock_calls if "modifyName" in str(c[1])]
    assert len(calls) == 1
    assert calls[0][2]["name"] == "多功能室主灯"
    assert manager.device_mapping["dev_1"].bemfa_nickname == "多功能室主灯"


async def test_nickname_unchanged_skips_modify_name(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """昵称未变化时不发 modifyName（幂等）。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, json={"code": 0})
    manager = _manager(hass)
    await manager.sync_devices([_device()], {"次卧": "次卧"})
    aioclient_mock.mock_calls.clear()
    await manager.sync_devices([_device()], {"次卧": "次卧"})
    assert not any("modifyName" in str(c[1]) for c in aioclient_mock.mock_calls)


# ---------------------------------------------------------------------------
# 实时同步（hass.bus 事件监听器）
# ---------------------------------------------------------------------------


def _register_listener(
    hass: HomeAssistant,
    manager: BemfaDeviceSyncManager,
    device: Device,
) -> tuple[_FakeCoordinator, Any]:
    """注册事件监听器并返回（桩 coordinator, 注销函数）。"""
    coordinator = _FakeCoordinator({device.appliance_id: device})
    coordinator.room_mapping = {device.room_name: device.room_name}
    coordinator.room_tokens = {device.room_name}
    unsub = manager.async_start_listeners(coordinator)
    return coordinator, unsub


async def test_listener_device_rename_syncs_nickname(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """用户在 HA 改设备名 → 事件监听器实时 modifyName。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_rename",
        friendly_name="客厅吊灯",
        room_name="客厅",
        appliance_types=["LIGHT"],
    )
    # 先建立 device_entry（分配区域），再首刷建立映射
    register_xiaodu_device(hass, "dev_rename", area_name="客厅", device_name="吊灯")
    await manager.sync_devices([device], {"客厅": "客厅"})
    _register_listener(hass, manager, device)
    aioclient_mock.mock_calls.clear()

    # 用户在 HA 给设备改名（单次 update，触发一次 EVENT_DEVICE_REGISTRY_UPDATED）
    from homeassistant.helpers import device_registry as dr

    registry = dr.async_get(hass)
    device_entry = registry.async_get_device(identifiers={("xiaodu", "dev_rename")})
    assert device_entry is not None
    registry.async_update_device(device_entry.id, name_by_user="新吊灯")
    await hass.async_block_till_done()

    calls = [c for c in aioclient_mock.mock_calls if "modifyName" in str(c[1])]
    assert len(calls) == 1
    assert calls[0][2]["name"] == "客厅新吊灯"


async def test_listener_device_area_change_syncs_nickname_and_room(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """用户在 HA 换区域 → 事件监听器实时 modifyName + changeTopicRoom。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_area",
        friendly_name="主灯",
        room_name="客厅",
        appliance_types=["LIGHT"],
    )
    # 先在「客厅」建立 device_entry + 映射，再监听
    register_xiaodu_device(hass, "dev_area", area_name="客厅", device_name="主灯")
    await manager.sync_devices([device], {"客厅": "客厅"})
    _register_listener(hass, manager, device)
    aioclient_mock.mock_calls.clear()

    # 用户把设备从「客厅」改分配到「卧室」（单次 area_id 变更事件）
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr

    bedroom = ar.async_get(hass).async_get_or_create("卧室").id
    registry = dr.async_get(hass)
    device_entry = registry.async_get_device(identifiers={("xiaodu", "dev_area")})
    assert device_entry is not None
    registry.async_update_device(device_entry.id, area_id=bedroom)
    await hass.async_block_till_done()

    nick_calls = [c for c in aioclient_mock.mock_calls if "modifyName" in str(c[1])]
    assert len(nick_calls) == 1
    assert nick_calls[0][2]["name"] == "卧室主灯"
    room_calls = [
        c for c in aioclient_mock.mock_calls if "changeTopicRoom" in str(c[1])
    ]
    assert len(room_calls) == 1
    assert room_calls[0][2]["room"] == "卧室"


async def test_listener_area_rename_syncs_affected_devices(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """区域改名 → 事件监听器同步所有指向该区域的设备。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_arearen",
        friendly_name="吊灯",
        room_name="客厅",
        appliance_types=["LIGHT"],
    )
    # 先建立 device_entry（分配到「客厅」），再首刷建立映射
    register_xiaodu_device(hass, "dev_arearen", area_name="客厅", device_name="吊灯")
    await manager.sync_devices([device], {"客厅": "客厅"})
    _register_listener(hass, manager, device)
    aioclient_mock.mock_calls.clear()

    # 区域「客厅」改名为「大客厅」（触发 EVENT_AREA_REGISTRY_UPDATED）
    from homeassistant.helpers import area_registry as ar

    area_reg = ar.async_get(hass)
    for a in area_reg.async_list_areas():
        if a.name == "客厅":
            area_reg.async_update(a.id, name="大客厅")
            break
    await hass.async_block_till_done()

    nick_calls = [c for c in aioclient_mock.mock_calls if "modifyName" in str(c[1])]
    assert len(nick_calls) == 1
    assert nick_calls[0][2]["name"] == "大客厅吊灯"


async def test_listener_ignores_unrelated_device_changes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """与昵称/区域无关的字段变更（如 model）不触发同步。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_model",
        friendly_name="吊灯",
        room_name="客厅",
        appliance_types=["LIGHT"],
    )
    # 先建立 device_entry + 映射，再监听
    register_xiaodu_device(hass, "dev_model", area_name="客厅", device_name="吊灯")
    await manager.sync_devices([device], {"客厅": "客厅"})
    _register_listener(hass, manager, device)
    aioclient_mock.mock_calls.clear()

    # 改 model（不在 name_by_user/name/area_id 监听范围内）
    from homeassistant.helpers import device_registry as dr

    registry = dr.async_get(hass)
    device_entry = registry.async_get_device(identifiers={("xiaodu", "dev_model")})
    assert device_entry is not None
    registry.async_update_device(device_entry.id, model="NewModel")
    await hass.async_block_till_done()

    assert not any(
        "modifyName" in str(c[1]) or "changeTopicRoom" in str(c[1])
        for c in aioclient_mock.mock_calls
    )


async def test_listener_unsub_stops_sync(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """注销监听器后，设备改名不再触发同步。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json={"code": 0})
    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, json={"code": 0})
    manager = _manager(hass)
    device = Device(
        appliance_id="dev_unsub",
        friendly_name="吊灯",
        room_name="客厅",
        appliance_types=["LIGHT"],
    )
    # 先建立 device_entry + 映射，再监听后立即注销
    register_xiaodu_device(hass, "dev_unsub", area_name="客厅", device_name="吊灯")
    await manager.sync_devices([device], {"客厅": "客厅"})
    _coordinator, unsub = _register_listener(hass, manager, device)
    unsub()
    aioclient_mock.mock_calls.clear()

    # 注销后再改名，不应触发同步
    from homeassistant.helpers import device_registry as dr

    registry = dr.async_get(hass)
    device_entry = registry.async_get_device(identifiers={("xiaodu", "dev_unsub")})
    assert device_entry is not None
    registry.async_update_device(device_entry.id, name_by_user="改名后")
    await hass.async_block_till_done()

    assert not any("modifyName" in str(c[1]) for c in aioclient_mock.mock_calls)


async def test_get_device_list_empty(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """空设备列表（device_list_ok.json 的 data.array 为空）。"""
    aioclient_mock.get(
        BEMFA_DEVICE_LIST_URL,
        json=load_json_fixture("device_list_ok.json", "bemfa"),
    )
    api = BemfaAPIClient(
        TEST_BEMFA_UID,
        async_get_clientsession(hass),
    )
    devices = await api.get_device_list()
    assert devices == []


async def test_get_device_list_parses_devices(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """设备列表解析：topic/type/name 字段 + openID（base64 用户私钥）。"""
    payload = copy.deepcopy(load_json_fixture("device_list_ok.json", "bemfa"))
    payload["data"]["array"] = [
        {"topic": "xdu1234567890a001", "type": 2, "name": "客厅灯"},
        {"topic": "xdu1234567890a002", "type": 6, "name": "开关"},
    ]
    aioclient_mock.get(
        BEMFA_DEVICE_LIST_URL,
        json=payload,
    )
    api = BemfaAPIClient(
        TEST_BEMFA_UID,
        async_get_clientsession(hass),
    )
    devices = await api.get_device_list()
    assert [(d.topic, d.device_type, d.name) for d in devices] == [
        ("xdu1234567890a001", "2", "客厅灯"),
        ("xdu1234567890a002", "6", "开关"),
    ]


async def test_control_device_sends_command(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """设备控制：openID/topicID/type/message 请求体 + 成功判定。"""
    aioclient_mock.post(
        BEMFA_DEVICE_CONTROL_URL,
        json=load_json_fixture("control_device_ok.json", "bemfa"),
    )
    api = BemfaAPIClient(
        TEST_BEMFA_UID,
        async_get_clientsession(hass),
    )
    result = await api.control_device(
        "xdu1234567890a001", {"on": True, "bri": 80}, device_type=2
    )
    assert result is True

    calls = [c for c in aioclient_mock.mock_calls if "postMassage" in str(c[1])]
    assert len(calls) == 1
    body = calls[0][2]
    expected_open_id = base64.b64encode(TEST_BEMFA_UID.encode()).decode()
    assert body["openID"] == expected_open_id
    assert body["topicID"] == "xdu1234567890a001"
    assert body["type"] == 2
    assert body["message"] == {"on": True, "bri": 80}


async def test_api_request_non_dict_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """_request 收到非 dict 响应时返回 None 并判定失败。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, json=[1, 2, 3])
    api = BemfaAPIClient(TEST_BEMFA_UID, async_get_clientsession(hass))
    result = await api.create_topic("xdu1234567890a001", "灯")
    assert result.success is False


async def test_api_request_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """_request 超时（TimeoutError）时返回 None 并判定失败。"""
    aioclient_mock.post(BEMFA_CREATE_TOPIC_V1_URL, exc=TimeoutError("timeout"))
    api = BemfaAPIClient(TEST_BEMFA_UID, async_get_clientsession(hass))
    result = await api.create_topic("xdu1234567890a001", "灯")
    assert result.success is False


async def test_delete_topic_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """deleteTopic 无响应与失败码分支（side_effect 按调用次数区分）。"""
    api = BemfaAPIClient(TEST_BEMFA_UID, async_get_clientsession(hass))
    call_count = 0

    async def _side_effect(
        method: str, url: str, data: dict[str, Any] | None
    ) -> AiohttpClientMockResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AiohttpClientMockResponse(method, url, status=500, json=None)
        return AiohttpClientMockResponse(method, url, status=200, json={"code": 1})

    aioclient_mock.post(BEMFA_DELETE_TOPIC_URL, side_effect=_side_effect)
    assert await api.delete_topic("xdu1234567890a001") is False
    assert await api.delete_topic("xdu1234567890a001") is False


async def test_change_topic_room_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """changeTopicRoom 无响应与失败码分支（side_effect 按调用次数区分）。"""
    api = BemfaAPIClient(TEST_BEMFA_UID, async_get_clientsession(hass))
    call_count = 0

    async def _side_effect(
        method: str, url: str, data: dict[str, Any] | None
    ) -> AiohttpClientMockResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AiohttpClientMockResponse(method, url, status=500, json=None)
        return AiohttpClientMockResponse(method, url, status=200, json={"code": 1})

    aioclient_mock.post(BEMFA_CHANGE_ROOM_URL, side_effect=_side_effect)
    assert await api.change_topic_room(["xdu1234567890a001"], "客厅") is False
    assert await api.change_topic_room(["xdu1234567890a001"], "客厅") is False


async def test_change_topic_group_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """changeTopicGroup 无响应与失败码分支（side_effect 按调用次数区分）。"""
    api = BemfaAPIClient(TEST_BEMFA_UID, async_get_clientsession(hass))
    call_count = 0

    async def _side_effect(
        method: str, url: str, data: dict[str, Any] | None
    ) -> AiohttpClientMockResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AiohttpClientMockResponse(method, url, status=500, json=None)
        return AiohttpClientMockResponse(method, url, status=200, json={"code": 1})

    aioclient_mock.post(BEMFA_CHANGE_GROUP_URL, side_effect=_side_effect)
    assert await api.change_topic_group(["xdu1234567890a001"], "默认分组") is False
    assert await api.change_topic_group(["xdu1234567890a001"], "默认分组") is False


async def test_modify_name_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """modifyName 无响应与失败码分支（注入测试 URL 避开 autouse 默认端点）。"""
    api = BemfaAPIClient(
        TEST_BEMFA_UID,
        async_get_clientsession(hass),
        modify_name_url="https://test.local/modify",
    )
    call_count = 0

    async def _side_effect(
        method: str, url: str, data: dict[str, Any] | None
    ) -> AiohttpClientMockResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AiohttpClientMockResponse(method, url, status=500, json=None)
        return AiohttpClientMockResponse(method, url, status=200, json={"code": 1})

    aioclient_mock.post("https://test.local/modify", side_effect=_side_effect)
    assert await api.modify_name("xdu1234567890a001", "灯") is False
    assert await api.modify_name("xdu1234567890a001", "灯") is False


async def test_list_topics_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """listTopics 无响应、失败码、异常响应结构分支（side_effect 按调用区分）。"""
    api = BemfaAPIClient(
        TEST_BEMFA_UID,
        async_get_clientsession(hass),
        all_topic_url="https://test.local/alltopic",
    )
    call_count = 0

    async def _side_effect(
        method: str, url: str, data: dict[str, Any] | None
    ) -> AiohttpClientMockResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AiohttpClientMockResponse(method, url, status=500, json=None)
        if call_count == 2:
            return AiohttpClientMockResponse(method, url, status=200, json={"code": 1})
        return AiohttpClientMockResponse(
            method, url, status=200, json={"code": 0, "data": {"nope": 1}}
        )

    aioclient_mock.get("https://test.local/alltopic", side_effect=_side_effect)
    assert await api.list_topics() is None
    assert await api.list_topics() is None
    assert await api.list_topics() is None


async def test_get_device_list_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """get_device_list 无响应、失败码、异常响应结构分支（side_effect 区分）。"""
    api = BemfaAPIClient(TEST_BEMFA_UID, async_get_clientsession(hass))
    call_count = 0

    async def _side_effect(
        method: str, url: str, data: dict[str, Any] | None
    ) -> AiohttpClientMockResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AiohttpClientMockResponse(method, url, status=500, json=None)
        if call_count == 2:
            return AiohttpClientMockResponse(method, url, status=200, json={"code": 1})
        if call_count == 3:
            return AiohttpClientMockResponse(
                method, url, status=200, json={"code": 0, "data": "oops"}
            )
        return AiohttpClientMockResponse(
            method, url, status=200, json={"code": 0, "data": {"array": "oops"}}
        )

    aioclient_mock.get(BEMFA_DEVICE_LIST_URL, side_effect=_side_effect)
    assert await api.get_device_list() == []
    assert await api.get_device_list() == []
    assert await api.get_device_list() == []
    assert await api.get_device_list() == []


async def test_control_device_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """control_device 无响应与失败码分支（side_effect 按调用次数区分）。"""
    api = BemfaAPIClient(TEST_BEMFA_UID, async_get_clientsession(hass))
    call_count = 0

    async def _side_effect(
        method: str, url: str, data: dict[str, Any] | None
    ) -> AiohttpClientMockResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AiohttpClientMockResponse(method, url, status=500, json=None)
        return AiohttpClientMockResponse(method, url, status=200, json={"code": 1})

    aioclient_mock.post(BEMFA_DEVICE_CONTROL_URL, side_effect=_side_effect)
    assert await api.control_device("xdu1234567890a001", {"on": True}, 2) is False
    assert await api.control_device("xdu1234567890a001", {"on": True}, 2) is False
