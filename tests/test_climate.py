"""Tests for the Xiaodu climate platform.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
AIR_CONDITION devices map to climate entities.
"""

from __future__ import annotations

import copy

import pytest
from homeassistant.components.climate import FAN_HIGH, FAN_MEDIUM, HVACMode
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.xiaodu.api.xiaodu_client import HOST
from tests.conftest import load_json_fixture


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_climate_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity is created from AIR_CONDITION device.

    AIR_CONDITION 1 has:
      - turnOnState.value="OFF" -> hvac_mode=OFF
      - temperature.value=16 -> current_temperature=16
      - No fanSpeed -> fan_mode defaults to FAN_MEDIUM
      - mode.value="COOL"
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.test_air_condition_1")
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes.get("current_temperature") == 16
    assert state.attributes.get("temperature") == 16
    assert state.attributes.get("fan_mode") == FAN_MEDIUM


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_climate_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a climate device sets hvac_mode from mode attribute.

    After optimistic update, turnOnState becomes "on" and the mode
    value "COOL" maps to HVACMode.COOL.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("climate.test_air_condition_1").state == HVACMode.OFF

    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": "climate.test_air_condition_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("climate.test_air_condition_1")
    assert state is not None
    assert state.state == HVACMode.COOL


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_climate_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a climate device sets hvac_mode to OFF."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn on first
    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": "climate.test_air_condition_1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.test_air_condition_1").state == HVACMode.COOL

    # Now turn off
    await hass.services.async_call(
        "climate",
        "turn_off",
        {"entity_id": "climate.test_air_condition_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("climate.test_air_condition_1")
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_climate_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature updates target via optimistic state.

    The climate entity issues N temperatureUp/Down calls then applies
    a single optimistic state. AIR_CONDITION 1 starts at 16 degrees.
    Setting to 18 should issue 2 temperatureUp calls.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initial temperature is 16
    state = hass.states.get("climate.test_air_condition_1")
    assert state.attributes.get("current_temperature") == 16

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.test_air_condition_1",
            ATTR_TEMPERATURE: 18,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # After optimistic state update, temperature should be 18
    state = hass.states.get("climate.test_air_condition_1")
    assert state is not None
    assert state.attributes.get("current_temperature") == 18
    assert state.attributes.get("temperature") == 18


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_climate_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting HVAC mode to HEAT sends turnOn + setMode commands."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test_air_condition_1", "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("climate.test_air_condition_1")
    assert state is not None
    assert state.state == HVACMode.HEAT

    # Verify commands were sent
    control_calls = [
        c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
    ]
    # Should have turnOn + setMode
    assert len(control_calls) >= 2
    command_names = [c[2]["header"]["name"] for c in control_calls]
    assert "TurnOnRequest" in command_names
    assert "SetModeRequest" in command_names


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_climate_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to OFF turns off the climate device."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn on first
    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": "climate.test_air_condition_1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.test_air_condition_1").state == HVACMode.COOL

    # Set to OFF
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test_air_condition_1", "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("climate.test_air_condition_1").state == HVACMode.OFF


async def test_climate_set_fan_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting fan mode sends setFanSpeed command.

    Uses a custom fixture with fanSpeed data to test fan mode reading.
    The base fixture has empty fanSpeed, so we modify it to include fan speed.
    """

    device_list = copy.deepcopy(load_json_fixture("device_list.json"))
    # Add fanSpeed data to the first AIR_CONDITION device
    for a in device_list["data"]["appliances"]:
        if a["applianceId"] == "appliance_test_air_condition_001":
            a["stateSetting"]["fanSpeed"] = {
                "name": "风速",
                "value": 2,
                "valueType": "NUM",
                "scale": "",
                "valueRangeMap": {"1": "低", "2": "中", "3": "高", "4": "自动"},
                "time": "2026-07-25 00:00:00",
            }
            break

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

    # Initial fan mode should be FAN_MEDIUM (value=2)
    state = hass.states.get("climate.test_air_condition_1")
    assert state is not None
    assert state.attributes.get("fan_mode") == FAN_MEDIUM

    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test_air_condition_1", "fan_mode": FAN_HIGH},
        blocking=True,
    )
    await hass.async_block_till_done()

    # After optimistic update, fan_mode should be FAN_HIGH
    state = hass.states.get("climate.test_air_condition_1")
    assert state is not None
    assert state.attributes.get("fan_mode") == FAN_HIGH

    # Verify command was sent
    control_calls = [
        c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
    ]
    assert len(control_calls) > 0
    call_data = control_calls[0][2]
    assert call_data is not None
    assert call_data["header"]["name"] == "IncrementFanSpeedRequest"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_climate_set_temperature_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting lower temperature issues temperatureDown calls.

    AIR_CONDITION 1 starts at 16 degrees. Setting to 18 first (2 temperatureUp),
    then setting to 16 (2 temperatureDown).
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # First raise temperature to 18
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.test_air_condition_1",
            ATTR_TEMPERATURE: 18,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    # Now lower temperature back to 16 -> 2 temperatureDown calls
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.test_air_condition_1",
            ATTR_TEMPERATURE: 16,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    control_calls = [
        c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
    ]
    # Should have 2 temperatureDown calls
    assert len(control_calls) >= 2
    for c in control_calls[:2]:
        assert c[2]["header"]["name"] == "DecrementTemperatureRequest"

    state = hass.states.get("climate.test_air_condition_1")
    assert state.attributes.get("current_temperature") == 16


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_climate_hvac_modes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity reports all supported HVAC modes."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.test_air_condition_1")
    assert state is not None
    hvac_modes = state.attributes.get("hvac_modes", [])
    assert HVACMode.OFF in hvac_modes
    assert HVACMode.COOL in hvac_modes
    assert HVACMode.HEAT in hvac_modes
    assert HVACMode.AUTO in hvac_modes
    assert HVACMode.DRY in hvac_modes
    assert HVACMode.FAN_ONLY in hvac_modes
