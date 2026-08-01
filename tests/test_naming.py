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


def test_separators_definition() -> None:
    """分隔符常量包含常见中英文分隔符。"""
    for sep in ("-", "_", " ", "（", ")", "·"):
        assert sep in NAME_EDGE_SEPARATORS
