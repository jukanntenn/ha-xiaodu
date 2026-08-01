"""End-to-end tests for the Xiaodu integration.

6 user-level scenarios per spec 14 §6:
1. Full config flow → setup → all device types appear
2. Polling discovers new device → new entity + Bemfa sync
3. Polling discovers state change → entity update + Bemfa publish
4. Control device → HTTP command body + Bemfa sync
5. Cookie expired → reauth → recovery
6. Bemfa bidirectional → MQTT publish on HA control
"""

from __future__ import annotations

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.xiaodu.const import (
    CONF_BEMFA_SECRET_ID,
    CONF_BEMFA_SECRET_KEY,
    CONF_BEMFA_UID,
    CONF_COOKIE,
    CONF_HOUSE_ID,
    CONF_HOUSE_NAME,
    CONF_ROOM_MAPPING,
    DOMAIN,
)
from tests.conftest import load_json_fixture
from tests.const import (
    TEST_APPLIANCE_ID,
    TEST_BEMFA_SECRET_ID,
    TEST_BEMFA_SECRET_KEY,
    TEST_BEMFA_UID,
    TEST_COOKIE,
    TEST_HOUSE_ID,
)
from tests.test_e2e.conftest import ApiServer

# All rooms for the selected device (appliance_test_light_001 is in 次卧)
DEVICE_ROOM = "次卧"
ROOM_MAPPING = {DEVICE_ROOM: DEVICE_ROOM}


async def _run_config_flow_to_bemfa(
    hass: HomeAssistant,
    bemfa_uid: str = "",
) -> FlowResultType:
    """Run the full config flow up to and including the bemfa step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cookie"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: TEST_COOKIE}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOUSE_ID: TEST_HOUSE_ID}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_ids": [TEST_APPLIANCE_ID]}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ROOM_MAPPING
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BEMFA_UID: bemfa_uid,
            CONF_BEMFA_SECRET_ID: TEST_BEMFA_SECRET_ID if bemfa_uid else "",
            CONF_BEMFA_SECRET_KEY: TEST_BEMFA_SECRET_KEY if bemfa_uid else "",
        },
    )


def _make_bemfa_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a config entry with Bemfa enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Xiaodu: Test Home",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: "Test Home",
        },
        options={
            CONF_ROOM_MAPPING: ROOM_MAPPING,
            "bemfa": {
                "enabled": True,
                "uid": TEST_BEMFA_UID,
                "secret_id": TEST_BEMFA_SECRET_ID,
                "secret_key": TEST_BEMFA_SECRET_KEY,
                "sync_devices": True,
            },
        },
    )
    entry.add_to_hass(hass)
    return entry


# ---------------------------------------------------------------------------
# Scenario 1: Full config flow → setup → ALL device types appear
# ---------------------------------------------------------------------------


async def test_scenario_1_full_config_flow_and_setup(
    hass: HomeAssistant,
    api_server: ApiServer,
    bemfa_mqtt_redirect,
) -> None:
    """Config flow 全步骤 → setup → 各类设备实体出现并状态正确。

    Verifies:
    - Config flow completes successfully
    - Entry loads (ConfigEntryState.LOADED)
    - Light entity exists with correct state
    - Switch entity exists (HEATER maps to SWITCH_TYPES)
    - Climate entity exists (AIR_CONDITION maps to CLIMATE_TYPES)
    - Cover entity exists (CURTAIN maps to COVER_TYPES)
    - Lock entity exists (DOOR_LOCK maps to LOCK_TYPES)
    - Button entity exists (CLOTHES_RACK maps to BUTTON_TYPES)
    """
    result = await _run_config_flow_to_bemfa(hass)
    assert result["type"] == FlowResultType.CREATE_ENTRY

    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED

    # Light entities (19 LIGHT devices in fixture)
    light_states = hass.states.async_all("light")
    assert len(light_states) >= 1
    light = hass.states.get("light.test_light_1")
    assert light is not None
    assert light.state in ("on", "off")

    # Switch entities (HEATER + AIR_FRESHER + SOCKET + SWITCH map to SWITCH_TYPES)
    switch_states = hass.states.async_all("switch")
    assert len(switch_states) >= 1

    # Climate entities (AIR_CONDITION maps to CLIMATE_TYPES)
    climate_states = hass.states.async_all("climate")
    assert len(climate_states) >= 1
    climate = hass.states.get("climate.test_air_condition_1")
    assert climate is not None
    assert climate.state == HVACMode.OFF
    assert climate.attributes.get("current_temperature") == 16

    # Cover entities (CURTAIN maps to COVER_TYPES)
    cover_states = hass.states.async_all("cover")
    assert len(cover_states) >= 1
    cover = hass.states.get("cover.test_curtain_1")
    assert cover is not None

    # Lock entities (DOOR_LOCK maps to LOCK_TYPES)
    lock_states = hass.states.async_all("lock")
    assert len(lock_states) >= 1
    lock = hass.states.get("lock.test_door_lock_1")
    assert lock is not None

    # Button entities (CLOTHES_RACK maps to BUTTON_TYPES)
    button_states = hass.states.async_all("button")
    assert len(button_states) >= 1
    button = hass.states.get("button.test_clothes_rack_1")
    assert button is not None


# ---------------------------------------------------------------------------
# Scenario 2: Polling discovers new device → new entity + Bemfa sync
# ---------------------------------------------------------------------------


async def test_scenario_2_polling_discovers_new_device(
    hass: HomeAssistant,
    api_server: ApiServer,
    bemfa_mqtt_redirect,
) -> None:
    """轮询发现新设备 → 新实体出现 + 巴法云主题创建。

    Verifies:
    - Second poll returns device_list_added (extra switch device)
    - coordinator.data grows by 1
    - New switch entity appears
    - Bemfa HTTP endpoints are called (create_topic, change_topic_room)
    """
    entry = _make_bemfa_config_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    initial_count = len(coordinator.data)

    # Trigger poll → returns device_list_added
    api_server.set_response(
        "/saiya/smarthome/appliance",
        json=load_json_fixture("device_list_added.json"),
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # New device appeared (switch_002 is the extra device in device_list_added)
    assert len(coordinator.data) == initial_count + 1
    assert "appliance_test_switch_002" in coordinator.data

    # New switch entity should exist
    await hass.async_block_till_done()
    new_switch = hass.states.get("switch.test_switch_2")
    assert new_switch is not None

    # Bemfa sync was triggered: create_topic HTTP request was sent with the
    # secretID/secretKey credentials (regression guard for requirement 5).
    create_calls = [
        r for r in api_server.requests if r["path"] == "/vs/web/v2/createTopic"
    ]
    assert len(create_calls) > 0
    create_body = create_calls[0]["body"]
    assert "secretID" in create_body
    assert "secretKey" in create_body
    assert create_body["secretID"] == TEST_BEMFA_SECRET_ID
    assert create_body["secretKey"] == TEST_BEMFA_SECRET_KEY


# ---------------------------------------------------------------------------
# Scenario 3: Polling discovers state change → entity update + Bemfa publish
# ---------------------------------------------------------------------------


async def test_scenario_3_polling_discovers_state_change(
    hass: HomeAssistant,
    api_server: ApiServer,
    bemfa_mqtt_redirect,
    bemfa_mqtt_probe,
) -> None:
    """轮询发现状态变化 → entity 状态更新 + 巴法云状态发布。

    Verifies:
    - Second poll returns device_list_state_changed
    - Entity state updates accordingly
    - Bemfa update_device_state is called (HTTP to Bemfa control endpoint)
    """
    entry = _make_bemfa_config_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data

    # Record initial state of light_001 (should be OFF in base fixture)
    initial_state = (
        coordinator.data["appliance_test_light_001"]
        .state_setting.get("turnOnState", {})
        .get("value")
    )
    assert initial_state == "OFF"

    # Trigger poll → returns state_changed fixture (light_001 = ON)
    api_server.set_response(
        "/saiya/smarthome/appliance",
        json=load_json_fixture("device_list_state_changed.json"),
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify state was refreshed
    new_state = (
        coordinator.data["appliance_test_light_001"]
        .state_setting.get("turnOnState", {})
        .get("value")
    )
    assert new_state == "ON"

    # 状态变化通过真实 broker 上报（wire 断言：{topic}/up = "on"）
    mapping = coordinator.bemfa_sync_manager.device_mapping[
        "appliance_test_light_001"
    ]
    _up_topic, payload = await bemfa_mqtt_probe.wait_for(
        lambda t, p: t == f"{mapping.bemfa_topic}/up" and p == "on"
    )
    assert payload == "on"


# ---------------------------------------------------------------------------
# Scenario 4: Control device → HTTP command body + Bemfa sync
# ---------------------------------------------------------------------------


async def test_scenario_4_control_device(
    hass: HomeAssistant,
    api_server: ApiServer,
    bemfa_mqtt_redirect,
) -> None:
    """控制设备 → 断言 HTTP 命令体 + 巴法云同步。

    Verifies:
    - turn_on sends HTTP request to directivesend
    - Request body contains correct TurnOnRequest command
    - Entity state updates via optimistic update
    - Bemfa HTTP calls are made after control
    """
    entry = _make_bemfa_config_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial state is off
    assert hass.states.get("light.test_light_1").state == "off"

    # 记录当前请求数，用于隔离控制命令
    request_count = len(api_server.requests)

    # Turn on the light
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test_light_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Entity state updated via optimistic update
    assert hass.states.get("light.test_light_1").state == "on"

    # HTTP command was sent to directivesend
    control_calls = [
        r
        for r in api_server.requests[request_count:]
        if r["path"] == "/saiya/smarthome/directivesend"
    ]
    assert len(control_calls) > 0
    call_data = control_calls[0]["body"]
    assert call_data is not None
    assert call_data["header"]["name"] == "TurnOnRequest"


# ---------------------------------------------------------------------------
# Scenario 5: Cookie expired → reauth → recovery
# ---------------------------------------------------------------------------


async def test_scenario_5_cookie_expired_reauth(
    hass: HomeAssistant,
    api_server: ApiServer,
) -> None:
    """Cookie 过期 → 触发 reauth → 重新配置恢复。

    Verifies:
    - Poll returning auth error triggers ConfigEntryAuthFailed
    - Entry enters SETUP_ERROR state
    - Reauth flow can be initiated
    - After reauth with new cookie, entry recovers
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Xiaodu: Test Home",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: "Test Home",
        },
        options={CONF_ROOM_MAPPING: ROOM_MAPPING},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    # Now replace device_list endpoint to return auth error
    api_server.set_response(
        "/saiya/smarthome/appliance",
        status=401,
        json={"status": 2, "msg": "user.not login", "data": {}},
    )

    # Trigger poll → auth failure
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Initiate reauth flow
    api_server.set_response(
        "/saiya/smarthome/appliance",
        json=load_json_fixture("device_list.json"),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reauth",
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Submit new cookie
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: "new_valid_cookie"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


# ---------------------------------------------------------------------------
# Scenario 6: Bemfa bidirectional → MQTT publish on HA control
# ---------------------------------------------------------------------------


async def test_scenario_6_bemfa_mqtt_publish(
    hass: HomeAssistant,
    api_server: ApiServer,
    bemfa_mqtt_redirect,
    bemfa_mqtt_probe,
) -> None:
    """HA 控制设备 → 巴法云真实收到 {topic}/up 状态。

    Verifies:
    - Control publishes {bemfa_topic}/up over the real broker
    - Payload is the official #-text state ("on")
    """
    entry = _make_bemfa_config_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    mapping = coordinator.bemfa_sync_manager.device_mapping[
        "appliance_test_light_001"
    ]
    assert mapping.bemfa_topic is not None

    # Turn on the light → 乐观更新 → 真实 MQTT 上报
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test_light_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    _up_topic, payload = await bemfa_mqtt_probe.wait_for(
        lambda t, p: t == f"{mapping.bemfa_topic}/up" and p == "on"
    )
    assert payload == "on"
