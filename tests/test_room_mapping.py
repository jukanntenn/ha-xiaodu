"""Tests for the room mapping module.

Pure unit tests - no HTTP mocking needed.
"""

from __future__ import annotations

from custom_components.xiaodu.room_mapping import RoomMapper


def test_auto_map_exact_match() -> None:
    """Test exact room name matching returns the area directly."""
    mapper = RoomMapper()
    xiaodu_rooms = ["客厅", "卧室", "厨房"]
    ha_areas = ["客厅", "卧室", "厨房", "卫生间"]
    result = mapper.auto_map(xiaodu_rooms, ha_areas)
    assert result == {"客厅": "客厅", "卧室": "卧室", "厨房": "厨房"}
    # Mapping is also stored internally
    assert mapper.get_mapped_room("客厅") == "客厅"


def test_auto_map_fuzzy_match() -> None:
    """Test fuzzy matching when one string contains the other.

    calculate_similarity returns 0.8 when one string is a substring
    of the other (e.g. "主卧" in "主卧室"). This is above the 0.6
    threshold so it should map.
    """
    mapper = RoomMapper()
    xiaodu_rooms = ["主卧"]
    ha_areas = ["主卧室", "客厅"]
    result = mapper.auto_map(xiaodu_rooms, ha_areas)
    # "主卧" is contained in "主卧室" -> similarity 0.8 >= 0.6 -> maps
    assert result == {"主卧": "主卧室"}


def test_auto_map_no_match() -> None:
    """Test that rooms with low similarity map to themselves."""
    mapper = RoomMapper()
    xiaodu_rooms = ["厨房"]
    ha_areas = ["Living Room", "Bedroom"]
    result = mapper.auto_map(xiaodu_rooms, ha_areas)
    # No match above threshold -> maps to itself
    assert result == {"厨房": "厨房"}


def test_auto_map_empty_inputs() -> None:
    """Test with empty inputs."""
    mapper = RoomMapper()
    assert mapper.auto_map([], []) == {}
    assert mapper.auto_map(["客厅"], []) == {"客厅": "客厅"}
    assert mapper.auto_map([], ["客厅"]) == {}


def test_calculate_similarity_exact() -> None:
    """Test similarity calculation for exact match."""
    assert RoomMapper.calculate_similarity("客厅", "客厅") == 1.0


def test_calculate_similarity_contains() -> None:
    """Test similarity calculation when one string contains the other."""
    # "主卧" in "主卧室"
    assert RoomMapper.calculate_similarity("主卧", "主卧室") == 0.8
    # "主卧室" contains "主卧"
    assert RoomMapper.calculate_similarity("主卧室", "主卧") == 0.8


def test_update_mapping() -> None:
    """Test manual mapping update."""
    mapper = RoomMapper()
    mapper.update_mapping("客厅", "Living Room")
    assert mapper.get_mapped_room("客厅") == "Living Room"
    # Unmapped room returns itself
    assert mapper.get_mapped_room("卧室") == "卧室"
