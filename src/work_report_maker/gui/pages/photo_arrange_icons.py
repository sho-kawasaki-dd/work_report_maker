from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap, QStandardItemModel

from work_report_maker.gui.pages.photo_import_page import PhotoItem


def snap_zoom_percent(percent: int, minimum: int, maximum: int, step: int) -> int:
    offset = round((percent - minimum) / step)
    snapped = minimum + (offset * step)
    return max(minimum, min(snapped, maximum))


def thumb_size_for_percent(percent: int, default_thumb_size: int) -> int:
    return max(1, round(default_thumb_size * percent / 100))


def zoom_label_text(percent: int) -> str:
    return f"サムネイルサイズ: {percent}%"


class PhotoArrangeIconController:
    def __init__(self, photo_key: Callable[[PhotoItem], int]) -> None:
        self._photo_key = photo_key
        self._cache_size: int | None = None
        self._cache: dict[int, QIcon] = {}

    @property
    def cache_size(self) -> int | None:
        return self._cache_size

    @property
    def cache(self) -> dict[int, QIcon]:
        return self._cache

    def clear(self) -> None:
        self._cache_size = None
        self._cache.clear()

    def icon_for_photo(self, photo: PhotoItem, size: int) -> QIcon:
        key = self._photo_key(photo)
        if self._cache_size != size:
            self._cache_size = size
            self._cache.clear()

        cached_icon = self._cache.get(key)
        if cached_icon is not None:
            return cached_icon

        pixmap = QPixmap()
        pixmap.loadFromData(photo.data)
        if pixmap.isNull():
            if photo.thumbnail is None or photo.thumbnail.isNull():
                return QIcon()
            pixmap = QPixmap.fromImage(photo.thumbnail)

        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        icon = QIcon(scaled)
        self._cache[key] = icon
        return icon

    def refresh_model_icons(
        self,
        model: QStandardItemModel,
        icon_size: int,
        photo_for_row: Callable[[int], PhotoItem | None],
    ) -> None:
        for row in range(model.rowCount()):
            item = model.item(row)
            photo = photo_for_row(row)
            if item is not None and photo is not None:
                item.setIcon(self.icon_for_photo(photo, icon_size))

    def apply_zoom_to_view(
        self,
        *,
        view,
        label,
        percent: int,
        default_thumb_size: int,
        grid_padding: int,
        model: QStandardItemModel,
        photo_for_row: Callable[[int], PhotoItem | None],
    ) -> None:
        thumb_size = thumb_size_for_percent(percent, default_thumb_size)
        label.setText(zoom_label_text(percent))
        view.setIconSize(QSize(thumb_size, thumb_size))
        view.setGridSize(QSize(thumb_size + grid_padding, thumb_size + grid_padding))
        self.refresh_model_icons(model, thumb_size, photo_for_row)
