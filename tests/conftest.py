"""Fixtures for testing the Xiaodu integration.

Follows the flo paradigm: aioclient_mock drives real XiaoduAPI/BemfaAPIClient
execution. No patching of API classes.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.xiaodu.api.xiaodu_client import HOST
from custom_components.xiaodu.bemfa.const import (
    BEMFA_CHANGE_GROUP_URL,
    BEMFA_CHANGE_ROOM_URL,
    BEMFA_CREATE_TOPIC_URL,
    BEMFA_DEVICE_CONTROL_URL,
    BEMFA_DEVICE_LIST_URL,
)
from custom_components.xiaodu.bemfa.mqtt_client import BemfaMQTTClient
from custom_components.xiaodu.const import (
    CONF_COOKIE,
    CONF_HOUSE_ID,
    CONF_HOUSE_NAME,
    CONF_ROOM_MAPPING,
    DOMAIN,
)
from tests.const import (
    TEST_BEMFA_SECRET_ID,
    TEST_BEMFA_SECRET_KEY,
    TEST_BEMFA_UID,
    TEST_COOKIE,
    TEST_HOUSE_ID,
    TEST_HOUSE_NAME,
    TEST_ROOM_NAME,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_json_fixture(filename: str, subdir: str = "xiaodu") -> dict[str, Any]:
    """Load a JSON fixture file."""
    return json.loads((FIXTURES_DIR / subdir / filename).read_text(encoding="utf-8"))


def register_bemfa_endpoints(aioclient_mock: AiohttpClientMocker) -> None:
    """Register all Bemfa HTTP API endpoints with fixture data."""
    aioclient_mock.post(
        BEMFA_CREATE_TOPIC_URL,
        json=load_json_fixture("create_topic_ok.json", "bemfa"),
    )
    aioclient_mock.post(
        "https://pro.bemfa.com/v1/deleteTopic",
        json=load_json_fixture("delete_topic_ok.json", "bemfa"),
    )
    aioclient_mock.post(
        BEMFA_CHANGE_ROOM_URL,
        json=load_json_fixture("change_topic_room_ok.json", "bemfa"),
    )
    aioclient_mock.post(
        BEMFA_CHANGE_GROUP_URL,
        json=load_json_fixture("change_topic_group_ok.json", "bemfa"),
    )
    aioclient_mock.post(
        BEMFA_DEVICE_CONTROL_URL,
        json=load_json_fixture("control_device_ok.json", "bemfa"),
    )
    aioclient_mock.get(
        BEMFA_DEVICE_LIST_URL,
        json=load_json_fixture("device_list_ok.json", "bemfa"),
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture(autouse=True)
def mock_bemfa_mqtt_connect() -> Generator[None]:
    """Keep Bemfa MQTT hermetic: never start a real paho network thread.

    MQTT is an external service, so the Bemfa MQTT client is patched (as
    AGENTS.md permits), while Bemfa HTTP endpoints go through aioclient_mock.
    Pretend the broker session is established so publish paths stay testable.
    """

    def _fake_connect(self: BemfaMQTTClient) -> None:
        self._connected = True

    with patch.object(BemfaMQTTClient, "connect", _fake_connect):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry without Bemfa."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Xiaodu: {TEST_HOUSE_NAME}",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={
            CONF_ROOM_MAPPING: {TEST_ROOM_NAME: TEST_ROOM_NAME},
        },
    )


@pytest.fixture
def mock_config_entry_with_bemfa() -> MockConfigEntry:
    """Mock config entry with Bemfa enabled."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Xiaodu: {TEST_HOUSE_NAME}",
        data={
            CONF_COOKIE: TEST_COOKIE,
            CONF_HOUSE_ID: TEST_HOUSE_ID,
            CONF_HOUSE_NAME: TEST_HOUSE_NAME,
        },
        options={
            CONF_ROOM_MAPPING: {TEST_ROOM_NAME: TEST_ROOM_NAME},
            "bemfa": {
                "enabled": True,
                "uid": TEST_BEMFA_UID,
                "secret_id": TEST_BEMFA_SECRET_ID,
                "secret_key": TEST_BEMFA_SECRET_KEY,
                "sync_devices": True,
            },
        },
    )


async def _control_side_effect(
    method: str, url: str, data: dict[str, Any] | None
) -> AiohttpClientMockResponse:
    """Dynamic handler for directivesend: returns OK for any command."""
    return AiohttpClientMockResponse(
        method=method,
        url=url,
        status=200,
        json=load_json_fixture("control_response_ok.json"),
    )


@pytest.fixture
def aioclient_mock_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Register all Xiaodu API endpoints with fixture data.

    Follows the flo conftest pattern: registers all endpoints that the
    integration needs for setup + first refresh.
    """
    # check_session
    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_ok.json"),
    )
    # get_home_list
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/multihouse",
        json=load_json_fixture("home_list.json"),
    )
    # get_device_list (initial)
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/appliance",
        json=load_json_fixture("device_list.json"),
    )
    # get_device_detail (light)
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/appliancedetails",
        json=load_json_fixture("device_detail_light.json"),
    )
    # control_device (directivesend) - uses side_effect for dynamic response
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/directivesend",
        side_effect=_control_side_effect,
    )
    # Bemfa HTTP endpoints (unused mocks are harmless for tests without Bemfa;
    # tests that enable Bemfa need these during setup, sync, and unload).
    register_bemfa_endpoints(aioclient_mock)
