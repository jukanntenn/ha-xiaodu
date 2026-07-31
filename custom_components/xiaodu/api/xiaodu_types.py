"""Xiaodu API 的数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ApplianceType(StrEnum):
    """小度设备类型（appliance type）枚举。

    见规范 §4.2.6。
    """

    LIGHT = "LIGHT"
    SOCKET = "SOCKET"
    SWITCH = "SWITCH"
    CLIMATE = "AIR_CONDITION"
    COVER = "CURTAIN"
    LOCK = "DOOR_LOCK"
    BUTTON = "CLOTHES_RACK"


@dataclass
class DeviceState:
    """小度设备状态。

    见规范 §4.2.4。
    """

    turn_on_state: str = "off"
    brightness: int | None = None
    color_temp: int | None = None
    temperature: int | None = None
    mode: str | None = None
    fan_speed: int | None = None


@dataclass
class Home:
    """小度家庭（Home）。"""

    home_id: str
    home_name: str
    room_count: int = 0
    device_count: int = 0


@dataclass
class Device:
    """小度设备（Device）。"""

    appliance_id: str
    friendly_name: str
    room_name: str
    appliance_types: list[str] = field(default_factory=list)
    state_setting: dict = field(default_factory=dict)
    bot_name: str | None = None


@dataclass
class DeviceDetail(Device):
    """小度设备详情（Device detail）。"""

    group_name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    firmware_version: str | None = None


@dataclass
class Command:
    """小度控制指令（Command）。"""

    action: str
    params: dict | None = None
