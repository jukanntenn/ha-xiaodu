"""Tests for the room-token stripping module.

Pure unit tests - no HTTP mocking needed.
"""

from __future__ import annotations

import pytest

from custom_components.xiaodu.naming import NAME_EDGE_SEPARATORS, strip_room


@pytest.mark.parametrize(
    ("name", "room_name", "mapped_room", "expected"),
    [
        # 前缀剥离（映射到自身，消除重复前缀）
        ("主卧空调", "主卧", "主卧", "空调"),
        # 前缀剥离 + 映射到其他区域（用户报告的核心场景）
        ("儿童房主灯", "儿童房", "书房", "主灯"),
        # 无房间 token，原样返回（不剥离、不拼接）
        ("电视墙射灯", "客厅", "客厅", "电视墙射灯"),
        ("全屋新风系统", "客厅", "客厅", "全屋新风系统"),
        # 后缀剥离 + 分隔符清理
        ("我的灯-客厅", "客厅", "客厅", "我的灯"),
        ("空调（主卧）", "主卧", "主卧", "空调"),
        # 中缀剥离（mapped_room 与 room_name 不同时优先剥离 room_name）
        ("我的书房空调", "书房", "多功能室", "我的空调"),
        # mapped_room 作为锚点（用户在 HA 纠正房间名后恰好是名字里的写法）
        ("主卫筒灯", "主卧", "主卫", "筒灯"),
        # 空格分隔的前缀
        ("客厅 我的灯", "客厅", "客厅", "我的灯"),
        # 无锚点命中 → 原样
        ("我的灯", "客厅", "客厅", "我的灯"),
        # 名字就是房间名 → 剥离后为空 → 原样
        ("儿童房", "儿童房", "书房", "儿童房"),
        # 剥离后过短 → 原样
        ("ab", "客厅", "客厅", "ab"),
        # 空名
        ("", "客厅", "客厅", ""),
        # 空房间
        ("电视墙射灯", "", "", "电视墙射灯"),
    ],
)
def test_strip_room(
    name: str,
    room_name: str,
    mapped_room: str,
    expected: str,
) -> None:
    """测试剥离算法的主要场景矩阵。"""
    assert strip_room(name, room_name, mapped_room) == expected


def test_strip_room_token_deduplicated() -> None:
    """room_name 与 mapped_room 相同时不重复尝试。"""
    assert strip_room("主卧主卧灯", "主卧", "主卧") == "主卧灯"


def test_strip_room_mapped_room_fallback() -> None:
    """room_name 未命中时回退 mapped_room 锚点。"""
    # 名字写的是映射后的区域名
    assert strip_room("书房主灯", "儿童房", "书房") == "主灯"


@pytest.mark.parametrize(
    ("name", "room_name", "mapped_room", "room_tokens", "expected"),
    [
        # 用户报告的核心 BUG：设备名嵌着他人房间词
        ("主卫灯带", "主卧", "主卧", {"主卧", "主卫"}, "灯带"),
        ("主卫射灯", "主卧", "主卧", {"主卧", "主卫"}, "射灯"),
        ("客厅灯带", "餐厅", "餐厅", {"餐厅", "客厅"}, "灯带"),
        # 迭代剥离多个相邻房间词
        ("主卧主卫灯带", "主卧", "主卧", {"主卧", "主卫"}, "灯带"),
        # 长房间词优先于短房间词（「主卧室」不应被「主卧」截断）
        ("主卧室吊灯", "主卧室", "主卧室", {"主卧", "主卧室"}, "吊灯"),
    ],
)
def test_strip_room_with_room_tokens(
    name: str,
    room_name: str,
    mapped_room: str,
    room_tokens: set[str],
    expected: str,
) -> None:
    """传入小度侧全部房间名时，剥掉设备名里嵌套的他人房间词。"""
    assert strip_room(name, room_name, mapped_room, room_tokens) == expected


def test_strip_room_room_tokens_none_keeps_legacy_behavior() -> None:
    """room_tokens=None 时退化为旧的「仅当前房间」单次剥离行为。"""
    # 设备名嵌着他人房间词，但不传 room_tokens → 旧逻辑剥不掉，原样返回
    assert strip_room("主卫灯带", "主卧", "主卧") == "主卫灯带"


def test_strip_room_room_tokens_empty_set_falls_back() -> None:
    """room_tokens 为空集时，回退到 {room_name, mapped_room} 单 token 剥离。"""
    assert strip_room("主卧空调", "主卧", "主卧", set()) == "空调"


def test_strip_room_name_equals_room_token() -> None:
    """设备名本身就是某个房间词时，剥完为空 → 原样返回（不夸大改动）。"""
    assert strip_room("主卫", "主卧", "主卧", {"主卧", "主卫"}) == "主卫"


def test_strip_room_strips_too_short_result() -> None:
    """前缀迭代剥离后结果过短（<2）时放弃，原样返回。"""
    # 假设房间词「主」，设备名「主灯」→ 剥完剩「灯」（长度 1）→ 放弃
    assert strip_room("主灯", "主卧", "主卧", {"主", "主卧"}) == "主灯"


def test_separators_definition() -> None:
    """分隔符常量包含常见中英文分隔符。"""
    for sep in ("-", "_", " ", "（", ")", "·"):
        assert sep in NAME_EDGE_SEPARATORS
