"""Fixtures for testing the Xiaodu integration.

Follows the flo paradigm: aioclient_mock drives real XiaoduAPI/BemfaAPIClient
execution. No patching of API classes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.xiaodu.api.xiaodu_client import HOST
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


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


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
