"""Tests for the Xiaodu coordinator.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.xiaodu.api.xiaodu_client import HOST, XiaoduAPI
from custom_components.xiaodu.api.xiaodu_types import Command, Device
from custom_components.xiaodu.const import (
    CONF_COOKIE,
    CONF_HOUSE_ID,
    CONF_HOUSE_NAME,
    DOMAIN,
)
from custom_components.xiaodu.coordinator import XiaoduCoordinator
from tests.conftest import load_json_fixture
from tests.const import TEST_COOKIE, TEST_HOUSE_ID, TEST_HOUSE_NAME, TEST_ROOM_NAME

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_coordinator_update_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test coordinator.data is populated after setup with device fixtures."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is not None
    assert len(coordinator.data) > 0
    # Verify a known device from fixture
    assert "appliance_test_light_001" in coordinator.data
    device = coordinator.data["appliance_test_light_001"]
    assert device.friendly_name == "Test Light 1"
    assert device.appliance_types == ["LIGHT"]


async def test_coordinator_auth_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup fails with ConfigEntryAuthFailed when API returns auth error."""
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/appliance",
        json=load_json_fixture("check_session_not_login.json"),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is not ConfigEntryState.LOADED


async def test_locked_devices_preserved(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test that locked devices are not overwritten by polling."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # Fixture has turnOnState.value="OFF" for light 001
    device = coordinator.data["appliance_test_light_001"]
    assert device.state_setting["turnOnState"]["value"] == "OFF"

    # Apply optimistic state which locks the device for 5 seconds
    coordinator.update_device_state_immediately(
        "appliance_test_light_001", {"turnOnState": "on"}
    )
    device = coordinator.data["appliance_test_light_001"]
    assert device.state_setting["turnOnState"]["value"] == "on"
    assert "appliance_test_light_001" in coordinator._locked_devices

    # Refresh - API returns original fixture data (OFF), but lock preserves "on"
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    device = coordinator.data["appliance_test_light_001"]
    assert device.state_setting["turnOnState"]["value"] == "on"


async def test_control_device_with_optimistic_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test control_device applies optimistic state and locks the device."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # Verify initial state is OFF
    device = coordinator.data["appliance_test_light_001"]
    assert device.state_setting["turnOnState"]["value"] == "OFF"

    # Control with optimistic state
    result = await coordinator.control_device(
        "appliance_test_light_001",
        Command(action="turnOn"),
        optimistic_state={"turnOnState": "on"},
    )

    assert result is True
    # Optimistic state applied
    assert device.state_setting["turnOnState"]["value"] == "on"
    # Device is locked
    assert "appliance_test_light_001" in coordinator._locked_devices


async def test_room_mapping_property(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test room_mapping property returns the config entry options mapping."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    mapping = coordinator.room_mapping
    assert isinstance(mapping, dict)
    assert mapping == {TEST_ROOM_NAME: TEST_ROOM_NAME}


async def test_devices_property(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test devices property returns current data dict and empty dict when no data."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    devices = coordinator.devices
    assert len(devices) > 0
    assert devices is coordinator.data

    # When data is None, devices returns empty dict
    coordinator.data = None
    assert coordinator.devices == {}


async def test_coordinator_device_count_all_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test coordinator loads all device types from fixture (31 devices)."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert len(coordinator.data) == 31

    # Verify specific device types exist
    type_ids = {
        "LIGHT": "appliance_test_light_001",
        "AIR_CONDITION": "appliance_test_air_condition_001",
        "HEATER": "appliance_test_heater_001",
        "AIR_FRESHER": "appliance_test_air_fresher_001",
        "SOCKET": "appliance_test_socket_001",
        "SWITCH": "appliance_test_switch_001",
        "CURTAIN": "appliance_test_curtain_001",
        "DOOR_LOCK": "appliance_test_door_lock_001",
        "CLOTHES_RACK": "appliance_test_clothes_rack_001",
    }
    for dev_type, dev_id in type_ids.items():
        assert dev_id in coordinator.data, f"Missing {dev_type} device: {dev_id}"
        assert dev_type in coordinator.data[dev_id].appliance_types


async def test_coordinator_state_changed_fixture(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test coordinator detects state change when fixture differs.

    Uses device_list_state_changed.json where light_008 has turnOnState=ON
    instead of OFF.
    """
    # First call returns base device_list, second returns state_changed
    call_count = 0

    async def _side_effect(method, url, data):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            fixture = "device_list.json"
        else:
            fixture = "device_list_state_changed.json"
        return AiohttpClientMockResponse(
            method=method,
            url=url,
            status=200,
            json=load_json_fixture(fixture),
        )

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
        side_effect=_side_effect,
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/appliancedetails",
        json=load_json_fixture("device_detail_light.json"),
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/directivesend",
        json=load_json_fixture("control_response_ok.json"),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Xiaodu: Test Home",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data

    # Initial state: light_001 is OFF
    assert (
        coordinator.data["appliance_test_light_001"].state_setting["turnOnState"][
            "value"
        ]
        == "OFF"
    )

    # Refresh → state_changed fixture → light_001 should be ON
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        coordinator.data["appliance_test_light_001"].state_setting["turnOnState"][
            "value"
        ]
        == "ON"
    )


async def test_coordinator_control_device_returns_true(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test control_device returns True on success."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    result = await coordinator.control_device(
        "appliance_test_light_001",
        Command(action="turnOn"),
    )
    assert result is True


async def test_coordinator_control_device_without_optimistic(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test control_device without optimistic_state still succeeds."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # State should remain unchanged (no optimistic update)
    device = coordinator.data["appliance_test_light_001"]
    original_state = device.state_setting["turnOnState"]["value"]

    result = await coordinator.control_device(
        "appliance_test_light_001",
        Command(action="turnOn"),
        optimistic_state=None,
    )
    assert result is True
    # State unchanged (no optimistic update applied)
    assert device.state_setting["turnOnState"]["value"] == original_state


async def test_coordinator_business_auth_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """业务层认证错误（HTTP 200 + error_401.json）→ ConfigEntryAuthFailed → setup 失败。"""
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
        json=load_json_fixture("error_401.json"),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Xiaodu: Test Home",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is not ConfigEntryState.LOADED


async def test_coordinator_device_not_found(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """设备列表接口 404（error_404.json）→ XiaoduNotFoundError → setup 失败。"""
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
        status=404,
        json=load_json_fixture("error_404.json"),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Xiaodu: Test Home",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is not ConfigEntryState.LOADED


async def test_coordinator_rate_limit(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch,
) -> None:
    """限流（HTTP 429 + error_429.json）→ API 层重试后失败 → setup 失败。"""
    monkeypatch.setattr(
        "custom_components.xiaodu.api.xiaodu_client.RETRY_DELAYS",
        [0.01, 0.01, 0.01],
    )
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
        status=429,
        json=load_json_fixture("error_429.json"),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Xiaodu: Test Home",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is not ConfigEntryState.LOADED


async def test_coordinator_business_api_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch,
) -> None:
    """业务层错误（HTTP 200 + error_network.json）→ XiaoduApiError → coordinator 重试后失败。"""
    monkeypatch.setattr(
        "custom_components.xiaodu.coordinator.RETRY_DELAYS",
        [0.01, 0.01, 0.01],
    )
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
        json=load_json_fixture("error_network.json"),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Xiaodu: Test Home",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is not ConfigEntryState.LOADED


async def test_coordinator_device_removed_fixture(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """设备被移除（device_list_removed.json 无 air_fresher_001）。"""
    call_count = 0

    async def _side_effect(method, url, data):
        nonlocal call_count
        call_count += 1
        fixture = "device_list.json" if call_count <= 1 else "device_list_removed.json"
        return AiohttpClientMockResponse(
            method=method,
            url=url,
            status=200,
            json=load_json_fixture(fixture),
        )

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
        side_effect=_side_effect,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Xiaodu: Test Home",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert "appliance_test_air_fresher_001" in coordinator.data

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert "appliance_test_air_fresher_001" not in coordinator.data
    assert "appliance_test_light_001" in coordinator.data


async def test_refresh_skipped_during_cooldown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    aioclient_mock_fixture: None,
) -> None:
    """手动刷新冷却期内跳过更新，直接返回现有数据。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator._last_manual_refresh = time.time()
    aioclient_mock.mock_calls.clear()

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    appliance_calls = [c for c in aioclient_mock.mock_calls if "appliance" in str(c[1])]
    assert appliance_calls == []


async def test_handle_bemfa_sync_without_manager(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """未启用 Bemfa 时同步函数直接返回。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    await coordinator._handle_bemfa_sync([])


async def test_publish_state_changes_without_manager(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """未启用 Bemfa 时状态发布直接返回。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    await coordinator._publish_state_changes({})


def _device(appliance_id: str = "appliance_test_light_001") -> Device:
    """构造一个最小的 Device（state_setting 含 turnOnState）。"""
    return Device(
        appliance_id=appliance_id,
        friendly_name="Test Light",
        room_name="次卧",
        appliance_types=["LIGHT"],
        state_setting={"turnOnState": {"value": "OFF"}},
    )


def _bemfa_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sync_manager,
) -> XiaoduCoordinator:
    """构造带假 Bemfa 同步管理器的 coordinator（API 走真实 mock）。"""
    api_client = XiaoduAPI(TEST_COOKIE, async_get_clientsession(hass), host=HOST)
    return XiaoduCoordinator(hass, mock_config_entry, api_client, sync_manager)


async def test_publish_state_changes_bemfa_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Bemfa 状态发布抛异常时仅记日志不抛出。"""
    sync_manager = AsyncMock()
    sync_manager.update_device_state.side_effect = RuntimeError("boom")
    coordinator = _bemfa_coordinator(hass, mock_config_entry, sync_manager)
    old_device = _device()
    new_device = _device()
    new_device.state_setting["turnOnState"]["value"] = "on"
    coordinator.data = {"appliance_test_light_001": old_device}

    await coordinator._publish_state_changes({"appliance_test_light_001": new_device})
    sync_manager.update_device_state.assert_awaited_once()


async def test_handle_bemfa_command_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """空指令列表直接返回。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    await coordinator.handle_bemfa_command("appliance_test_light_001", [])


async def test_handle_bemfa_command_set_temperature_missing_params(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """setTemperature 缺少参数时跳过并记录警告。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    await coordinator.handle_bemfa_command(
        "appliance_test_light_001", [Command(action="setTemperature")]
    )


async def test_optimistic_state_branches() -> None:
    """指令 → 乐观状态映射全分支（静态方法）。"""
    from custom_components.xiaodu.coordinator import XiaoduCoordinator

    assert XiaoduCoordinator._optimistic_state(Command(action="turnOn")) == {
        "turnOnState": "on"
    }
    assert XiaoduCoordinator._optimistic_state(Command(action="turnOff")) == {
        "turnOnState": "off"
    }
    assert XiaoduCoordinator._optimistic_state(
        Command(action="setBrightness", params={"attributeValue": 50})
    ) == {"turnOnState": "on", "brightness": 50}
    assert XiaoduCoordinator._optimistic_state(Command(action="setBrightness")) is None
    assert XiaoduCoordinator._optimistic_state(
        Command(action="setMode", params={"mode": "m1"})
    ) == {"mode": "m1"}
    assert XiaoduCoordinator._optimistic_state(Command(action="setMode")) is None
    assert XiaoduCoordinator._optimistic_state(
        Command(action="setFanSpeed", params={"speed": 3})
    ) == {"fanSpeed": 3}
    assert XiaoduCoordinator._optimistic_state(Command(action="setFanSpeed")) is None
    assert XiaoduCoordinator._optimistic_state(Command(action="unknown")) is None


async def test_adjust_temperature_branches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    aioclient_mock_fixture: None,
) -> None:
    """温度逼近循环：无设备、缺温度、零差值、正负差值。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    device = coordinator.data["appliance_test_light_001"]

    # 设备不存在 → 直接返回
    await coordinator.handle_bemfa_command(
        "appliance_missing", [Command(action="setTemperature", params={"target": 26})]
    )

    # 缺少 temperature 状态 → 直接返回
    await coordinator.handle_bemfa_command(
        "appliance_test_light_001",
        [Command(action="setTemperature", params={"target": 26})],
    )

    # 差值 0 → 不发送任何指令
    device.state_setting["temperature"] = {"value": 26}
    aioclient_mock.mock_calls.clear()
    await coordinator.handle_bemfa_command(
        "appliance_test_light_001",
        [Command(action="setTemperature", params={"target": 26})],
    )
    await hass.async_block_till_done()
    assert aioclient_mock.mock_calls == []

    # 目标更高 → 2 次 temperatureUp
    device.state_setting["temperature"] = {"value": 24}
    aioclient_mock.mock_calls.clear()
    await coordinator.handle_bemfa_command(
        "appliance_test_light_001",
        [Command(action="setTemperature", params={"target": 26})],
    )
    await hass.async_block_till_done()
    up_calls = [c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])]
    assert len(up_calls) == 2


async def test_apply_optimistic_state_bemfa_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """乐观更新时 Bemfa 发布异常仅记日志。"""
    sync_manager = AsyncMock()
    sync_manager.update_device_state.side_effect = RuntimeError("boom")
    coordinator = _bemfa_coordinator(hass, mock_config_entry, sync_manager)
    coordinator.data = {"appliance_test_light_001": _device()}

    await coordinator.apply_optimistic_state(
        "appliance_test_light_001", {"turnOnState": "on"}
    )
    sync_manager.update_device_state.assert_awaited_once()
    await coordinator.async_cancel_background_tasks()


async def test_update_device_state_immediately_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """无数据时立即更新直接返回。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.data = None
    coordinator.update_device_state_immediately(
        "appliance_test_light_001", {"turnOnState": "on"}
    )


async def test_update_device_state_immediately_scalar(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """stateSetting 中非 dict 值直接被替换。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    device = coordinator.data["appliance_test_light_001"]
    device.state_setting["scalarKey"] = 26
    coordinator.update_device_state_immediately(
        "appliance_test_light_001", {"scalarKey": 28}
    )
    assert device.state_setting["scalarKey"] == 28


async def test_refresh_after_delay(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """延迟刷新：设置冷却标记并发起刷新。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_request_refresh_after_delay(0.01)
    await hass.async_block_till_done()
    assert coordinator._last_manual_refresh > 0


async def test_async_update_data_with_bemfa(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """带 Bemfa 时更新流程：同步设备列表 + 发布状态变更。"""
    sync_manager = AsyncMock()
    sync_manager.sync_devices.return_value = None
    sync_manager.update_device_state.return_value = None
    coordinator = _bemfa_coordinator(hass, mock_config_entry, sync_manager)

    data = await coordinator._async_update_data()
    sync_manager.sync_devices.assert_awaited_once()
    assert data
    assert "appliance_test_light_001" in data

    # 状态变化后再次更新 → 发布状态变更
    coordinator.data = data
    device = data["appliance_test_light_001"]
    device.state_setting["turnOnState"]["value"] = "on"
    await coordinator._async_update_data()
    sync_manager.update_device_state.assert_awaited()


async def test_handle_bemfa_command_regular_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """常规下行指令走 control_device（非温度逼近）。"""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    await coordinator.handle_bemfa_command(
        "appliance_test_light_001", [Command(action="turnOn")]
    )
    await hass.async_block_till_done()

    device = coordinator.data["appliance_test_light_001"]
    assert device.state_setting["turnOnState"]["value"] == "on"


async def test_handle_bemfa_sync_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Bemfa 设备同步抛异常时仅记日志不阻断更新。"""
    sync_manager = AsyncMock()
    sync_manager.sync_devices.side_effect = RuntimeError("boom")
    coordinator = _bemfa_coordinator(hass, mock_config_entry, sync_manager)

    data = await coordinator._async_update_data()
    assert data


async def test_entity_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """device_info：设备存在时含名称/区域，缺失时回退。"""
    from custom_components.xiaodu.light import XiaoduLight

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    light = XiaoduLight(coordinator, "appliance_test_light_001")
    info = light.device_info
    assert info["identifiers"] == {(DOMAIN, "appliance_test_light_001")}
    assert info["name"] is not None
    assert info["suggested_area"] is not None
    assert light.appliance_id == "appliance_test_light_001"

    missing = XiaoduLight(coordinator, "appliance_missing")
    assert missing.device_info["name"] == "appliance_missing"


async def test_entity_added_to_hass_area_assignment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """async_added_to_hass：无房间/无映射/已分配时跳过，正常时分配区域。"""
    from homeassistant.helpers import device_registry as dr

    from custom_components.xiaodu.light import XiaoduLight

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    light = XiaoduLight(coordinator, "appliance_test_light_001")
    light.hass = hass
    await light.async_added_to_hass()

    registry = dr.async_get(hass)
    device_entry = registry.async_get_device(
        identifiers={(DOMAIN, "appliance_test_light_001")}
    )
    assert device_entry is not None
    assert device_entry.area_id is not None

    # 已分配区域时不再覆盖
    await light.async_added_to_hass()
    assert (
        registry.async_get_device(
            identifiers={(DOMAIN, "appliance_test_light_001")}
        ).area_id
        == device_entry.area_id
    )


async def test_entity_added_to_hass_skip_branches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """async_added_to_hass 的跳过分支：设备缺失、无房间、空映射。"""
    from custom_components.xiaodu.light import XiaoduLight

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    device = coordinator.data["appliance_test_light_001"]

    # 设备不存在
    missing = XiaoduLight(coordinator, "appliance_missing")
    missing.hass = hass
    await missing.async_added_to_hass()

    # 设备无房间名
    device.room_name = ""
    no_room = XiaoduLight(coordinator, "appliance_test_light_001")
    no_room.hass = hass
    await no_room.async_added_to_hass()

    # 房间映射到空值
    device.room_name = "次卧"
    empty_map = XiaoduLight(coordinator, "appliance_test_light_001")
    empty_map.hass = hass
    original_options = mock_config_entry.options
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**original_options, "room_mapping": {"次卧": ""}},
    )
    await empty_map.async_added_to_hass()
    hass.config_entries.async_update_entry(mock_config_entry, options=original_options)


async def test_entity_added_to_hass_unregistered_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """设备未注册时跳过分配；手动注册（无区域）后正常分配。"""
    from homeassistant.helpers import device_registry as dr

    from custom_components.xiaodu.light import XiaoduLight

    coordinator = _bemfa_coordinator(hass, mock_config_entry, None)
    coordinator.data = {"appliance_test_light_001": _device()}
    mock_config_entry.add_to_hass(hass)

    # 设备存在但 registry 无记录 → 跳过
    light = XiaoduLight(coordinator, "appliance_test_light_001")
    light.hass = hass
    await light.async_added_to_hass()

    # 手动注册设备（无区域）→ 正常分配
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        identifiers={(DOMAIN, "appliance_test_light_001")},
        config_entry_id=mock_config_entry.entry_id,
        manufacturer="Xiaodu",
    )
    await light.async_added_to_hass()
    device_entry = registry.async_get_device(
        identifiers={(DOMAIN, "appliance_test_light_001")}
    )
    assert device_entry is not None
    assert device_entry.area_id is not None
