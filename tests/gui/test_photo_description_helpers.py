from __future__ import annotations

from PySide6.QtCore import QDate

from work_report_maker.gui.pages.photo_description_dates import format_work_date, parse_work_date
from work_report_maker.gui.pages.photo_description_focus import is_active_photo_key, resolve_focused_photo_key
from work_report_maker.gui.pages.photo_description_navigation import (
    layout_positions,
    move_button_states,
    photo_index_for_key,
    resolve_current_photo_key,
    shifted_photo_key,
    visible_range,
)


def _photo_key(value: str) -> int:
    return hash(value)


def test_parse_and_format_work_date_round_trip() -> None:
    value = "2025年 3月 27日(木)"

    parsed = parse_work_date(value)

    assert parsed == QDate(2025, 3, 27)
    assert format_work_date(parsed) == value


def test_parse_work_date_returns_none_for_invalid_text() -> None:
    assert parse_work_date("invalid") is None
    assert parse_work_date("2025/03/27") is None


def test_resolve_current_photo_key_keeps_previous_when_present() -> None:
    items = ["a", "b", "c"]

    resolved = resolve_current_photo_key(items, _photo_key("b"), _photo_key)

    assert resolved == _photo_key("b")


def test_resolve_current_photo_key_falls_back_to_first_item() -> None:
    items = ["a", "b", "c"]

    resolved = resolve_current_photo_key(items, _photo_key("missing"), _photo_key)

    assert resolved == _photo_key("a")


def test_visible_range_and_shifted_photo_key_follow_current_anchor() -> None:
    items = ["a", "b", "c", "d"]
    current_key = _photo_key("b")

    current_index = photo_index_for_key(items, current_key, _photo_key)

    assert current_index == 1
    assert visible_range(len(items), current_index, 2) == (1, 3)
    assert shifted_photo_key(items, current_key, 1, _photo_key) == _photo_key("c")
    assert shifted_photo_key(items, current_key, -1, _photo_key) == _photo_key("a")
    assert shifted_photo_key(items, current_key, -2, _photo_key) is None


def test_layout_positions_handles_single_and_grid_modes() -> None:
    assert layout_positions(0) == []
    assert layout_positions(1) == [(0, 0, 0, 1, 2)]
    assert layout_positions(4) == [
        (0, 0, 0, 1, 1),
        (1, 0, 1, 1, 1),
        (2, 1, 0, 1, 1),
        (3, 1, 1, 1, 1),
    ]


def test_move_button_states_reflect_navigation_and_reorder_edges() -> None:
    assert move_button_states(4, 1, 1) == (True, True, True, True)
    assert move_button_states(4, 0, 0) == (False, True, False, True)
    assert move_button_states(4, 3, 3) == (True, False, True, False)
    assert move_button_states(0, None, None) == (False, False, False, False)


def test_resolve_focused_photo_key_prefers_visible_focus_then_current() -> None:
    visible_keys = [_photo_key("b"), _photo_key("c")]

    assert resolve_focused_photo_key(visible_keys, _photo_key("c"), _photo_key("b")) == _photo_key("c")
    assert resolve_focused_photo_key(visible_keys, _photo_key("a"), _photo_key("b")) == _photo_key("b")
    assert resolve_focused_photo_key([], _photo_key("a"), _photo_key("b")) is None


def test_is_active_photo_key_matches_focused_key() -> None:
    key = _photo_key("a")

    assert is_active_photo_key(key, key) is True
    assert is_active_photo_key(key, _photo_key("b")) is False
    assert is_active_photo_key(None, key) is False