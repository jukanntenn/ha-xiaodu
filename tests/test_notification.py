"""Tests for the Bemfa binding guidance notification.

验证 config flow 启用巴法云同步时创建 persistent_notification，跳过时不创建。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant import config_entries
from homeassistant.components import persistent_notification as pn
from homeassistant.components.persistent_notification import (
    _async_get_or_create_notifications,
)
from homeassistant.data_entry_flow import FlowResultType

from custom_components.xiaodu.const import (
    CONF_BEMFA_SECRET_ID,
    CONF_BEMFA_SECRET_KEY,
    CONF_BEMFA_UID,
    CONF_COOKIE,
    CONF_HOUSE_ID,
    DOMAIN,
)
from custom_components.xiaodu.notification import NOTIFICATION_ID
from tests.const import (
    TEST_APPLIANCE_ID,
    TEST_BEMFA_SECRET_ID,
    TEST_BEMFA_SECRET_KEY,
    TEST_BEMFA_UID,
    TEST_COOKIE,
    TEST_HOUSE_ID,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

DEVICE_ROOM = "次卧"


def _room_mapping_form_data() -> dict[str, str]:
    """Build room mapping form data for the selected device's room."""
    return {DEVICE_ROOM: DEVICE_ROOM}


async def _goto_bemfa_menu(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> str:
    """走完 cookie→home→device→room_mapping，进入 bemfa 菜单，返回 flow_id。"""
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
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "bemfa"
    return result["flow_id"]


async def test_notification_created_when_bemfa_v2_enabled(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    aioclient_mock_fixture: None,
) -> None:
    """启用 v2 巴法云同步后应创建「去米家绑定」引导通知。"""
    flow_id = await _goto_bemfa_menu(hass, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "bemfa_v2"}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_BEMFA_UID: TEST_BEMFA_UID,
            CONF_BEMFA_SECRET_ID: TEST_BEMFA_SECRET_ID,
            CONF_BEMFA_SECRET_KEY: TEST_BEMFA_SECRET_KEY,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    notifications = _async_get_or_create_notifications(hass)
    assert NOTIFICATION_ID in notifications
    notif = notifications[NOTIFICATION_ID]
    assert "米家" in notif["message"]
    assert notif["title"]


async def test_notification_created_when_bemfa_v1_enabled(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    aioclient_mock_fixture: None,
) -> None:
    """启用 v1 巴法云同步后也应创建引导通知。"""
    flow_id = await _goto_bemfa_menu(hass, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "bemfa_v1"}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_BEMFA_UID: TEST_BEMFA_UID}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    notifications = _async_get_or_create_notifications(hass)
    assert NOTIFICATION_ID in notifications


async def test_notification_not_created_when_bemfa_skipped(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    aioclient_mock_fixture: None,
) -> None:
    """跳过巴法云同步时不应创建引导通知。"""
    flow_id = await _goto_bemfa_menu(hass, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "bemfa_skip"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "bemfa" not in result["options"]

    notifications = _async_get_or_create_notifications(hass)
    assert NOTIFICATION_ID not in notifications


async def test_notification_dismiss_removes_it(hass: HomeAssistant) -> None:
    """dismiss 后通知即从内存消失（用户可手动关闭，不会持续打扰）。"""
    pn.async_create(hass, "test", title="t", notification_id=NOTIFICATION_ID)
    assert NOTIFICATION_ID in _async_get_or_create_notifications(hass)

    pn.async_dismiss(hass, NOTIFICATION_ID)
    assert NOTIFICATION_ID not in _async_get_or_create_notifications(hass)
