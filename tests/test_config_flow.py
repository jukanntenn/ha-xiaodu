"""Tests for the Xiaodu config flow.

Uses aioclient_mock to drive real XiaoduAPI execution (flo paradigm).
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.xiaodu.api.xiaodu_client import HOST
from custom_components.xiaodu.const import (
    CONF_BEMFA_UID,
    CONF_COOKIE,
    CONF_HOUSE_ID,
    CONF_ROOM_MAPPING,
    DOMAIN,
)
from tests.conftest import load_json_fixture
from tests.const import (
    TEST_APPLIANCE_ID,
    TEST_BEMFA_UID,
    TEST_COOKIE,
    TEST_HOUSE_ID,
    TEST_HOUSE_NAME,
)

# The room for TEST_APPLIANCE_ID ("appliance_test_light_001") in the fixture
DEVICE_ROOM = "次卧"


def _room_mapping_form_data() -> dict[str, str]:
    """Build room mapping form data for the selected device's room."""
    return {DEVICE_ROOM: DEVICE_ROOM}


# ---------------------------------------------------------------------------
# ConfigFlow: user step
# ---------------------------------------------------------------------------


async def test_user_step_shows_menu(hass: HomeAssistant) -> None:
    """Test the user step shows a menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["cookie"]


# ---------------------------------------------------------------------------
# ConfigFlow: cookie step error paths
# ---------------------------------------------------------------------------


async def test_cookie_auth_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test cookie validation failure (auth error)."""
    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_not_login.json"),
        status=HTTPStatus.OK,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cookie"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: "bad_cookie"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cookie"
    assert result["errors"]["base"] == "auth_failed"


async def test_cookie_empty_rejected(hass: HomeAssistant) -> None:
    """Test empty cookie is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cookie"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: ""}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cookie"
    assert result["errors"]["base"] == "invalid_cookie"


async def test_cookie_no_homes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test no homes found error."""
    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_ok.json"),
    )
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/multihouse",
        json={"status": 0, "data": {"houseList": []}},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cookie"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: TEST_COOKIE}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cookie"
    assert result["errors"]["base"] == "no_homes"


# ---------------------------------------------------------------------------
# ConfigFlow: home/device step error paths
# ---------------------------------------------------------------------------


async def test_no_devices_in_home_step(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test no devices found error in home step."""
    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_ok.json"),
    )
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/multihouse",
        json=load_json_fixture("home_list.json"),
    )
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/appliance",
        json={"status": 0, "data": {"appliances": []}},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cookie"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: TEST_COOKIE}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOUSE_ID: TEST_HOUSE_ID}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "home"
    assert result["errors"]["base"] == "no_devices"


async def test_home_step_api_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test device-list API error in home step maps to cannot_connect.

    A 500 response from the appliance endpoint must surface as a
    recoverable form error rather than crashing the flow.
    """
    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_ok.json"),
    )
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/multihouse",
        json=load_json_fixture("home_list.json"),
    )
    aioclient_mock.post(
        f"{HOST}/saiya/smarthome/appliance",
        json=load_json_fixture("error_500.json"),
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cookie"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: TEST_COOKIE}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOUSE_ID: TEST_HOUSE_ID}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "home"
    assert result["errors"]["base"] == "cannot_connect"


# ---------------------------------------------------------------------------
# ConfigFlow: full happy path
# ---------------------------------------------------------------------------


async def test_full_flow_without_bemfa(
    hass: HomeAssistant,
    aioclient_mock_fixture: None,
) -> None:
    """Test the full config flow without Bemfa configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cookie"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cookie"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: TEST_COOKIE}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "home"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOUSE_ID: TEST_HOUSE_ID}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_ids": [TEST_APPLIANCE_ID]}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "room_mapping"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _room_mapping_form_data()
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bemfa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BEMFA_UID: ""}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Xiaodu: {TEST_HOUSE_NAME}"
    assert result["data"][CONF_COOKIE] == TEST_COOKIE
    assert result["data"][CONF_HOUSE_ID] == TEST_HOUSE_ID
    assert "bemfa" not in result["options"]


async def test_full_flow_with_bemfa(
    hass: HomeAssistant,
    aioclient_mock_fixture: None,
) -> None:
    """Test the full config flow with Bemfa configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cookie"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: TEST_COOKIE}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOUSE_ID: TEST_HOUSE_ID}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_ids": [TEST_APPLIANCE_ID]}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _room_mapping_form_data()
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BEMFA_UID: TEST_BEMFA_UID}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"]["bemfa"]["enabled"] is True
    assert result["options"]["bemfa"]["uid"] == TEST_BEMFA_UID


async def test_unique_id_already_configured(
    hass: HomeAssistant,
    aioclient_mock_fixture: None,
) -> None:
    """Test flow aborts when unique id is already configured."""
    # Create a first entry
    first_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    first_result = await hass.config_entries.flow.async_configure(
        first_result["flow_id"], {"next_step_id": "cookie"}
    )
    first_result = await hass.config_entries.flow.async_configure(
        first_result["flow_id"], {CONF_COOKIE: TEST_COOKIE}
    )
    first_result = await hass.config_entries.flow.async_configure(
        first_result["flow_id"], {CONF_HOUSE_ID: TEST_HOUSE_ID}
    )
    first_result = await hass.config_entries.flow.async_configure(
        first_result["flow_id"], {"device_ids": [TEST_APPLIANCE_ID]}
    )
    first_result = await hass.config_entries.flow.async_configure(
        first_result["flow_id"], _room_mapping_form_data()
    )
    first_result = await hass.config_entries.flow.async_configure(
        first_result["flow_id"], {CONF_BEMFA_UID: ""}
    )
    assert first_result["type"] == FlowResultType.CREATE_ENTRY

    # Start a second flow with the same home
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cookie"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: TEST_COOKIE}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOUSE_ID: TEST_HOUSE_ID}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_ids": [TEST_APPLIANCE_ID]}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _room_mapping_form_data()
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BEMFA_UID: ""}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# ConfigFlow: reauth
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow triggered by SOURCE_REAUTH succeeds."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
            "unique_id": mock_config_entry.unique_id,
        },
        data=mock_config_entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: "new_valid_cookie"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_invalid_cookie(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test reauth flow rejects empty cookie."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: ""}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "invalid_cookie"


async def test_reauth_flow_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth flow with auth failure."""
    # Register a failing session check for reauth
    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_not_login.json"),
    )

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COOKIE: "expired_cookie"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "auth_failed"


# ---------------------------------------------------------------------------
# OptionsFlow: init menu
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_options_flow_init_menu(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow init shows a menu."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    assert set(result["menu_options"]) == {"room_mapping", "bemfa", "reauth"}


# ---------------------------------------------------------------------------
# OptionsFlow: room_mapping
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_options_flow_room_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow room mapping."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "room_mapping"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "room_mapping"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _room_mapping_form_data()
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ROOM_MAPPING] == _room_mapping_form_data()


# ---------------------------------------------------------------------------
# OptionsFlow: bemfa
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_options_flow_bemfa_enable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow bemfa configuration (enable)."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "bemfa"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bemfa"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_BEMFA_UID: TEST_BEMFA_UID}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["bemfa"]["enabled"] is True
    assert result["data"]["bemfa"]["uid"] == TEST_BEMFA_UID
    assert result["data"][CONF_ROOM_MAPPING] == _room_mapping_form_data()


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_options_flow_bemfa_disable(
    hass: HomeAssistant,
    mock_config_entry_with_bemfa: MockConfigEntry,
) -> None:
    """Test options flow bemfa configuration (disable by clearing UID)."""
    mock_config_entry_with_bemfa.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_config_entry_with_bemfa.entry_id
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "bemfa"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_BEMFA_UID: ""}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["bemfa"]["enabled"] is False
    assert result["data"]["bemfa"]["uid"] == ""


# ---------------------------------------------------------------------------
# OptionsFlow: reauth
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_options_flow_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow reauth success path."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "reauth"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COOKIE: "new_cookie_value"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_flow_reauth_invalid_cookie(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock_fixture: None,
) -> None:
    """Test options flow reauth with empty cookie."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "reauth"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COOKIE: ""}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth"
    assert result["errors"]["base"] == "invalid_cookie"


async def test_options_flow_reauth_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test options flow reauth with auth failure."""
    aioclient_mock.post(
        f"{HOST}/appserver/gateway/app/v1",
        json=load_json_fixture("check_session_not_login.json"),
    )

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "reauth"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COOKIE: "expired"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "auth_failed"
