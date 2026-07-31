"""Tests for the Xiaodu cover platform.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
CURTAIN devices map to cover entities.
"""

from __future__ import annotations

import pytest
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_cover_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cover entity is created from CURTAIN device.

    CURTAIN device has turnOnState.value="OFF" -> is_closed=True.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_curtain_1")
    assert state is not None
    assert state.state == "closed"
    assert state.attributes.get("device_class") == CoverDeviceClass.CURTAIN


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_cover_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test opening a cover sends turnOn command and updates state."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_curtain_1").state == "closed"

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.test_curtain_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_curtain_1")
    assert state is not None
    assert state.state == "open"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_cover_close(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test closing a cover sends turnOff command and updates state."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Open first
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.test_curtain_1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("cover.test_curtain_1").state == "open"

    # Now close
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.test_curtain_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_curtain_1")
    assert state is not None
    assert state.state == "closed"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_cover_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test stopping a cover sends stop (PauseRequest) command."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.test_curtain_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify the stop command was sent
    control_calls = [
        c for c in aioclient_mock.mock_calls if "directivesend" in str(c[1])
    ]
    assert len(control_calls) > 0
    call_data = control_calls[0][2]
    assert call_data is not None
    assert call_data["header"]["name"] == "PauseRequest"
