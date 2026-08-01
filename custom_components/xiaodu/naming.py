"""设备名中的房间 token 剥离（naming normalization）。

用于把百度侧可能携带房间前缀/后缀的设备名规范化为纯设备名，
再与映射后的 HA 区域名组合（巴法云昵称）或作为 HA 设备默认名。

算法分两层：
    L1 锚点剥离：用 {小度房间名, 映射后区域名} 作为锚点 token，
        按 前缀 → 后缀 → 中缀 的顺序尝试剥离，剥离后清理边缘分隔符；
    L2 兜底：全部 token 均无法剥离（或剥离结果过短/为空）时返回原名。

保证：剥离失败时原样返回，绝不夸大改动（"尽力而为，最坏原样"）。
"""

from __future__ import annotations

# 剥离后需要清理的边缘分隔符
NAME_EDGE_SEPARATORS = " -_·:：/\\|()（）[]【】、,，.。~"


def strip_room(name: str, room_name: str, mapped_room: str) -> str:
    """尽力从设备名中剥离房间 token，返回剥离后的名字；无法剥离时原样返回。

    Args:
        name: 设备原始名（小度 friendly_name）。
        room_name: 小度房间名。
        mapped_room: 映射后的 HA 区域名（未映射时等于 room_name）。

    Returns:
        剥离后的设备名；剥离失败返回原 name。
    """
    if not name:
        return name
    tokens: list[str] = []
    for token in (room_name, mapped_room):
        if token and token not in tokens:
            tokens.append(token)
    for token in tokens:
        stripped = _strip_single_token(name, token)
        if stripped is not None:
            return stripped
    return name


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
    if not rest or len(rest) < 2:
        return None
    return rest
