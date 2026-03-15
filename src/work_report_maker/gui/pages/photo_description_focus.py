from __future__ import annotations

from collections.abc import Iterable


def resolve_focused_photo_key(
    visible_keys: Iterable[int],
    focused_key: int | None,
    current_key: int | None,
) -> int | None:
    visible_key_set = set(visible_keys)
    if focused_key is not None and focused_key in visible_key_set:
        return focused_key
    if current_key is not None and current_key in visible_key_set:
        return current_key
    return next(iter(visible_key_set), None)


def is_active_photo_key(photo_key: int | None, focused_key: int | None) -> bool:
    return photo_key is not None and focused_key is not None and photo_key == focused_key