"""Tests for the Xiaodu coordinator.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.xiaodu.api.xiaodu_client import HOST
from custom_components.xiaodu.api.xiaodu_types import Command
from custom_components.xiaodu.const import (
    CONF_COOKIE,
    CONF_HOUSE_ID,
    CONF_HOUSE_NAME,
    DOMAIN,
)
from tests.conftest import load_json_fixture
from tests.const import TEST_COOKIE, TEST_HOUSE_ID, TEST_HOUSE_NAME, TEST_ROOM_NAME


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
