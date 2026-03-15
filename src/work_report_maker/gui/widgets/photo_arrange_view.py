"""PhotoArrangePage 向けの入力専用 view / delegate。

このモジュールは「入力イベントをどう解釈するか」に責務を限定し、実際の並び替えや削除は
page 側へ signal で委譲する。view 自体が model を直接組み替えないことで、PhotoItem 実体と
表示行の同期責務を page 側に一元化している。
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent, QKeyEvent
from PySide6.QtWidgets import QListView, QStyleOptionViewItem, QStyledItemDelegate


class PageBorderDelegate(QStyledItemDelegate):
    """3 枚ごとの PDF ページ境界を一覧上に可視化する delegate。"""

    def __init__(self, photos_per_page: int, parent=None) -> None:
        super().__init__(parent)
        self._photos_per_page = photos_per_page

    def paint(
        self,
        painter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if not index.isValid():
            return

        model = index.model()
        if model is None:
            return

        super().paint(painter, option, index)
        row = index.row()
        total = model.rowCount()
        if row < 0 or row >= total:
            return

        if (row + 1) % self._photos_per_page == 0 and row < total - 1:
            painter.save()
            pen = painter.pen()
            pen.setColor(Qt.GlobalColor.darkGray)
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            right = option.rect.right()
            painter.drawLine(right, option.rect.top() + 4, right, option.rect.bottom() - 4)
            painter.restore()


class PhotoArrangeListView(QListView):
    """Arrange 用のキーボード操作と内部 D&D を signal 化する QListView。"""

    internal_drop_requested = Signal(int)
    delete_requested = Signal()
    move_single_left_requested = Signal()
    move_single_right_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        indexes = self.selectedIndexes()
        if not indexes:
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        # event.source() だけに頼ると外部 drag と識別しづらいケースがあるため、独自 MIME type を
        # 付けて「自分が開始した並べ替え drag」であることを明示する。
        mime_data.setData("application/x-work-report-maker-photo-arrange", b"move")
        drag.setMimeData(mime_data)

        current = self.currentIndex()
        if current.isValid():
            pixmap = self.viewport().grab(self.visualRect(current))
            if not pixmap.isNull():
                drag.setPixmap(pixmap)

        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._is_internal_drag(event):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._is_internal_drag(event):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if self._is_internal_drag(event):
            target_row = self._drop_row_for_event(event)
            self.internal_drop_requested.emit(target_row)
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        super().dropEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self.delete_requested.emit()
            event.accept()
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Left:
                self.move_single_left_requested.emit()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Right:
                self.move_single_right_requested.emit()
                event.accept()
                return

        super().keyPressEvent(event)

    def _is_internal_drag(self, event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> bool:
        mime_data = event.mimeData()
        return (
            event.source() is self
            and mime_data is not None
            and mime_data.hasFormat("application/x-work-report-maker-photo-arrange")
        )

    def _drop_row_for_event(self, event: QDropEvent) -> int:
        """ドロップ位置から「選択ブロックを挿入すべき row」を算出する。"""

        pos = event.position().toPoint()
        index = self.indexAt(pos)
        model = self.model()
        if model is None:
            return 0
        if not index.isValid():
            return model.rowCount()

        row = index.row()
        rect = self.visualRect(index)
        if pos.x() >= rect.center().x() or pos.y() >= rect.center().y():
            return row + 1
        return row
