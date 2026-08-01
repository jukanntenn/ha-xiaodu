"""E2E test fixtures.

Registers all endpoints with side_effects for dynamic responses
to simulate real-world polling scenarios.
"""

from __future__ import annotations

from typing import Any

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.xiaodu.api.xiaodu_client import HOST
from tests.conftest import load_json_fixture, register_bemfa_endpoints


class DeviceListSideEffect:
    """Return different device lists based on call count.

    - 1st call: device_list.json (initial)
    - 2nd call: device_list_added.json or device_list_state_changed.json
    - 3rd+ calls: same as 2nd
    """

    def __init__(self, second_fixture: str = "device_list_added.json") -> None:
        self._call_count = 0
        self._second_fixture = second_fixture

    async def __call__(
        self, method: str, url: str, data: dict[str, Any] | None
    ) -> AiohttpClientMockResponse:
        self._call_count += 1
        fixture = "device_list.json" if self._call_count <= 1 else self._second_fixture
        return AiohttpClientMockResponse(
            method=method,
            url=url,
            status=200,
            json=load_json_fixture(fixture),
        )


@pytest.fixture
def aioclient_mock_e2e(aioclient_mock: AiohttpClientMocker) -> None:
    """Register all endpoints for e2e testing with dynamic device list."""
    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_ok.json"),
    )
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/multihouse",
        json=load_json_fixture("home_list.json"),
    )
    # Device list with side_effect for dynamic responses
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/appliance",
        side_effect=DeviceListSideEffect(),
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/appliancedetails",
        json=load_json_fixture("device_detail_light.json"),
    )
    aioclient_mock.get(
        f"{HOST}/saiya/smarthome/directivesend",
        json=load_json_fixture("control_response_ok.json"),
    )
    # Register Bemfa endpoints for when Bemfa is enabled
    register_bemfa_endpoints(aioclient_mock)
