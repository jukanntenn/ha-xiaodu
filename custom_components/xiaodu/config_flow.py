"""小度（Xiaodu）集成的配置流程（Config Flow）。"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import area_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api.exceptions import XiaoduApiError, XiaoduAuthError, XiaoduNetworkError
from .api.xiaodu_client import XiaoduAPI
from .const import (
    AREA_LABEL,
    CONF_BEMFA_SECRET_ID,
    CONF_BEMFA_SECRET_KEY,
    CONF_BEMFA_UID,
    CONF_COOKIE,
    CONF_HOUSE_ID,
    CONF_HOUSE_NAME,
    CONF_ROOM_MAPPING,
    DOMAIN,
    ORIG_LABEL,
)
from .naming import strip_room
from .room_mapping import RoomMapper

if TYPE_CHECKING:
    from .api.xiaodu_types import Device

_LOGGER = logging.getLogger(__name__)

# 巴法云 UID：32 位十六进制（新版）或 45 位字母数字/下划线/连字符
_UID_RE = re.compile(r"^[0-9a-fA-F]{32}$|^[A-Za-z0-9_-]{45}$")


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
        config_entry: config_entries.ConfigEntry,  # noqa: ARG004 - HA 固定签名，参数未用
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
            if (
                self._api is None
            ):  # pragma: no cover - defensive; home step is only reachable after cookie auth
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
                label=self._device_label(d),
            )
            for d in self._devices
        ]
        default_ids = [d.appliance_id for d in self._devices]
        return vol.Schema(
            {
                vol.Optional("device_ids", default=default_ids): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    )
                ),
            }
        )

    @staticmethod
    def _device_label(d: Device) -> str:
        """生成设备在列表中的显示标签。

        room_name 非空时拼括号显示房间，否则只显示设备名；
        friendly_name 为空时兜底到 appliance_id。
        """
        name = d.friendly_name or d.appliance_id
        if d.room_name:
            return f"{name} ({d.room_name})"
        return name

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
        if not xiaodu_rooms:
            # 所选设备均未分配房间——无需映射，跳过本步
            self._room_mapping = {}
            return await self.async_step_bemfa()

        # 获取 HA 区域（areas）
        ar = area_registry.async_get(self.hass)
        ha_areas = [area.name for area in ar.async_list_areas()]

        mapper = RoomMapper()
        auto_mapping = mapper.auto_map(xiaodu_rooms, ha_areas)
        self._room_mapping = auto_mapping

        schema_fields: dict = {}
        for xiaodu_room, mapped_area in auto_mapping.items():
            area_options = [*ha_areas, xiaodu_room]
            schema_fields[vol.Optional(xiaodu_room, default=mapped_area)] = vol.In(
                sorted(set(area_options))
            )

        return self.async_show_form(
            step_id="room_mapping",
            data_schema=vol.Schema(schema_fields),
        )

    async def async_step_bemfa(
        self, _user_input: dict[str, object] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理 Bemfa（巴法云）配置——选择认证方式（可选步骤）。"""
        return self.async_show_menu(
            step_id="bemfa",
            menu_options=["bemfa_v2", "bemfa_v1", "bemfa_skip"],
        )

    async def async_step_bemfa_v2(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理 v2 认证（实名认证，推荐）。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            uid = user_input[CONF_BEMFA_UID].strip()
            secret_id = user_input[CONF_BEMFA_SECRET_ID].strip()
            secret_key = user_input[CONF_BEMFA_SECRET_KEY].strip()
            if not uid or not secret_id or not secret_key:
                errors["base"] = "bemfa_credentials_required"
            elif not _UID_RE.match(uid):
                errors["base"] = "invalid_bemfa_uid"
            else:
                return await self._async_finish(
                    {
                        "enabled": True,
                        "uid": uid,
                        "secret_id": secret_id,
                        "secret_key": secret_key,
                        "sync_devices": True,
                    }
                )

        return self.async_show_form(
            step_id="bemfa_v2",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BEMFA_UID): str,
                    vol.Required(CONF_BEMFA_SECRET_ID): str,
                    vol.Required(CONF_BEMFA_SECRET_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_bemfa_v1(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理 v1 旧版认证（仅私钥，无需实名）。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            uid = user_input[CONF_BEMFA_UID].strip()
            if not uid:
                errors["base"] = "bemfa_credentials_required"
            elif not _UID_RE.match(uid):
                errors["base"] = "invalid_bemfa_uid"
            else:
                return await self._async_finish(
                    {
                        "enabled": True,
                        "uid": uid,
                        "secret_id": "",
                        "secret_key": "",
                        "sync_devices": True,
                    }
                )

        return self.async_show_form(
            step_id="bemfa_v1",
            data_schema=vol.Schema({vol.Required(CONF_BEMFA_UID): str}),
            errors=errors,
        )

    async def async_step_bemfa_skip(
        self, _user_input: dict[str, object] | None = None
    ) -> config_entries.ConfigFlowResult:
        """跳过 Bemfa（巴法云）配置。"""
        return await self._async_finish(None)

    async def _async_finish(
        self, bemfa_config: dict[str, bool | str] | None
    ) -> config_entries.ConfigFlowResult:
        """创建配置条目（config entry）。"""
        # 校验唯一性
        _ = await self.async_set_unique_id(f"xiaodu_{self._house_id}")
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

        options: dict[str, object] = {
            CONF_ROOM_MAPPING: self._room_mapping,
        }
        if bemfa_config:
            options["bemfa"] = bemfa_config

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
            # 不传 description → HA 前端自动 fallback 到 strings.json 的
            # config.create_entry.default，再用 description_placeholders 做模板替换。
            description_placeholders={
                "device_overview": self._format_device_overview()
            },
        )

    def _format_device_overview(self) -> str:
        """生成「设备原始信息对照」的 Markdown 列表，供 create_entry 描述展示。

        HA 在 config_flow 完成后会弹出内置的「命名和分配」步骤，每行显示
        一个设备（设备名输入框 + HA 区域选择器）。但设备名在实体建立时
        已被 ``strip_room`` 剥离了房间前缀（如「主卧射灯」→「射灯」），
        用户在该步骤失去了设备的原始归属信息，无法核对自动分配的区域
        是否正确。

        本方法把每个设备的「剥离后名 + 原始名 + 所在房间 + HA 区域」
        格式化为 Markdown 列表，通过 ``description_placeholders`` 注入到
        ``create_entry`` 的描述里，渲染在「命名和分配」步骤的设备列表
        上方，让用户对照核对。

        仅当剥离后名与原始名不同时才标注「← 原始名」，避免冗余。
        """
        # 小度侧全部房间名——作为剥离锚点全集（与运行时一致）
        room_tokens = {d.room_name for d in self._devices if d.room_name}
        lines: list[str] = []
        for d in self._devices:
            name = d.friendly_name or d.appliance_id
            room = d.room_name
            mapped_room = self._room_mapping.get(room, room) if room else ""
            stripped = (
                strip_room(name, room, mapped_room, room_tokens) if room else name
            )
            room_part = f" @{room}" if room else ""
            area_part = f" → HA {AREA_LABEL}[{mapped_room}]" if mapped_room else ""
            if stripped != name:
                lines.append(
                    f"- **{stripped}** ← {ORIG_LABEL}「{name}」{room_part}{area_part}"
                )
            else:
                lines.append(f"- **{stripped}**{room_part}{area_part}")
        return "\n".join(lines)

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
        ar = area_registry.async_get(self.hass)
        ha_areas = [area.name for area in ar.async_list_areas()]

        schema_fields: dict = {}
        for xiaodu_room, mapped_area in current_mapping.items():
            schema_fields[vol.Optional(xiaodu_room, default=mapped_area)] = vol.In(
                sorted({*ha_areas, xiaodu_room})
            )

        return self.async_show_form(
            step_id="room_mapping",
            data_schema=vol.Schema(schema_fields),
        )

    async def async_step_bemfa(
        self, _user_input: dict[str, object] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理 Bemfa（巴法云）配置的修改——选择认证方式或禁用。"""
        current_bemfa = cast(
            "dict[str, str]", self.config_entry.options.get("bemfa", {})
        )
        menu_options = ["bemfa_v2", "bemfa_v1"]
        if current_bemfa.get("enabled"):
            menu_options.append("bemfa_disable")
        return self.async_show_menu(
            step_id="bemfa",
            menu_options=menu_options,
        )

    async def async_step_bemfa_v2(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理 v2 认证配置的修改。"""
        errors: dict[str, str] = {}
        current_bemfa = cast(
            "dict[str, str]", self.config_entry.options.get("bemfa", {})
        )
        if user_input is not None:
            uid = user_input[CONF_BEMFA_UID].strip()
            secret_id = user_input[CONF_BEMFA_SECRET_ID].strip()
            secret_key = user_input[CONF_BEMFA_SECRET_KEY].strip()
            if not uid or not secret_id or not secret_key:
                errors["base"] = "bemfa_credentials_required"
            elif not _UID_RE.match(uid):
                errors["base"] = "invalid_bemfa_uid"
            else:
                options = {
                    **self.config_entry.options,
                    "bemfa": {
                        "enabled": True,
                        "uid": uid,
                        "secret_id": secret_id,
                        "secret_key": secret_key,
                        "sync_devices": True,
                    },
                }
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="bemfa_v2",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BEMFA_UID, default=current_bemfa.get("uid", "")
                    ): str,
                    vol.Required(
                        CONF_BEMFA_SECRET_ID,
                        default=current_bemfa.get("secret_id", ""),
                    ): str,
                    vol.Required(
                        CONF_BEMFA_SECRET_KEY,
                        default=current_bemfa.get("secret_key", ""),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_bemfa_v1(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """处理 v1 认证配置的修改。"""
        errors: dict[str, str] = {}
        current_bemfa = cast(
            "dict[str, str]", self.config_entry.options.get("bemfa", {})
        )
        if user_input is not None:
            uid = user_input[CONF_BEMFA_UID].strip()
            if not uid:
                errors["base"] = "bemfa_credentials_required"
            elif not _UID_RE.match(uid):
                errors["base"] = "invalid_bemfa_uid"
            else:
                options = {
                    **self.config_entry.options,
                    "bemfa": {
                        "enabled": True,
                        "uid": uid,
                        "secret_id": "",
                        "secret_key": "",
                        "sync_devices": True,
                    },
                }
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="bemfa_v1",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BEMFA_UID, default=current_bemfa.get("uid", "")
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_bemfa_disable(
        self, _user_input: dict[str, object] | None = None
    ) -> config_entries.ConfigFlowResult:
        """禁用 Bemfa（巴法云）同步。"""
        options = {
            **self.config_entry.options,
            "bemfa": {
                "enabled": False,
                "uid": "",
                "secret_id": "",
                "secret_key": "",
                "sync_devices": False,
            },
        }
        return self.async_create_entry(title="", data=options)

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
