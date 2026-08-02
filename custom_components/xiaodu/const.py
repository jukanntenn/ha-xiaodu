"""小度（Xiaodu）集成的常量定义。"""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

from .api.xiaodu_types import ApplianceType

DOMAIN = "xiaodu"

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LOCK,
    Platform.BUTTON,
]

SCAN_INTERVAL = timedelta(seconds=30)

# 配置项键名（Configuration keys）
CONF_COOKIE = "cookie"
CONF_HOUSE_ID = "house_id"
CONF_HOUSE_NAME = "house_name"
CONF_ROOM_MAPPING = "room_mapping"
CONF_BEMFA_UID = "bemfa_uid"
CONF_BEMFA_SECRET_ID = "bemfa_secret_id"  # noqa: S105 - config key name
CONF_BEMFA_SECRET_KEY = "bemfa_secret_key"  # noqa: S105 - config key name
CONF_BEMFA_ENABLED = "bemfa_enabled"

# 设备类型编码映射：xiaodu_type -> bemfa_topic_suffix（巴法云主题后缀）
DEVICE_TYPE_SUFFIX_MAP: dict[str, str] = {
    ApplianceType.LIGHT: "002",
    ApplianceType.SOCKET: "001",
    ApplianceType.SWITCH: "006",
    ApplianceType.CLIMATE: "005",
    ApplianceType.COVER: "009",
}

# 用于平台发现（platform discovery）的设备类型分组
LIGHT_TYPES = {ApplianceType.LIGHT}
SWITCH_TYPES = {
    ApplianceType.SOCKET,
    ApplianceType.SWITCH,
    "HEATER",
    "AIR_FRESHER",
    "WINDOW_OPENER",
}
SOCKET_TYPES = {ApplianceType.SOCKET}
CLIMATE_TYPES = {ApplianceType.CLIMATE}
COVER_TYPES = {ApplianceType.COVER}
LOCK_TYPES = {"DOOR_LOCK"}
BUTTON_TYPES = {"CLOTHES_RACK"}

# create_entry 设备原始信息对照表中的字段标签。
# 设备名/房间名本身为中文（小度生态），故标签也固定中文以保持一致；
# 引导文案由 strings.json 的 create_entry 翻译键本地化。
ORIG_LABEL = "原始"
AREA_LABEL = "区域"
