"""Tests for the Xiaodu button platform.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
CLOTHES_RACK devices map to button entities.
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
async def test_button_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button entity is created from CLOTHES_RACK device."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("button.test_clothes_rack_1")
    assert state is not None


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test pressing a button sends turnOn command."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.test_clothes_rack_1"},
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
