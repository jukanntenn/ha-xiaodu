"""Tests for the Xiaodu switch platform.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
HEATER, AIR_FRESHER, SOCKET, SWITCH types map to SWITCH_TYPES in const.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.components.switch import SwitchDeviceClass

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_switch_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch entities created from HEATER, AIR_FRESHER, SOCKET, SWITCH devices.

    HEATER has turnOnState.value="ON" (on).
    AIR_FRESHER has turnOnState.value="" (off).
    SOCKET has turnOnState.value="OFF" (off), device_class=OUTLET.
    SWITCH has turnOnState.value="ON" (on).
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # HEATER: turnOnState.value="ON" -> state "on"
    heater_state = hass.states.get("switch.test_heater_1")
    assert heater_state is not None
    assert heater_state.state == "on"

    # AIR_FRESHER: turnOnState.value="" -> state "off"
    fresher_state = hass.states.get("switch.test_air_fresher_1")
    assert fresher_state is not None
    assert fresher_state.state == "off"

    # SOCKET: turnOnState.value="OFF" -> state "off", device_class=OUTLET
    socket_state = hass.states.get("switch.test_socket_1")
    assert socket_state is not None
    assert socket_state.state == "off"
    assert socket_state.attributes.get("device_class") == SwitchDeviceClass.OUTLET

    # SWITCH: turnOnState.value="ON" -> state "on"
    switch_state = hass.states.get("switch.test_switch_1")
    assert switch_state is not None
    assert switch_state.state == "on"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a switch updates entity state via optimistic update."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # AIR_FRESHER starts off, turn it on
    assert hass.states.get("switch.test_air_fresher_1").state == "off"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.test_air_fresher_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_air_fresher_1")
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a switch updates entity state via optimistic update."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # HEATER starts on, turn it off
    assert hass.states.get("switch.test_heater_1").state == "on"

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.test_heater_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_heater_1")
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_switch_command_body(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test switch turn_on/turn_off sends correct HTTP command body."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    # Turn on the socket
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.test_socket_1"},
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
async def test_switch_turn_on_socket(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a SOCKET device (OUTLET class)."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_socket_1").state == "off"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.test_socket_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_socket_1")
    assert state is not None
    assert state.state == "on"
