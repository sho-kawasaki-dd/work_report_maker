from __future__ import annotations

from typing import Callable, TypeVar


T = TypeVar("T")


def resolve_current_photo_key(
    items: list[T],
    previous_key: int | None,
    key_for_item: Callable[[T], int],
) -> int | None:
    if not items:
        return None
    if previous_key is not None:
        for item in items:
            if key_for_item(item) == previous_key:
                return previous_key
    return key_for_item(items[0])


def photo_index_for_key(
    items: list[T],
    photo_key: int | None,
    key_for_item: Callable[[T], int],
) -> int | None:
    if photo_key is None:
        return None
    for index, item in enumerate(items):
        if key_for_item(item) == photo_key:
            return index
    return None


def visible_range(total: int, current_index: int | None, view_mode: int) -> tuple[int, int]:
    if current_index is None or total <= 0:
        return (0, 0)
    start = max(0, min(current_index, total - 1))
    end = min(start + view_mode, total)
    return (start, end)


def shifted_photo_key(
    items: list[T],
    current_key: int | None,
    offset: int,
    key_for_item: Callable[[T], int],
) -> int | None:
    current_index = photo_index_for_key(items, current_key, key_for_item)
    if current_index is None:
        return None
    target_index = current_index + offset
    if target_index < 0 or target_index >= len(items):
        return None
    return key_for_item(items[target_index])


def layout_positions(visible_count: int) -> list[tuple[int, int, int, int, int]]:
    if visible_count <= 0:
        return []
    if visible_count == 1:
        return [(0, 0, 0, 1, 2)]
    positions: list[tuple[int, int, int, int, int]] = []
    for index in range(visible_count):
        row = index // 2
        col = index % 2
        positions.append((index, row, col, 1, 1))
    return positions


def move_button_states(
    total: int,
    current_index: int | None,
    focused_index: int | None,
) -> tuple[bool, bool, bool, bool]:
    has_previous = current_index is not None and current_index > 0
    has_next = current_index is not None and current_index < total - 1
    can_move_previous = focused_index is not None and focused_index > 0
    can_move_next = focused_index is not None and focused_index < total - 1
    return (has_previous, has_next, can_move_previous, can_move_next)