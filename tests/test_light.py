"""Tests for the Xiaodu light platform.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
LIGHT devices map to light entities.
"""

from __future__ import annotations

import copy

import pytest
from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.xiaodu.api.xiaodu_client import HOST
from tests.conftest import load_json_fixture


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_light_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light entity is created with correct state and color mode.

    The fixture lights have no brightness/colorTemperatureInKelvin at the
    top level of stateSetting, so color_mode should be ONOFF.
    All fixture lights have turnOnState.value="OFF", so state is "off".
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light_1")
    assert state is not None
    assert state.state == "off"
    # When light is off, color_mode is None; supported_color_modes is set
    assert ColorMode.ONOFF in state.attributes.get("supported_color_modes", [])


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_light_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning a light on updates entity state via optimistic update."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("light.test_light_1").state == "off"

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test_light_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light_1")
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_light_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning a light off updates entity state via optimistic update."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn on first so we can verify turning off
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test_light_1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("light.test_light_1").state == "on"

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.test_light_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light_1")
    assert state is not None
    assert state.state == "off"


async def test_light_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test light with brightness in stateSetting reports BRIGHTNESS color mode.

    Creates a custom fixture response that includes brightness at the top level
    of stateSetting (the real fixture only has it nested under mode).
    """
    # Build a modified device list with brightness in stateSetting for light 1
    device_list = copy.deepcopy(load_json_fixture("device_list.json"))
    device_list["data"]["appliances"][0]["stateSetting"]["brightness"] = {
        "name": "亮度",
        "value": 80,
        "valueType": "NUM",
        "scale": "%",
        "valueRangeMap": {"min": 1, "max": 100},
        "time": "2026-07-25 00:00:00",
    }

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
        json=device_list,
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/appliancedetails",
        json=load_json_fixture("device_detail_light.json"),
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/directivesend",
        json=load_json_fixture("control_response_ok.json"),
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light_1")
    assert state is not None
    assert state.state == "off"
    # With brightness (but no colorTemperatureInKelvin) → BRIGHTNESS supported
    assert ColorMode.BRIGHTNESS in state.attributes.get("supported_color_modes", [])


async def test_light_with_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test light with brightness + colorTemperatureInKelvin reports COLOR_TEMP mode."""
    device_list = copy.deepcopy(load_json_fixture("device_list.json"))
    device_list["data"]["appliances"][0]["stateSetting"]["brightness"] = {
        "name": "亮度",
        "value": 80,
        "valueType": "NUM",
        "scale": "%",
        "valueRangeMap": {"min": 1, "max": 100},
        "time": "2026-07-25 00:00:00",
    }
    device_list["data"]["appliances"][0]["stateSetting"]["colorTemperatureInKelvin"] = {
        "name": "色温",
        "value": 50,
        "valueType": "NUM",
        "scale": "%",
        "valueKelvinRangeMap": {"min": 2700, "max": 6500},
        "time": "2026-07-25 00:00:00",
    }

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
        json=device_list,
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/appliancedetails",
        json=load_json_fixture("device_detail_light.json"),
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/directivesend",
        json=load_json_fixture("control_response_ok.json"),
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light_1")
    assert state is not None
    assert state.state == "off"
    assert ColorMode.COLOR_TEMP in state.attributes.get("supported_color_modes", [])
    # Verify min/max color temp
    assert state.attributes.get("min_color_temp_kelvin") == 2700
    assert state.attributes.get("max_color_temp_kelvin") == 6500


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_light_effect_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light with mode.valueRangeMap reports effect_list."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light_1")
    assert state is not None
    # Fixture light 001 has mode.valueRangeMap with 3 modes
    effect_list = state.attributes.get("effect_list", [])
    assert len(effect_list) == 3
    assert "明亮" in effect_list
    assert "舒适" in effect_list
    assert "起夜" in effect_list


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_light_set_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting a light effect sends lightSetMode command."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test_light_1", "effect": "明亮"},
        blocking=True,
    )
    await hass.async_block_till_done()

    control_calls = [
        c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
    ]
    assert len(control_calls) > 0
    call_data = control_calls[0][2]
    assert call_data is not None
    assert call_data["header"]["name"] == "SetModeRequest"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_light_command_body_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test turn_on sends correct TurnOnRequest command body."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test_light_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    control_calls = [
        c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
    ]
    assert len(control_calls) > 0
    call_data = control_calls[0][2]
    assert call_data is not None
    assert call_data["header"]["name"] == "TurnOnRequest"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_light_command_body_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test turn_off sends correct TurnOffRequest command body."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.test_light_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    control_calls = [
        c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
    ]
    assert len(control_calls) > 0
    call_data = control_calls[0][2]
    assert call_data is not None
    assert call_data["header"]["name"] == "TurnOffRequest"
