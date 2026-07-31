"""小度（Xiaodu）集成的配置流程（Config Flow）。"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api.exceptions import XiaoduApiError, XiaoduAuthError, XiaoduNetworkError
from .api.xiaodu_client import XiaoduAPI
from .api.xiaodu_types import Device
from .const import (
    CONF_BEMFA_UID,
    CONF_COOKIE,
    CONF_HOUSE_ID,
    CONF_HOUSE_NAME,
    CONF_ROOM_MAPPING,
    DOMAIN,
)
from .room_mapping import RoomMapper

_LOGGER = logging.getLogger(__name__)


class XiaoduConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """处理小度的配置流程（config flow）。"""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """初始化配置流程。"""
        self._cookie: str = ""
        self._api: XiaoduAPI | None = None
        self._homes: dict[str, str] = {}
        self._house_id: str = ""
        self._house_name: str = ""
        self._devices: list[Device] = []
        self._room_mapping: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> XiaoduOptionsFlow:
        """创建选项流程（options flow）。"""
        return XiaoduOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理初始步骤——显示菜单。"""
        return self.async_show_menu(
            step_id="user",
            menu_options=["cookie"],
        )

    async def async_step_cookie(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理 Cookie 的输入与校验。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            cookie = user_input[CONF_COOKIE].strip()
            if not cookie:
                errors["base"] = "invalid_cookie"
            else:
                session = async_get_clientsession(self.hass)
                self._api = XiaoduAPI(cookie, session)
                try:
                    await self._api.check_session()
                    self._cookie = cookie
                    homes = await self._api.get_home_list()
                    self._homes = {h.home_id: h.home_name for h in homes}
                    if not self._homes:
                        errors["base"] = "no_homes"
                    else:
                        return await self.async_step_home()
                except XiaoduAuthError:
                    errors["base"] = "auth_failed"
                except XiaoduNetworkError:
                    errors["base"] = "cannot_connect"
                except XiaoduApiError:
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="cookie",
            data_schema=vol.Schema({vol.Required(CONF_COOKIE): str}),
            errors=errors,
        )

    async def async_step_home(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理家庭（home）选择。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._house_id = user_input[CONF_HOUSE_ID]
            self._house_name = self._homes.get(self._house_id, "")
            if self._api is None:
                return self.async_abort(reason="cannot_connect")
            try:
                self._devices = await self._api.get_device_list(self._house_id)
            except XiaoduAuthError:
                errors["base"] = "auth_failed"
            except (XiaoduApiError, XiaoduNetworkError):
                errors["base"] = "cannot_connect"
            else:
                if not self._devices:
                    errors["base"] = "no_devices"
                else:
                    return await self.async_step_device()

        return self.async_show_form(
            step_id="home",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOUSE_ID): vol.In(self._homes),
                }
            ),
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理设备选择。"""
        if user_input is not None:
            selected_ids = user_input.get("device_ids", [])
            if not selected_ids:
                return self.async_show_form(
                    step_id="device",
                    data_schema=self._device_schema(),
                    errors={"base": "no_devices"},
                )
            # 按所选设备进行筛选
            self._devices = [d for d in self._devices if d.appliance_id in selected_ids]
            return await self.async_step_room_mapping()

        return self.async_show_form(
            step_id="device",
            data_schema=self._device_schema(),
        )

    def _device_schema(self) -> vol.Schema:
        """构建设备选择表单（schema）。"""
        options = [
            SelectOptionDict(
                value=d.appliance_id,
                label=f"{d.friendly_name} ({d.room_name})",
            )
            for d in self._devices
        ]
        return vol.Schema(
            {
                vol.Required("device_ids"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    )
                ),
            }
        )

    async def async_step_room_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理房间映射（room mapping）确认。"""
        if user_input is not None:
            # 表单以每个小度房间名作为字段名，因此
            # ``user_input`` 本身即为 ``{xiaodu_room: ha_area}`` 的映射。
            self._room_mapping = dict(user_input)
            return await self.async_step_bemfa()

        # 自动匹配房间
        xiaodu_rooms = list({d.room_name for d in self._devices if d.room_name})
        # 获取 HA 区域（areas）
        from homeassistant.helpers import area_registry

        ar = area_registry.async_get(self.hass)
        ha_areas = [area.name for area in ar.async_list_areas()]

        mapper = RoomMapper()
        auto_mapping = mapper.auto_map(xiaodu_rooms, ha_areas)
        self._room_mapping = auto_mapping

        schema_fields: dict = {}
        for xiaodu_room, mapped_area in auto_mapping.items():
            area_options = [*ha_areas, xiaodu_room]
            schema_fields[vol.Optional(xiaodu_room, default=mapped_area)] = vol.In(
                list(set(area_options))
            )

        return self.async_show_form(
            step_id="room_mapping",
            data_schema=vol.Schema(schema_fields),
        )

    async def async_step_bemfa(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理 Bemfa（巴法云）配置（可选）。"""
        if user_input is not None:
            bemfa_uid = user_input.get(CONF_BEMFA_UID, "").strip()
            bemfa_enabled = bool(bemfa_uid)

            # 校验唯一性
            await self.async_set_unique_id(f"xiaodu_{self._house_id}")
            self._abort_if_unique_id_configured()

            # 序列化设备数据，用于写入配置条目（config entry）
            serialized_devices = [
                {
                    "applianceId": d.appliance_id,
                    "houseId": self._house_id,
                    "cookie": self._cookie,
                }
                for d in self._devices
            ]
            appliance_types_list = [
                {"applianceTypes": d.appliance_types} for d in self._devices
            ]

            options: dict[str, Any] = {
                CONF_ROOM_MAPPING: self._room_mapping,
            }
            if bemfa_enabled:
                options["bemfa"] = {
                    "enabled": True,
                    "uid": bemfa_uid,
                    "sync_devices": True,
                }

            return self.async_create_entry(
                title=f"Xiaodu: {self._house_name}",
                data={
                    CONF_COOKIE: self._cookie,
                    CONF_HOUSE_ID: self._house_id,
                    CONF_HOUSE_NAME: self._house_name,
                    "devices": serialized_devices,
                    "appliance_types": appliance_types_list,
                },
                options=options,
            )

        return self.async_show_form(
            step_id="bemfa",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BEMFA_UID, default=""): str,
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """处理重新认证（re-authentication）触发。"""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理重新认证（re-authentication）确认。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            cookie = user_input[CONF_COOKIE].strip()
            if cookie:
                session = async_get_clientsession(self.hass)
                api = XiaoduAPI(cookie, session)
                try:
                    await api.check_session()
                    self.hass.config_entries.async_update_entry(
                        self._get_reauth_entry(),
                        data={**self._get_reauth_entry().data, CONF_COOKIE: cookie},
                    )
                    return self.async_update_reload_and_abort(self._get_reauth_entry())
                except XiaoduAuthError:
                    errors["base"] = "auth_failed"
                except (XiaoduNetworkError, XiaoduApiError):
                    errors["base"] = "cannot_connect"
            else:
                errors["base"] = "invalid_cookie"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_COOKIE): str}),
            errors=errors,
        )


class XiaoduOptionsFlow(config_entries.OptionsFlow):
    """处理小度的选项流程（options flow）。"""

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """返回配置条目（config entry）。"""
        return self.hass.config_entries.async_get_known_entry(self.handler)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理选项（options）的初始步骤。"""
        return self.async_show_menu(
            step_id="init",
            menu_options=["room_mapping", "bemfa", "reauth"],
        )

    async def async_step_room_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理房间映射（room mapping）的修改。"""
        if user_input is not None:
            # 表单以每个小度房间名作为字段名，因此
            # ``user_input`` 本身即为 ``{xiaodu_room: ha_area}`` 的映射。
            new_mapping = dict(user_input)
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    CONF_ROOM_MAPPING: new_mapping,
                },
            )

        current_mapping = self.config_entry.options.get(CONF_ROOM_MAPPING, {})
        from homeassistant.helpers import area_registry

        ar = area_registry.async_get(self.hass)
        ha_areas = [area.name for area in ar.async_list_areas()]

        schema_fields: dict = {}
        for xiaodu_room, mapped_area in current_mapping.items():
            schema_fields[vol.Optional(xiaodu_room, default=mapped_area)] = vol.In(
                [*ha_areas, xiaodu_room]
            )

        return self.async_show_form(
            step_id="room_mapping",
            data_schema=vol.Schema(schema_fields),
        )

    async def async_step_bemfa(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理 Bemfa（巴法云）配置的修改。"""
        if user_input is not None:
            bemfa_uid = user_input.get(CONF_BEMFA_UID, "").strip()
            options = {
                **self.config_entry.options,
                "bemfa": {
                    "enabled": bool(bemfa_uid),
                    "uid": bemfa_uid,
                    "sync_devices": True,
                },
            }
            return self.async_create_entry(title="", data=options)

        current_bemfa = self.config_entry.options.get("bemfa", {})
        current_uid = current_bemfa.get("uid", "")
        return self.async_show_form(
            step_id="bemfa",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BEMFA_UID, default=current_uid): str,
                }
            ),
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """从选项菜单处理重新认证（re-authentication）。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            cookie = user_input[CONF_COOKIE].strip()
            if cookie:
                session = async_get_clientsession(self.hass)
                api = XiaoduAPI(cookie, session)
                try:
                    await api.check_session()
                except XiaoduAuthError:
                    errors["base"] = "auth_failed"
                except (XiaoduNetworkError, XiaoduApiError):
                    errors["base"] = "cannot_connect"
                else:
                    # 在条目数据中更新 Cookie；OptionsFlow 中的
                    # async_create_entry 会保存 options 并触发重载。
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={**self.config_entry.data, CONF_COOKIE: cookie},
                    )
                    return self.async_create_entry(
                        title="",
                        data=dict(self.config_entry.options),
                    )
            else:
                errors["base"] = "invalid_cookie"

        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema({vol.Required(CONF_COOKIE): str}),
            errors=errors,
        )
