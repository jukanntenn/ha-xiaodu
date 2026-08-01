"""巴法云（Bemfa）MQTT 报文编解码（官方 # 文本协议）。

依据 .local/bemfa 官方文档：speaker_mi.md 定义各设备类型消息格式，
mqtt..md 定义 /up（上行状态）与 /set（下行控制）频道语义。
"""

from __future__ import annotations

import logging
from typing import Any

from ..api.xiaodu_types import ApplianceType, Command
from ..const import DEVICE_TYPE_SUFFIX_MAP

_LOGGER = logging.getLogger(__name__)

BEMFA_MODE_CODES: dict[str, int] = {
    "auto": 1,
    "cool": 2,
    "heat": 3,
    "fan": 4,
    "dehumidification": 5,
}
XIAODU_MODE_BY_CODE: dict[int, str] = {
    code: mode for mode, code in BEMFA_MODE_CODES.items()
}
SUPPORTED_TYPES: frozenset[str] = frozenset(DEVICE_TYPE_SUFFIX_MAP)


def encode_state(device_type: str, state_setting: dict[str, Any]) -> str | None:
    """把小度 state_setting 编码为巴法云 # 文本；不支持/无状态返回 None。"""
    if device_type not in SUPPORTED_TYPES:
        return None
    turn_on = state_setting.get("turnOnState", {})
    on = str(turn_on.get("value", "")).lower() == "on"
    if not on:
        return "off"
    if device_type == ApplianceType.LIGHT:
        brightness = state_setting.get("brightness", {}).get("value")
        if brightness is not None:
            return f"on#{int(brightness)}"
        return "on"
    if device_type == ApplianceType.CLIMATE:
        parts = ["on"]
        mode = str(state_setting.get("mode", {}).get("value", "")).lower()
        if code := BEMFA_MODE_CODES.get(mode):
            parts.append(str(code))
        temperature = state_setting.get("temperature", {}).get("value")
        if temperature is not None:
            parts.append(str(int(temperature)))
        fan_speed = state_setting.get("fanSpeed", {}).get("value")
        if fan_speed is not None:
            parts.append(str(int(fan_speed)))
        return "#".join(parts)
    return "on"


def parse_command(device_type: str, message: str) -> list[Command]:
    """把巴法云下行 # 文本解析为 Xiaodu Command 列表。"""
    if device_type not in SUPPORTED_TYPES:
        return []
    parts = message.split("#")
    head = parts[0]
    if device_type in (ApplianceType.SOCKET, ApplianceType.SWITCH):
        if head == "on":
            return [Command(action="turnOn")]
        if head == "off":
            return [Command(action="turnOff")]
        _LOGGER.warning("Unsupported %s command: %s", device_type, message)
        return []
    if device_type == ApplianceType.LIGHT:
        if head == "off":
            return [Command(action="turnOff")]
        if head != "on":
            _LOGGER.warning("Unsupported %s command: %s", device_type, message)
            return []
        commands = [Command(action="turnOn")]
        if len(parts) >= 2:
            brightness = _bemfa_int(parts[1], 1, 100)
            if brightness is None:
                return []
            commands.append(
                Command(action="setBrightness", params={"attributeValue": brightness})
            )
        if len(parts) >= 3:
            _LOGGER.warning("Light RGB/color-temp control not supported: %s", message)
        return commands
    if device_type == ApplianceType.COVER:
        if head == "on":
            commands = [Command(action="turnOn")]
            if len(parts) >= 2:
                if _bemfa_int(parts[1], 0, 100) is None:
                    return []
                _LOGGER.warning(
                    "Cover position not supported, treating as open: %s", message
                )
            return commands
        if head == "off":
            return [Command(action="turnOff")]
        if head == "pause":
            return [Command(action="stop")]
        _LOGGER.warning("Unsupported %s command: %s", device_type, message)
        return []
    if device_type == ApplianceType.CLIMATE:
        if head == "off":
            return [Command(action="turnOff")]
        if head != "on":
            _LOGGER.warning("Unsupported %s command: %s", device_type, message)
            return []
        commands = [Command(action="turnOn")]
        if len(parts) >= 2:
            mode_code = _bemfa_int(parts[1], 1, 7)
            if mode_code is None:
                return []
            if mode_code in XIAODU_MODE_BY_CODE:
                commands.append(
                    Command(
                        action="setMode",
                        params={"mode": XIAODU_MODE_BY_CODE[mode_code]},
                    )
                )
            else:
                _LOGGER.warning("AC mode %s not supported (sleep/eco)", mode_code)
        if len(parts) >= 3:
            temperature = _bemfa_int(parts[2], 16, 32)
            if temperature is None:
                _LOGGER.warning("AC temperature out of range, ignored: %s", message)
            else:
                commands.append(
                    Command(action="setTemperature", params={"target": temperature})
                )
        if len(parts) >= 4:
            speed = _bemfa_int(parts[3], 0, 5)
            if speed is None:
                _LOGGER.warning("AC fan speed invalid, ignored: %s", message)
            elif speed == 0:
                commands.append(Command(action="setFanSpeed", params={"speed": 4}))
            elif speed <= 4:
                commands.append(Command(action="setFanSpeed", params={"speed": speed}))
            else:
                _LOGGER.warning("AC fan speed %s not supported", speed)
        if len(parts) >= 5:
            _LOGGER.warning("AC swing control not supported: %s", message)
        return commands
    return []


def _bemfa_int(raw: str, minimum: int, maximum: int) -> int | None:
    """解析范围内的整数，非法/越界返回 None。"""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if minimum <= value <= maximum else None
