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

from custom_components.xiaodu.bemfa.sync_manager import DeviceMapping
from custom_components.xiaodu.const import (
    CONF_COOKIE,
)


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


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_diagnostics_includes_coordinator_health(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics exports coordinator health status."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert "coordinator" in diag
    assert "last_update_success" in diag["coordinator"]
    assert "last_exception" in diag["coordinator"]


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_diagnostics_redacts_bemfa_secrets(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry_with_bemfa: MockConfigEntry,
) -> None:
    """Test diagnostics redacts bemfa secret_id/secret_key in options."""
    mock_config_entry_with_bemfa.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry_with_bemfa.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry_with_bemfa
    )

    options = diag.get("options", {})
    bemfa_opts = options.get("bemfa", {})
    # secret fields must be redacted
    assert bemfa_opts.get("secret_id") == "**REDACTED**"
    assert bemfa_opts.get("secret_key") == "**REDACTED**"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_diagnostics_includes_sync_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry_with_bemfa: MockConfigEntry,
) -> None:
    """Test diagnostics exports DeviceMapping.sync_error."""
    mock_config_entry_with_bemfa.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry_with_bemfa.entry_id)
    await hass.async_block_till_done()

    # Inject a mapping with sync_error to verify it's exported
    coordinator = mock_config_entry_with_bemfa.runtime_data
    coordinator.bemfa_sync_manager._device_mapping["dev_err"] = DeviceMapping(
        xiaodu_appliance_id="dev_err",
        bemfa_topic="topic_err",
        device_type="LIGHT",
        sync_status="error",
        sync_error="参数错误",
    )

    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry_with_bemfa
    )

    bemfa_data = diag.get("bemfa", {})
    assert "dev_err" in bemfa_data
    assert bemfa_data["dev_err"]["sync_error"] == "参数错误"
    assert bemfa_data["dev_err"]["sync_status"] == "error"
