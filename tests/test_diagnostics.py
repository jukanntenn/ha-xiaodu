"""Tests for the Xiaodu diagnostics.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
"""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.xiaodu.const import CONF_COOKIE


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics output has expected structure."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert "config_entry_data" in diag
    assert "devices" in diag
    assert "device_count" in diag
    assert diag["device_count"] > 0


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_diagnostics_redacts_cookie(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics redacts sensitive cookie data."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    # Cookie should be redacted
    entry_data = diag["config_entry_data"]
    cookie_val = entry_data.get(CONF_COOKIE)
    assert CONF_COOKIE not in entry_data or cookie_val == "**REDACTED**"
