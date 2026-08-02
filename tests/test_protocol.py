"""巴法云官方 # 文本协议编解码用例。"""

from __future__ import annotations

from custom_components.xiaodu.api.xiaodu_types import Command
from custom_components.xiaodu.bemfa.protocol import encode_state, parse_command


def test_encode_switch_off() -> None:
    assert encode_state("SWITCH", {"turnOnState": {"value": "OFF"}}) == "off"
    assert encode_state("SWITCH", {"turnOnState": {"value": "ON"}}) == "on"


def test_encode_socket_off() -> None:
    assert encode_state("SOCKET", {"turnOnState": {"value": "OFF"}}) == "off"


def test_encode_light_brightness() -> None:
    state = {
        "turnOnState": {"value": "ON"},
        "brightness": {"value": 80},
    }
    assert encode_state("LIGHT", state) == "on#80"


def test_encode_light_no_brightness() -> None:
    assert encode_state("LIGHT", {"turnOnState": {"value": "ON"}}) == "on"


def test_encode_climate_full() -> None:
    state = {
        "turnOnState": {"value": "ON"},
        "mode": {"value": "cool"},
        "temperature": {"value": 23},
        "fanSpeed": {"value": 3},
    }
    assert encode_state("AIR_CONDITION", state) == "on#2#23#3"


def test_encode_climate_partial() -> None:
    state = {"turnOnState": {"value": "ON"}, "mode": {"value": "heat"}}
    assert encode_state("AIR_CONDITION", state) == "on#3"


def test_encode_cover() -> None:
    assert encode_state("CURTAIN", {"turnOnState": {"value": "ON"}}) == "on"
    assert encode_state("CURTAIN", {"turnOnState": {"value": "OFF"}}) == "off"


def test_encode_unsupported_type_returns_none() -> None:
    assert encode_state("DOOR_LOCK", {"turnOnState": {"value": "ON"}}) is None


def test_parse_switch() -> None:
    assert parse_command("SWITCH", "on") == [Command(action="turnOn")]
    assert parse_command("SWITCH", "off") == [Command(action="turnOff")]
    assert parse_command("SWITCH", "pause") == []


def test_parse_light_brightness() -> None:
    assert parse_command("LIGHT", "on#80") == [
        Command(action="turnOn"),
        Command(action="setBrightness", params={"attributeValue": 80}),
    ]


def test_parse_light_invalid_brightness() -> None:
    assert parse_command("LIGHT", "on#101") == []
    assert parse_command("LIGHT", "on#abc") == []


def test_parse_climate_on_off() -> None:
    assert parse_command("AIR_CONDITION", "on") == [Command(action="turnOn")]
    assert parse_command("AIR_CONDITION", "off") == [Command(action="turnOff")]


def test_parse_climate_mode_temp_fan() -> None:
    commands = parse_command("AIR_CONDITION", "on#2#23#3")
    assert commands == [
        Command(action="turnOn"),
        Command(action="setMode", params={"mode": "cool"}),
        Command(action="setTemperature", params={"target": 23}),
        Command(action="setFanSpeed", params={"speed": 3}),
    ]


def test_parse_climate_auto_fan_speed_zero() -> None:
    commands = parse_command("AIR_CONDITION", "on#1#20#0")
    assert Command(action="setFanSpeed", params={"speed": 4}) in commands


def test_parse_climate_unsupported_mode() -> None:
    commands = parse_command("AIR_CONDITION", "on#6")
    assert commands == [Command(action="turnOn")]


def test_parse_climate_out_of_range_temp() -> None:
    assert parse_command("AIR_CONDITION", "on#2#15") == [
        Command(action="turnOn"),
        Command(action="setMode", params={"mode": "cool"}),
    ]


def test_parse_cover() -> None:
    assert parse_command("CURTAIN", "on") == [Command(action="turnOn")]
    assert parse_command("CURTAIN", "off") == [Command(action="turnOff")]
    assert parse_command("CURTAIN", "pause") == [Command(action="stop")]
    assert parse_command("CURTAIN", "on#80") == [Command(action="turnOn")]


def test_parse_unsupported_type() -> None:
    assert parse_command("DOOR_LOCK", "on") == []


def test_parse_light_off_and_unsupported() -> None:
    """灯光关闭、非法指令与 RGB 提示分支。"""
    assert parse_command("LIGHT", "off") == [Command(action="turnOff")]
    assert parse_command("LIGHT", "toggle") == []
    assert parse_command("LIGHT", "on#80#FF0000") == [
        Command(action="turnOn"),
        Command(action="setBrightness", params={"attributeValue": 80}),
    ]


def test_parse_cover_invalid_position_and_unsupported() -> None:
    """窗帘非法位置值与非 on/off/pause 指令分支。"""
    assert parse_command("CURTAIN", "on#abc") == []
    assert parse_command("CURTAIN", "open") == []


def test_parse_climate_remaining_branches() -> None:
    """空调非法指令、非法模式码、非法/超高风速与摆动提示分支。"""
    assert parse_command("AIR_CONDITION", "heat") == []
    assert parse_command("AIR_CONDITION", "on#8") == []
    assert parse_command("AIR_CONDITION", "on#2#23#x") == [
        Command(action="turnOn"),
        Command(action="setMode", params={"mode": "cool"}),
        Command(action="setTemperature", params={"target": 23}),
    ]
    assert parse_command("AIR_CONDITION", "on#2#23#9") == [
        Command(action="turnOn"),
        Command(action="setMode", params={"mode": "cool"}),
        Command(action="setTemperature", params={"target": 23}),
    ]
    assert parse_command("AIR_CONDITION", "on#2#23#5") == [
        Command(action="turnOn"),
        Command(action="setMode", params={"mode": "cool"}),
        Command(action="setTemperature", params={"target": 23}),
    ]
    assert parse_command("AIR_CONDITION", "on#2#23#3#x") == [
        Command(action="turnOn"),
        Command(action="setMode", params={"mode": "cool"}),
        Command(action="setTemperature", params={"target": 23}),
        Command(action="setFanSpeed", params={"speed": 3}),
    ]
