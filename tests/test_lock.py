"""Tests for the Xiaodu lock platform.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
DOOR_LOCK devices map to lock entities.

Note: The lock entity checks lockState first, then falls back to turnOnState.
The optimistic update from async_unlock/async_lock only updates turnOnState,
which doesn't affect is_locked when lockState is present. So the lock entity
state remains "locked" after optimistic update (lockState.value="locked" persists).
The actual state change would come from the next poll after the real device responds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_lock_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lock entity is created from DOOR_LOCK device.

    DOOR_LOCK has lockState.value="locked" -> is_locked=True.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_door_lock_1")
    assert state is not None
    assert state.state == "locked"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_lock_unlock_sends_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test unlocking a lock sends turnOn command."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": "lock.test_door_lock_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify the turnOn command was sent
    control_calls = [
        c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
    ]
    assert len(control_calls) > 0
    call_data = control_calls[0][2]
    assert call_data is not None
    assert call_data["header"]["name"] == "TurnOnRequest"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_lock_lock_sends_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test locking a lock sends turnOff command."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        "lock",
        "lock",
        {"entity_id": "lock.test_door_lock_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify the turnOff command was sent
    control_calls = [
        c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
    ]
    assert len(control_calls) > 0
    call_data = control_calls[0][2]
    assert call_data is not None
    assert call_data["header"]["name"] == "TurnOffRequest"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_lock_state_reflects_lockstate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lock entity state reflects lockState from fixture.

    The fixture has lockState.value="locked", so the entity should be "locked".
    The entity checks lockState first, then falls back to turnOnState.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_door_lock_1")
    assert state is not None
    assert state.state == "locked"

    # Verify the device has lockState in state_setting
    coordinator = mock_config_entry.runtime_data
    device = coordinator.data["appliance_test_door_lock_001"]
    assert "lockState" in device.state_setting
    assert device.state_setting["lockState"]["value"] == "locked"
