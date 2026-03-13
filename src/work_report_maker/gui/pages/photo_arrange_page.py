"""ウィザード Step 6: 画像並び替え・追加・削除ページ。

PhotoImportPage で読み込んだ画像のサムネイル一覧を表示し、
ドラッグ＆ドロップや矢印ボタンで並び替え、追加・削除を行う。

3枚ごとのページ区切りを QStyledItemDelegate でカスタム描画する。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSize, Qt, QThread, Signal
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
    QKeyEvent,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSlider,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWizardPage,
)

from PySide6.QtCore import QMimeData

from work_report_maker.gui.pages.photo_import_page import (
    PhotoItem,
    _ImportWorker,
    _format_failure_message,
)
from work_report_maker.services.image_processor import collect_image_paths

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter

    from work_report_maker.gui.main_window import ReportWizard

# 1ページあたりの写真枚数
_PHOTOS_PER_PAGE = 3

# デフォルトのサムネイルサイズ
_DEFAULT_THUMB_SIZE = 128

# サムネイルグリッドの余白 (アイコンサイズに加算)
_GRID_PADDING = 40

# モデル内で PhotoItem を参照するためのキー格納ロール
_PHOTO_KEY_ROLE = Qt.ItemDataRole.UserRole


# ── ページ区切りデリゲート ────────────────────────────────


class _PageBorderDelegate(QStyledItemDelegate):
    """3枚ごとにページ境界線を右端に描画するデリゲート。"""

    def paint(
        self,
        painter: QPainter,
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

        # 3枚ごとの最後のアイテム（0-indexed で 2, 5, 8, ...）の右端に線を引く
        # ただし最終アイテムには描画しない
        if (row + 1) % _PHOTOS_PER_PAGE == 0 and row < total - 1:
            painter.save()
            pen = painter.pen()
            pen.setColor(Qt.GlobalColor.darkGray)
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            right = option.rect.right()
            painter.drawLine(right, option.rect.top() + 4, right, option.rect.bottom() - 4)
            painter.restore()


class _PhotoArrangeListView(QListView):
    """Arrange ページ専用の DnD 制御付き QListView。"""

    internal_drop_requested = Signal(int)

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
        mime_data.setData(
            "application/x-work-report-maker-photo-arrange",
            b"move",
        )
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

    def _is_internal_drag(self, event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> bool:
        mime_data = event.mimeData()
        return (
            event.source() is self
            and mime_data is not None
            and mime_data.hasFormat("application/x-work-report-maker-photo-arrange")
        )

    def _drop_row_for_event(self, event: QDropEvent) -> int:
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


# ── メインページ ──────────────────────────────────────────


class PhotoArrangePage(QWizardPage):
    """画像並び替え・追加・削除ウィザードページ。

    UI 構成:
        - サムネイルグリッド (QListView IconMode + QStandardItemModel)
        - 移動ボタン (← →)
        - 追加・削除ボタン
        - ズームスライダー
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("写真の並び替え")
        self.setSubTitle(
            "写真の順序をドラッグ＆ドロップまたは矢印ボタンで変更できます。"
        )

        self._initialized = False  # initializePage 済みフラグ
        self._add_thread: QThread | None = None
        self._add_worker: _ImportWorker | None = None
        self._add_progress: QProgressDialog | None = None
        self._add_import_page = None
        self._add_insert_pos = 0
        self._add_counter = 0
        self._add_failures: list[tuple[str, str]] = []
        self._photo_items_by_key: dict[int, PhotoItem] = {}

        # ── サムネイルグリッド ──
        self._model = QStandardItemModel(self)
        self._view = _PhotoArrangeListView()
        self._view.setModel(self._model)
        self._view.setViewMode(QListView.ViewMode.IconMode)
        self._view.setIconSize(QSize(_DEFAULT_THUMB_SIZE, _DEFAULT_THUMB_SIZE))
        self._view.setGridSize(
            QSize(
                _DEFAULT_THUMB_SIZE + _GRID_PADDING,
                _DEFAULT_THUMB_SIZE + _GRID_PADDING,
            )
        )
        self._view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._view.setDragDropOverwriteMode(False)
        self._view.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._view.setResizeMode(QListView.ResizeMode.Adjust)
        self._view.setWrapping(True)
        self._view.setSpacing(4)
        self._view.setItemDelegate(_PageBorderDelegate(self._view))
        self._view.internal_drop_requested.connect(self._move_selection_to)

        # ── 操作ボタン群 ──
        btn_left = QToolButton()
        btn_left.setText("←")
        btn_left.setToolTip("選択した写真を左へ移動")
        btn_left.clicked.connect(self._move_left)

        btn_right = QToolButton()
        btn_right.setText("→")
        btn_right.setToolTip("選択した写真を右へ移動")
        btn_right.clicked.connect(self._move_right)

        btn_add = QPushButton("写真追加")
        btn_add.clicked.connect(self._add_photos)

        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._delete_selected)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_left)
        btn_row.addWidget(btn_right)
        btn_row.addStretch()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_delete)

        # ── ズームスライダー ──
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(64, 256)
        self._zoom_slider.setValue(_DEFAULT_THUMB_SIZE)
        self._zoom_slider.valueChanged.connect(self._on_zoom_changed)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("サムネイルサイズ:"))
        zoom_row.addWidget(self._zoom_slider, 1)

        # ── 情報ラベル ──
        self._info_label = QLabel()
        self._update_info_label()

        # ── レイアウト組立 ──
        main_layout = QVBoxLayout()
        main_layout.addLayout(btn_row)
        main_layout.addWidget(self._view, 1)
        main_layout.addLayout(zoom_row)
        main_layout.addWidget(self._info_label)
        self.setLayout(main_layout)

    # ── ウィザード参照 ────────────────────────────────────

    def _wizard(self) -> ReportWizard:
        from work_report_maker.gui.main_window import ReportWizard

        return cast(ReportWizard, self.wizard())

    # ── ページ初期化 ──────────────────────────────────────

    def initializePage(self) -> None:
        """PhotoImportPage の PhotoItem リストからモデルを構築する。

        前のページに戻って再度進んだ場合は、既存の並び順を維持する。
        """
        import_page = self._wizard()._photo_import_page
        import_items = import_page.photo_items
        import_keys = {self._photo_key(photo): photo for photo in import_items}

        if self._initialized:
            existing = {self._photo_key_at_row(row) for row in range(self._model.rowCount())}
            # 新規追加分のみ末尾に追加
            for photo in import_items:
                key = self._photo_key(photo)
                if key not in existing:
                    self._append_item(photo)
            # インポートページから削除されたアイテムをモデルから除去
            rows_to_remove = []
            for row in range(self._model.rowCount()):
                key = self._photo_key_at_row(row)
                if key is not None and key not in import_keys:
                    rows_to_remove.append(row)
            for row in reversed(rows_to_remove):
                self._model.removeRow(row)
        else:
            self._model.clear()
            for photo in import_items:
                self._append_item(photo)
            self._initialized = True

        self._photo_items_by_key = dict(import_keys)
        self._update_info_label()

    def _photo_key(self, photo: PhotoItem) -> int:
        return id(photo)

    def _photo_key_at_row(self, row: int) -> int | None:
        item = self._model.item(row)
        if item is None:
            return None
        key = item.data(_PHOTO_KEY_ROLE)
        return key if isinstance(key, int) else None

    def _photo_for_row(self, row: int) -> PhotoItem | None:
        key = self._photo_key_at_row(row)
        if key is None:
            return None
        return self._photo_items_by_key.get(key)

    def _make_model_item(self, photo: PhotoItem) -> QStandardItem:
        item = QStandardItem()
        item.setText(photo.filename)
        if photo.thumbnail is not None and not photo.thumbnail.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(photo.thumbnail)))
        item.setData(self._photo_key(photo), _PHOTO_KEY_ROLE)
        item.setEditable(False)
        return item

    def _append_item(self, photo: PhotoItem) -> None:
        """PhotoItem を QStandardItemModel に追加する。"""
        self._photo_items_by_key[self._photo_key(photo)] = photo
        self._model.appendRow(self._make_model_item(photo))

    def _insert_item(self, row: int, photo: PhotoItem) -> None:
        """PhotoItem を指定行に挿入する。"""
        self._photo_items_by_key[self._photo_key(photo)] = photo
        self._model.insertRow(row, self._make_model_item(photo))

    # ── ズーム ────────────────────────────────────────────

    def _on_zoom_changed(self, value: int) -> None:
        self._view.setIconSize(QSize(value, value))
        self._view.setGridSize(QSize(value + _GRID_PADDING, value + _GRID_PADDING))

    # ── 並び替え (矢印ボタン) ─────────────────────────────

    def _selected_rows_sorted(self) -> list[int]:
        """選択中の行インデックスを昇順で返す。"""
        indexes = self._view.selectionModel().selectedIndexes()
        return sorted({idx.row() for idx in indexes})

    def _select_rows(self, rows: list[int]) -> None:
        selection_model = self._view.selectionModel()
        selection_model.clearSelection()
        if not rows:
            return

        for row in rows:
            index = self._model.index(row, 0)
            selection_model.select(index, selection_model.SelectionFlag.Select)

        current_index = self._model.index(rows[0], 0)
        selection_model.setCurrentIndex(
            current_index,
            selection_model.SelectionFlag.NoUpdate,
        )

    def _move_rows_to(self, rows: list[int], insert_row: int) -> list[int]:
        if not rows:
            return []

        row_count = self._model.rowCount()
        if row_count == 0:
            return []

        rows = sorted(set(rows))
        insert_row = max(0, min(insert_row, row_count))

        if rows[0] <= insert_row <= rows[-1] + 1:
            return rows

        moved_rows: list[list[QStandardItem]] = []
        for offset, row in enumerate(rows):
            taken = self._model.takeRow(row - offset)
            if taken:
                moved_rows.append(taken)

        if not moved_rows:
            return rows

        adjusted_insert = insert_row - sum(1 for row in rows if row < insert_row)
        adjusted_insert = max(0, min(adjusted_insert, self._model.rowCount()))

        new_rows: list[int] = []
        for index, taken in enumerate(moved_rows):
            destination = adjusted_insert + index
            self._model.insertRow(destination, taken)
            new_rows.append(destination)

        self._update_info_label()
        return new_rows

    def _move_selection_to(self, insert_row: int) -> None:
        rows = self._selected_rows_sorted()
        new_rows = self._move_rows_to(rows, insert_row)
        self._select_rows(new_rows)

    def _move_left(self) -> None:
        """選択中のアイテム群を左 (行番号を減らす方向) に移動する。"""
        rows = self._selected_rows_sorted()
        if not rows or rows[0] == 0:
            return
        new_rows = self._move_rows_to(rows, rows[0] - 1)
        self._select_rows(new_rows)

    def _move_right(self) -> None:
        """選択中のアイテム群を右 (行番号を増やす方向) に移動する。"""
        rows = self._selected_rows_sorted()
        if not rows or rows[-1] >= self._model.rowCount() - 1:
            return
        new_rows = self._move_rows_to(rows, rows[-1] + 2)
        self._select_rows(new_rows)

    # ── 追加操作 ──────────────────────────────────────────

    def _add_photos(self) -> None:
        """ファイル選択ダイアログを開き、画像を追加する。"""
        if self._add_thread is not None and self._add_thread.isRunning():
            return

        self._add_failures.clear()

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "写真を追加",
            "",
            "画像/ZIP (*.jpg *.jpeg *.png *.zip)",
        )
        if not files:
            return
        all_paths: list[Path] = []
        for f in files:
            all_paths.extend(collect_image_paths(Path(f)))
        if not all_paths:
            return

        # 挿入位置: 選択中の最小行の直後、未選択なら末尾
        rows = self._selected_rows_sorted()
        insert_pos = (rows[0] + 1) if rows else self._model.rowCount()

        # 圧縮設定は PhotoImportPage から参照
        import_page = self._wizard()._photo_import_page

        worker = _ImportWorker(
            all_paths,
            dpi=import_page.dpi(),
            jpeg_quality=import_page.jpeg_quality(),
            png_quality_max=import_page.png_quality_max(),
        )

        thread = QThread(self)
        worker.moveToThread(thread)

        total = len(all_paths)
        progress = QProgressDialog(
            "写真を追加しています...", "キャンセル", 0, total, self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        # 追加アイテムのカウンタ (挿入位置をずらすために使用)
        self._add_counter = 0

        self._add_thread = thread
        self._add_worker = worker
        self._add_progress = progress
        self._add_import_page = import_page
        self._add_insert_pos = insert_pos

        worker.progress.connect(progress.setValue, Qt.ConnectionType.QueuedConnection)
        worker.items_ready.connect(self._on_add_items_ready, Qt.ConnectionType.QueuedConnection)
        worker.failures_ready.connect(self._record_add_failures, Qt.ConnectionType.QueuedConnection)
        progress.canceled.connect(self._cancel_add_photos)

        worker.finished.connect(self._on_add_worker_finished, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(self._on_add_thread_finished, Qt.ConnectionType.QueuedConnection)
        thread.started.connect(worker.run, Qt.ConnectionType.QueuedConnection)
        thread.start()

    def _on_add_items_ready(self, items: list[PhotoItem]) -> None:
        import_page = self._add_import_page
        if import_page is None:
            return

        self._view.setUpdatesEnabled(False)
        try:
            for item in items:
                pos = self._add_insert_pos + self._add_counter
                self._insert_item(pos, item)
                self._add_counter += 1
        finally:
            self._view.setUpdatesEnabled(True)

        import_page.add_photo_items(items)
        self._update_info_label()

    def _cancel_add_photos(self) -> None:
        if self._add_worker is not None:
            self._add_worker.cancel()

    def _on_add_worker_finished(self) -> None:
        if self._add_thread is not None:
            self._add_thread.quit()

    def _on_add_thread_finished(self) -> None:
        self._cleanup_add_state()
        self._show_add_failures()

    def _cleanup_add_state(self) -> None:
        if self._add_progress is not None:
            self._add_progress.close()
            self._add_progress.deleteLater()
            self._add_progress = None

        if self._add_worker is not None:
            self._add_worker.deleteLater()
            self._add_worker = None

        if self._add_thread is not None:
            self._add_thread.deleteLater()
            self._add_thread = None

        self._add_import_page = None
        self._add_insert_pos = 0
        self._add_counter = 0

    def cancel_active_import(self) -> bool:
        if self._add_worker is not None:
            self._add_worker.cancel()
        if self._add_thread is not None and self._add_thread.isRunning():
            self._add_thread.quit()
            if not self._add_thread.wait(2000):
                return False
        self._cleanup_add_state()
        return True

    def _record_add_failures(self, failures: list[tuple[str, str]]) -> None:
        self._add_failures.extend(failures)

    def _show_add_failures(self) -> None:
        if not self._add_failures:
            return

        message = _format_failure_message(self._add_failures)
        self._add_failures.clear()
        QMessageBox.warning(self, "写真追加エラー", message)

    # ── 削除操作 ──────────────────────────────────────────

    def _delete_selected(self) -> None:
        """選択中のアイテムを確認後に削除する。"""
        rows = self._selected_rows_sorted()
        if not rows:
            return

        count = len(rows)
        reply = QMessageBox.question(
            self,
            "削除確認",
            f"{count} 枚の画像を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # PhotoImportPage のリストからも除去
        import_page = self._wizard()._photo_import_page
        items_to_remove: list[PhotoItem] = []
        for row in rows:
            photo = self._photo_for_row(row)
            if photo is not None:
                items_to_remove.append(photo)

        import_page.remove_photo_items(items_to_remove)
        for photo in items_to_remove:
            self._photo_items_by_key.pop(self._photo_key(photo), None)

        # モデルから逆順に除去
        for row in reversed(rows):
            self._model.removeRow(row)
        self._update_info_label()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Delete キーで選択中のアイテムを削除する。"""
        if event.key() == Qt.Key.Key_Delete:
            self._delete_selected()
        else:
            super().keyPressEvent(event)

    # ── データ収集 ────────────────────────────────────────

    def collect_photo_items(self) -> list[PhotoItem]:
        """並び順に PhotoItem リストを返す。"""
        items: list[PhotoItem] = []
        for row in range(self._model.rowCount()):
            photo = self._photo_for_row(row)
            if photo is not None:
                items.append(photo)
        return items

    # ── 情報表示 ──────────────────────────────────────────

    def _update_info_label(self) -> None:
        total = self._model.rowCount()
        pages = (total + _PHOTOS_PER_PAGE - 1) // _PHOTOS_PER_PAGE if total else 0
        self._info_label.setText(
            f"写真 {total} 枚 / {pages} ページ "
            f"（1ページあたり {_PHOTOS_PER_PAGE} 枚）"
        )
