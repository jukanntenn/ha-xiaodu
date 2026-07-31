"""Tests for the Xiaodu integration setup.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
"""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.xiaodu.bemfa.sync_manager import DeviceMapping

DELETE_TOPIC_URL = "https://pro.bemfa.com/v1/deleteTopic"


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test setting up the integration loads successfully."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_with_bemfa(
    hass: HomeAssistant,
    mock_config_entry_with_bemfa: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test setting up the integration with Bemfa enabled."""
    mock_config_entry_with_bemfa.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry_with_bemfa.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_bemfa.state is ConfigEntryState.LOADED

    # Verify secret credentials are passed to the Bemfa API client (step 3.6.6)
    coordinator = mock_config_entry_with_bemfa.runtime_data
    api_client = coordinator.bemfa_sync_manager._api_client
    assert api_client._secret_id == "test_secret_id_abcdefghijklmnop"  # noqa: S105
    assert api_client._secret_key == "test_secret_key_qrstuvwxyz123456"  # noqa: S105


async def test_unload_with_bemfa_cleans_up_topics(
    hass: HomeAssistant,
    mock_config_entry_with_bemfa: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    aioclient_mock_fixture: None,
) -> None:
    """Test unloading with Bemfa enabled deletes all mapped topics.

    Verifies F3: orphaned Bemfa topics must not be left behind on unload.
    The delete_topic HTTP endpoint should be hit once per mapped device.
    """
    mock_config_entry_with_bemfa.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry_with_bemfa.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry_with_bemfa.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry_with_bemfa.runtime_data
    # Seed the sync manager with two mapped devices so we can assert each
    # triggers a delete_topic call on unload.
    coordinator.bemfa_sync_manager._device_mapping["dev_a"] = DeviceMapping(
        xiaodu_appliance_id="dev_a",
        bemfa_topic="topic_a",
        device_type="LIGHT",
    )
    coordinator.bemfa_sync_manager._device_mapping["dev_b"] = DeviceMapping(
        xiaodu_appliance_id="dev_b",
        bemfa_topic="topic_b",
        device_type="SWITCH",
    )

    # Register the delete_topic endpoint so unload's cleanup calls succeed.
    aioclient_mock.post(DELETE_TOPIC_URL, json={"code": 0, "msg": "success"})
    aioclient_mock.mock_calls.clear()

    # MQTT disconnect runs off the event loop; stub it so the test does not
    # touch a real broker.
    with patch.object(coordinator.bemfa_sync_manager._mqtt_client, "disconnect"):
        assert await hass.config_entries.async_unload(
            mock_config_entry_with_bemfa.entry_id
        )
        await hass.async_block_till_done()

    assert mock_config_entry_with_bemfa.state is ConfigEntryState.NOT_LOADED

    # Each mapped device should have triggered exactly one delete_topic call.
    # mock_calls tuple is (method, url, data, headers); url is a yarl.URL.
    delete_calls = [c for c in aioclient_mock.mock_calls if "deleteTopic" in str(c[1])]
    assert len(delete_calls) == 2
    # The mapping should be empty after cleanup.
    assert coordinator.bemfa_sync_manager.device_mapping == {}
