"""小度房间与 Home Assistant 区域（area）之间的房间映射（room mapping）。"""

from __future__ import annotations

from difflib import SequenceMatcher


class RoomMapper:
    """将小度房间名映射到 Home Assistant 区域（area）名。"""

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        """初始化房间映射器（room mapper）。"""
        self._mapping: dict[str, str] = mapping or {}

    @property
    def mapping(self) -> dict[str, str]:
        """返回当前的映射。"""
        return dict(self._mapping)

    def auto_map(self, xiaodu_rooms: list[str], ha_areas: list[str]) -> dict[str, str]:
        """自动将小度房间映射到 HA 区域（area）。

        Args:
            xiaodu_rooms: 小度房间名列表。
            ha_areas: Home Assistant 区域（area）名列表。

        Returns:
            映射字典 {xiaodu_room: ha_area}。
        """
        result: dict[str, str] = {}
        for room in xiaodu_rooms:
            best_score = 0.0
            best_area = room
            for area in ha_areas:
                score = self.calculate_similarity(room, area)
                if score > best_score:
                    best_score = score
                    best_area = area
            if best_score >= 0.6:
                result[room] = best_area
            else:
                result[room] = room
        self._mapping.update(result)
        return result

    def get_mapped_room(self, xiaodu_room: str) -> str:
        """获取小度房间对应的 HA 区域（area）。

        Args:
            xiaodu_room: 小度房间名。

        Returns:
            映射到的 HA 区域名；若未映射则返回原始房间名。
        """
        return self._mapping.get(xiaodu_room, xiaodu_room)

    def update_mapping(self, xiaodu_room: str, ha_area: str) -> None:
        """更新单条房间映射。

        Args:
            xiaodu_room: 小度房间名。
            ha_area: 要映射到的 HA 区域（area）名。
        """
        self._mapping[xiaodu_room] = ha_area

    @staticmethod
    def calculate_similarity(str1: str, str2: str) -> float:
        """计算两个字符串之间的相似度。

        规则：
            - 完全匹配：1.0
            - 一方包含另一方：0.8
            - 模糊匹配：SequenceMatcher 比率值
            - 不匹配：0.0

        Args:
            str1: 第一个字符串。
            str2: 第二个字符串。

        Returns:
            介于 0.0 与 1.0 之间的相似度得分。
        """
        if str1 == str2:
            return 1.0
        if str1 and str2 and (str1 in str2 or str2 in str1):
            return 0.8
        return SequenceMatcher(None, str1, str2).ratio()
