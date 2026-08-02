"""设备名中的房间 token 剥离（naming normalization）。

用于把百度侧可能携带房间前缀/后缀的设备名规范化为纯设备名，
再与映射后的 HA 区域名组合（巴法云昵称）或作为 HA 设备默认名。

算法分两层：
    L1 锚点剥离：用「小度侧全部房间名 + 映射后区域名」作为锚点 token，
        按 前缀迭代 → 后缀 → 中缀 的顺序剥离，剥离后清理边缘分隔符；
    L2 兜底：全部 token 均无法剥离（或剥离结果过短/为空）时返回原名。

前缀迭代剥离的动机：用户在米家/小度里给「跨区域设备」起名时，常把
相邻房间词一起写进设备名（如设备在「主卧」房间却叫「主卫灯带」、
在「餐厅」却叫「客厅灯带」）。仅以「当前房间」做锚点无法识别这些
嵌套的他人房间词，导致拼接昵称时房间词叠加（「主卧主卫灯带」）。
因此剥离锚点必须覆盖小度侧的所有房间名，并反复剥前缀直到开头不再是
任何房间词。

保证：剥离失败时原样返回，绝不夸大改动（"尽力而为，最坏原样"）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

# 剥离后需要清理的边缘分隔符
NAME_EDGE_SEPARATORS = " -_·:：/\\|()（）[]【】、,，.。~"

# 剥离后允许的最短结果长度（避免把「客厅」剥成空串或「灯」之类的误伤）
_MIN_STRIPPED_LENGTH = 2


def strip_room(
    name: str,
    room_name: str,
    mapped_room: str,
    room_tokens: Collection[str] | None = None,
) -> str:
    """尽力从设备名中剥离房间 token，返回剥离后的名字；无法剥离时原样返回。

    Args:
        name: 设备原始名（小度 friendly_name）。
        room_name: 设备所在的小度房间名。
        mapped_room: 映射后的 HA 区域名（未映射时等于 room_name）。
        room_tokens: 小度侧的全部房间名集合，用作前缀迭代剥离的锚点。
            传入后，会反复从 name 开头剥掉任意房间词（如设备在「主卧」
            却叫「主卫灯带」，「主卫」也是真实房间，需剥掉）；为 ``None``
            时仅用 ``room_name``/``mapped_room`` 做单次前缀剥离。

    Returns:
        剥离后的设备名；剥离失败返回原 name。
    """
    if not name:
        return name

    # L1-a：前缀迭代剥离——用全部房间词反复剥开头，直到开头不再是房间词。
    # 这一步专治「设备名嵌着别人房间词」的场景（主卫灯带@主卧 → 灯带）。
    if room_tokens:
        result = _strip_prefix_iter(name, room_tokens)
        if result is not None:
            return result

    # L1-b：单 token 兜底——仅用 {room_name, mapped_room}，按
    # 前缀 → 后缀 → 中缀 各尝试一次（保留对后缀/中缀场景的覆盖）。
    tokens: list[str] = []
    for token in (room_name, mapped_room):
        if token and token not in tokens:
            tokens.append(token)
    for token in tokens:
        stripped = _strip_single_token(name, token)
        if stripped is not None:
            return stripped

    return name


def _strip_prefix_iter(name: str, room_tokens: Collection[str]) -> str | None:
    """反复从 name 开头剥掉任意房间 token，直到开头不再是房间词。

    每剥一次后清理边缘分隔符；任何一步结果为空/过短则整体放弃（返回 None，
    交由调用方走兜底）。最终结果与原 name 相同（没有任何房间前缀可剥）时
    也返回 None，让调用方继续尝试后缀/中缀剥离。
    """
    # 按长度降序，优先匹配更长的房间词（如「主卧室」优先于「主卧」），
    # 避免短词贪婪截断长词。
    sorted_tokens = sorted((t for t in room_tokens if t), key=len, reverse=True)
    result = name
    stripped_any = False
    while True:
        for token in sorted_tokens:
            if result == token:
                # 名字本身就是房间词 → 剥完为空 → 放弃
                return None
            if result.startswith(token):
                rest = result[len(token) :]
                rest = rest.strip(NAME_EDGE_SEPARATORS).strip()
                if not rest or len(rest) < _MIN_STRIPPED_LENGTH:
                    return None
                result = rest
                stripped_any = True
                break
        else:
            # 开头已无任何房间词可剥
            break
    return result if stripped_any and result != name else None


def _strip_single_token(name: str, token: str) -> str | None:
    """用单个 token 尝试剥离；成功返回剥离后的名字，失败返回 None。

    位置优先级：前缀 → 后缀 → 中缀（只剥离第一处）。
    剥离后清理边缘分隔符；结果为空或过短（<2 字符）视为剥离失败。
    """
    if token not in name:
        return None
    if name.startswith(token):
        rest = name[len(token) :]
    elif name.endswith(token):
        rest = name[: -len(token)]
    else:
        rest = name.replace(token, "", 1)
    rest = rest.strip(NAME_EDGE_SEPARATORS).strip()
    if not rest or len(rest) < _MIN_STRIPPED_LENGTH:
        return None
    return rest
