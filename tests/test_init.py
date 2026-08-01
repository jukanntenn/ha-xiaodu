"""Tests for the Xiaodu integration setup.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.xiaodu.bemfa.const import BEMFA_TOPIC_PREFIX
from custom_components.xiaodu.bemfa.sync_manager import DeviceMapping
from tests.conftest import MqttBrokerHandle

DELETE_TOPIC_URL = "https://pro.bemfa.com/v1/deleteTopic"

TOPIC_PREFIX = BEMFA_TOPIC_PREFIX


def _wait_for_sessions(
    broker: MqttBrokerHandle, expected: int, timeout_seconds: float
) -> bool:
    """在线程中轮询 broker 会话数（避免 asyncio 轮询 lint）。"""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if broker.sessions == expected:
            return True
        time.sleep(0.05)
    return False


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
    bemfa_mqtt_redirect: MqttBrokerHandle,
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
        bemfa_topic=f"{TOPIC_PREFIX}aaaa00000000002",
        device_type="LIGHT",
    )
    coordinator.bemfa_sync_manager._device_mapping["dev_b"] = DeviceMapping(
        xiaodu_appliance_id="dev_b",
        bemfa_topic=f"{TOPIC_PREFIX}bbbb00000000006",
        device_type="SWITCH",
    )

    # Register the delete_topic endpoint so unload's cleanup calls succeed.
    aioclient_mock.post(DELETE_TOPIC_URL, json={"code": 0, "msg": "success"})
    aioclient_mock.mock_calls.clear()

    assert await hass.config_entries.async_unload(mock_config_entry_with_bemfa.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_bemfa.state is ConfigEntryState.NOT_LOADED

    # Every mapped device should have triggered a delete_topic call. The two
    # seeded devices must be among them (setup may also have synced the
    # fixture devices, so the total count can be larger than two).
    # mock_calls tuple is (method, url, data, headers); url is a yarl.URL.
    delete_calls = [c for c in aioclient_mock.mock_calls if "deleteTopic" in str(c[1])]
    assert len(delete_calls) >= 2
    deleted_topics = {c[2]["topic"] for c in delete_calls if c[2] is not None}
    assert {f"{TOPIC_PREFIX}aaaa00000000002", f"{TOPIC_PREFIX}bbbb00000000006"} <= (
        deleted_topics
    )
    # The mapping should be empty after cleanup.
    assert coordinator.bemfa_sync_manager.device_mapping == {}
    # 真实断开：broker 上只剩探针会话（本测试未启用探针，因此为 0）。
    assert await asyncio.to_thread(_wait_for_sessions, bemfa_mqtt_redirect, 0, 3.0)


async def test_unload_with_bemfa_disconnects_when_topic_cleanup_fails(
    hass: HomeAssistant,
    mock_config_entry_with_bemfa: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    aioclient_mock_fixture: None,
    bemfa_mqtt_redirect: MqttBrokerHandle,
) -> None:
    """Test unload still disconnects MQTT when topic cleanup fails.

    Guards async_cleanup_all: a topic-deletion error must not skip the MQTT
    disconnect (which previously left the paho network thread running).
    """
    mock_config_entry_with_bemfa.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry_with_bemfa.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry_with_bemfa.runtime_data
    coordinator.bemfa_sync_manager._device_mapping["dev_err"] = DeviceMapping(
        xiaodu_appliance_id="dev_err",
        bemfa_topic="topic_err",
        device_type="LIGHT",
    )

    # Replace mocks so deleteTopic raises during unload cleanup.
    aioclient_mock.clear_requests()

    async def _topic_cleanup_failure(
        method: str, url: str, data: dict[str, Any] | None
    ) -> None:
        raise RuntimeError("topic cleanup failed")

    aioclient_mock.post(DELETE_TOPIC_URL, side_effect=_topic_cleanup_failure)

    assert await hass.config_entries.async_unload(mock_config_entry_with_bemfa.entry_id)
    await hass.async_block_till_done()

    # 清理失败也必须断开 MQTT：broker 会话归零。
    assert await asyncio.to_thread(_wait_for_sessions, bemfa_mqtt_redirect, 0, 3.0)
