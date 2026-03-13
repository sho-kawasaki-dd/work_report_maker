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

# サムネイルズーム率
_MIN_ZOOM_PERCENT = 50
_MAX_ZOOM_PERCENT = 200
_DEFAULT_ZOOM_PERCENT = 100
_ZOOM_STEP_PERCENT = 25

# サムネイルグリッドの余白 (アイコンサイズに加算)
_GRID_PADDING = 40

# モデル内で PhotoItem を参照するためのキー格納ロール
_PHOTO_KEY_ROLE = Qt.ItemDataRole.UserRole

# QListView 上の各アイテムは QStandardItem だが、実データ本体は PhotoImportPage 側の
# PhotoItem にある。ここでは UserRole に「PhotoItem を一意に引くためのキー」だけを
# 持たせて、表示の並び順と実データを疎結合に管理する。


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

        # 標準の描画処理で、アイコン・選択状態・テキストをまず描く。
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

    # 内部 DnD 完了後に、ドロップ先行番号だけを親ページへ通知する。
    internal_drop_requested = Signal(int)

    # 実際の削除や移動ロジックは親ページ側に集約し、View はキー入力の仲介だけを担う。
    delete_requested = Signal()
    move_single_left_requested = Signal()
    move_single_right_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Arrange ページ内では「一覧の中だけで写真を並び替える」ことが主目的なので、
        # 受け入れ・ドラッグ開始・ドロップ位置表示をすべて有効にしておく。
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        indexes = self.selectedIndexes()
        if not indexes:
            return

        # Qt 標準の内部移動に完全に任せるのではなく、独自 MIME タイプを使って
        # 「この View 内の写真移動」であることを明示的に識別する。
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData(
            "application/x-work-report-maker-photo-arrange",
            b"move",
        )
        drag.setMimeData(mime_data)

        current = self.currentIndex()
        if current.isValid():
            # ドラッグ中の視覚フィードバックとして、現在アイテムの見た目をそのまま掴ませる。
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
        # キーイベントは View が直接受けやすいため、親ページにシグナルで委譲する。
        # これにより、フォーカスが QListView 上にある通常利用時でもショートカットが効く。
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
        # 自分自身を source とし、かつ独自 MIME タイプを持つイベントだけを
        # Arrange ページ独自の並び替えとして扱う。
        mime_data = event.mimeData()
        return (
            event.source() is self
            and mime_data is not None
            and mime_data.hasFormat("application/x-work-report-maker-photo-arrange")
        )

    def _drop_row_for_event(self, event: QDropEvent) -> int:
        # ドロップ位置が既存アイテムの前か後かを、アイテム中心との相対位置で判定する。
        # IconMode では単純な縦リストとは限らないため、x/y のどちらかが中心を超えたら
        # 「そのアイテムの後ろ」とみなす簡易ルールにしている。
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

        # initializePage() を複数回呼ばれても、ユーザーが Arrange ページ上で並べた順序を
        # 可能な限り維持したいので、初回構築かどうかをフラグで管理する。
        self._initialized = False  # initializePage 済みフラグ

        # 「写真追加」実行中のワーカースレッド関連状態。
        self._add_thread: QThread | None = None
        self._add_worker: _ImportWorker | None = None
        self._add_progress: QProgressDialog | None = None
        self._add_import_page = None
        self._add_insert_pos = 0
        self._add_counter = 0
        self._add_failures: list[tuple[str, str]] = []

        # QStandardItemModel と PhotoItem 実体の対応表。モデルにはキーだけを保存し、
        # 実データはこの辞書経由で引く。
        self._photo_items_by_key: dict[int, PhotoItem] = {}

        # ズーム倍率ごとの巨大なキャッシュは持たず、「現在表示中の倍率 1 つ分だけ」
        # QIcon を保持する軽量キャッシュ。倍率が変わったら丸ごと捨てる。
        self._icon_cache_size: int | None = None
        self._icon_cache: dict[int, QIcon] = {}

        # ── サムネイルグリッド ──
        self._model = QStandardItemModel(self)
        self._view = _PhotoArrangeListView()
        self._view.setModel(self._model)

        # 一覧はグリッド状のアイコン表示とし、下に通し番号キャプションを出す。
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

        # View が拾った操作イベントを、実処理を持つページメソッドへ接続する。
        self._view.internal_drop_requested.connect(self._move_selection_to)
        self._view.delete_requested.connect(self._delete_selected)
        self._view.move_single_left_requested.connect(self._move_single_selection_left)
        self._view.move_single_right_requested.connect(self._move_single_selection_right)

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
        self._zoom_slider.setRange(_MIN_ZOOM_PERCENT, _MAX_ZOOM_PERCENT)
        self._zoom_slider.setSingleStep(_ZOOM_STEP_PERCENT)
        self._zoom_slider.setPageStep(_ZOOM_STEP_PERCENT)
        self._zoom_slider.setTickInterval(_ZOOM_STEP_PERCENT)
        self._zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._zoom_slider.setValue(_DEFAULT_ZOOM_PERCENT)

        # スライダーは細かく連続変化させず、25% 刻みで段階的に動かす。
        self._zoom_slider.valueChanged.connect(self._on_zoom_changed)

        self._zoom_label = QLabel()
        self._update_zoom_label(_DEFAULT_ZOOM_PERCENT)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(self._zoom_label)
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
        # 親 wizard への型付きアクセサ。各ページ間同期に使う。
        from work_report_maker.gui.main_window import ReportWizard

        return cast(ReportWizard, self.wizard())

    # ── ページ初期化 ──────────────────────────────────────

    def initializePage(self) -> None:
        """PhotoImportPage の PhotoItem リストからモデルを構築する。

        前のページに戻って再度進んだ場合は、既存の並び順を維持する。
        """

        # Arrange ページは PhotoImportPage をデータソースとして参照する。ここで毎回
        # import 側の状態を取り込みつつ、Arrange 側での並び替え結果はできるだけ残す。
        import_page = self._wizard()._photo_import_page
        import_items = import_page.photo_items
        import_keys = {self._photo_key(photo): photo for photo in import_items}

        if self._initialized:
            # 既存モデルにない写真だけを末尾追加し、逆に import 側から消えた写真は除去する。
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
            # 初回表示時は import 側の現在順で素直にモデルを作る。
            self._model.clear()
            for photo in import_items:
                self._append_item(photo)
            self._initialized = True

        # モデル差し替え後に、実データ辞書・表示番号・アイコン表示を同期させる。
        self._photo_items_by_key = dict(import_keys)
        self._refresh_item_labels()
        self._refresh_item_icons()
        self._update_info_label()

    def _photo_key(self, photo: PhotoItem) -> int:
        # PhotoItem 自体は dataclass だが、等値性より「同一インスタンス性」で扱いたいので id を使う。
        return id(photo)

    def _photo_key_at_row(self, row: int) -> int | None:
        # モデル行から PhotoItem 実体を引くためのキー取得。
        item = self._model.item(row)
        if item is None:
            return None
        key = item.data(_PHOTO_KEY_ROLE)
        return key if isinstance(key, int) else None

    def _photo_for_row(self, row: int) -> PhotoItem | None:
        # 行番号 -> UserRole のキー -> 実体辞書、の順で辿る。
        key = self._photo_key_at_row(row)
        if key is None:
            return None
        return self._photo_items_by_key.get(key)

    def _row_for_photo(self, photo: PhotoItem) -> int | None:
        # PhotoItem 実体から現在の表示行を逆引きする。
        for row in range(self._model.rowCount()):
            if self._photo_for_row(row) is photo:
                return row
        return None

    def _make_model_item(self, photo: PhotoItem) -> QStandardItem:
        # 実データ本体は PhotoItem 側にあるので、モデル項目は表示用の薄いラッパーに留める。
        # テキストは後で現在行番号から再計算するため、ここでは空で作る。
        item = QStandardItem()
        item.setText("")
        item.setData(self._photo_key(photo), _PHOTO_KEY_ROLE)
        item.setEditable(False)

        # キャプションは番号表示へ切り替えたが、元ファイル名も確認できるようツールチップには残す。
        item.setToolTip(photo.filename)
        return item

    def _append_item(self, photo: PhotoItem) -> None:
        """PhotoItem を QStandardItemModel に追加する。"""

        # 実体辞書にも先に登録しておくことで、後続のアイコン更新がすぐ使えるようにする。
        self._photo_items_by_key[self._photo_key(photo)] = photo
        self._model.appendRow(self._make_model_item(photo))

    def _insert_item(self, row: int, photo: PhotoItem) -> None:
        """PhotoItem を指定行に挿入する。"""
        self._photo_items_by_key[self._photo_key(photo)] = photo
        self._model.insertRow(row, self._make_model_item(photo))

    def _refresh_item_labels(self) -> None:
        # 表示番号は常に「現在の見た目の順序」を正とし、1 始まりで通し番号を振り直す。
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item is not None:
                item.setText(str(row + 1))

    def _clear_icon_cache(self) -> None:
        # キャッシュ対象は 1 倍率分だけなので、倍率変更やデータ破棄時は丸ごとクリアで十分。
        self._icon_cache_size = None
        self._icon_cache.clear()

    def _make_icon_for_photo(self, photo: PhotoItem, size: int) -> QIcon:
        # 別倍率へ切り替わったら、以前の倍率のキャッシュは使わない。
        key = self._photo_key(photo)
        if self._icon_cache_size != size:
            self._icon_cache_size = size
            self._icon_cache.clear()

        # 同じ倍率内では同一 PhotoItem の再スケーリングを避ける。
        cached_icon = self._icon_cache.get(key)
        if cached_icon is not None:
            return cached_icon

        # まず圧縮済み bytes から表示用 pixmap を作る。これにより、100% 超でも
        # 128px の固定サムネイルに縛られず、必要サイズで再描画できる。
        pixmap = QPixmap()
        pixmap.loadFromData(photo.data)
        if pixmap.isNull():
            # まれに bytes からの復元に失敗した場合だけ、既存 thumbnail をフォールバック利用する。
            if photo.thumbnail is None or photo.thumbnail.isNull():
                return QIcon()
            pixmap = QPixmap.fromImage(photo.thumbnail)

        # 画像比率は崩さず、要求された一辺サイズに収まるよう滑らかに縮放する。
        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        icon = QIcon(scaled)
        self._icon_cache[key] = icon
        return icon

    def _refresh_item_icons(self) -> None:
        # 現在の iconSize に合わせて、全アイテムの見た目をまとめて同期する。
        icon_size = self._view.iconSize().width()
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            photo = self._photo_for_row(row)
            if item is not None and photo is not None:
                item.setIcon(self._make_icon_for_photo(photo, icon_size))

    # ── ズーム ────────────────────────────────────────────

    def _update_zoom_label(self, percent: int) -> None:
        # いま UI 上で何 % なのかが一目でわかるようにする。
        self._zoom_label.setText(f"サムネイルサイズ: {percent}%")

    def _snap_zoom_percent(self, percent: int) -> int:
        # スライダー値を 25% 刻みに丸める。50%〜200% の範囲外には出さない。
        offset = round((percent - _MIN_ZOOM_PERCENT) / _ZOOM_STEP_PERCENT)
        snapped = _MIN_ZOOM_PERCENT + (offset * _ZOOM_STEP_PERCENT)
        return max(_MIN_ZOOM_PERCENT, min(snapped, _MAX_ZOOM_PERCENT))

    def _thumb_size_for_percent(self, percent: int) -> int:
        # 100% を 128px と解釈した実表示サイズへ変換する。
        return max(1, round(_DEFAULT_THUMB_SIZE * percent / 100))

    def _on_zoom_changed(self, value: int) -> None:
        # ユーザーが途中の値へ動かしても、内部では 25% 刻みの代表値に正規化して扱う。
        snapped_value = self._snap_zoom_percent(value)
        if snapped_value != value:
            # 再代入時にシグナルが無限再帰しないよう一時的にブロックする。
            self._zoom_slider.blockSignals(True)
            self._zoom_slider.setValue(snapped_value)
            self._zoom_slider.blockSignals(False)
        value = snapped_value

        thumb_size = self._thumb_size_for_percent(value)
        self._update_zoom_label(value)

        # 枠サイズと実アイコン表示の両方を更新しないと、「枠だけ大きい」状態になる。
        self._view.setIconSize(QSize(thumb_size, thumb_size))
        self._view.setGridSize(QSize(thumb_size + _GRID_PADDING, thumb_size + _GRID_PADDING))
        self._refresh_item_icons()

    # ── 並び替え (矢印ボタン) ─────────────────────────────

    def _selected_rows_sorted(self) -> list[int]:
        """選択中の行インデックスを昇順で返す。"""

        # selectedIndexes() は列ごとに複数返り得るため、行番号だけを集合化して整列する。
        indexes = self._view.selectionModel().selectedIndexes()
        return sorted({idx.row() for idx in indexes})

    def _single_selected_row(self) -> int | None:
        # Ctrl+左右キーは「単一選択専用」なので、1 行以外は明示的に無効化する。
        rows = self._selected_rows_sorted()
        if len(rows) != 1:
            return None
        return rows[0]

    def _select_rows(self, rows: list[int]) -> None:
        # 並び替え後はモデル行が変わるため、選択状態を新行番号で作り直す必要がある。
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
        # 複数行移動の中核ロジック。D&D / ボタン / キーバインドが最終的にここへ集約される。
        if not rows:
            return []

        row_count = self._model.rowCount()
        if row_count == 0:
            return []

        # 重複や順不同があっても安定動作するよう、先に昇順一意化しておく。
        rows = sorted(set(rows))
        insert_row = max(0, min(insert_row, row_count))

        # 選択ブロックの内部へ落とすだけなら見た目が変わらないので no-op 扱いにする。
        if rows[0] <= insert_row <= rows[-1] + 1:
            return rows

        # takeRow() は行を抜くたび後続行が詰まるので、offset で補正しながら取り出す。
        moved_rows: list[list[QStandardItem]] = []
        for offset, row in enumerate(rows):
            taken = self._model.takeRow(row - offset)
            if taken:
                moved_rows.append(taken)

        if not moved_rows:
            return rows

        # 取り出し前の insert_row を、その後の行詰めを考慮した位置へ補正する。
        adjusted_insert = insert_row - sum(1 for row in rows if row < insert_row)
        adjusted_insert = max(0, min(adjusted_insert, self._model.rowCount()))

        new_rows: list[int] = []
        for index, taken in enumerate(moved_rows):
            destination = adjusted_insert + index
            self._model.insertRow(destination, taken)
            new_rows.append(destination)

        # 行位置が変わったので、番号表示を現在順へ同期する。
        self._refresh_item_labels()
        self._update_info_label()
        return new_rows

    def _move_selection_to(self, insert_row: int) -> None:
        # D&D で計算された挿入位置へ、現在選択ブロックを移す。
        rows = self._selected_rows_sorted()
        new_rows = self._move_rows_to(rows, insert_row)
        self._select_rows(new_rows)

    def _move_left(self) -> None:
        """選択中のアイテム群を左 (行番号を減らす方向) に移動する。"""

        # 左端を超える移動はできないので先頭選択時は no-op。
        rows = self._selected_rows_sorted()
        if not rows or rows[0] == 0:
            return
        new_rows = self._move_rows_to(rows, rows[0] - 1)
        self._select_rows(new_rows)

    def _move_right(self) -> None:
        """選択中のアイテム群を右 (行番号を増やす方向) に移動する。"""

        # ブロック全体を 1 つ右へ送るには、末尾のさらに次位置へ挿入する必要がある。
        rows = self._selected_rows_sorted()
        if not rows or rows[-1] >= self._model.rowCount() - 1:
            return
        new_rows = self._move_rows_to(rows, rows[-1] + 2)
        self._select_rows(new_rows)

    def _move_single_selection_left(self) -> None:
        # Ctrl+左は単一選択時だけ有効にする。
        row = self._single_selected_row()
        if row is None:
            return
        photo = self._photo_for_row(row)
        if photo is None:
            return
        new_row = self.move_photo_item_left(photo)
        if new_row is None:
            return
        new_rows = [new_row]
        self._select_rows(new_rows)

    def _move_single_selection_right(self) -> None:
        # Ctrl+右は単一選択時だけ有効にする。
        row = self._single_selected_row()
        if row is None:
            return
        photo = self._photo_for_row(row)
        if photo is None:
            return
        new_row = self.move_photo_item_right(photo)
        if new_row is None:
            return
        new_rows = [new_row]
        self._select_rows(new_rows)

    def move_photo_item_left(self, photo: PhotoItem) -> int | None:
        """指定した PhotoItem を 1 つ前へ移動し、新しい行番号を返す。"""
        row = self._row_for_photo(photo)
        if row is None or row == 0:
            return None
        new_rows = self._move_rows_to([row], row - 1)
        if not new_rows:
            return None
        return new_rows[0]

    def move_photo_item_right(self, photo: PhotoItem) -> int | None:
        """指定した PhotoItem を 1 つ後ろへ移動し、新しい行番号を返す。"""
        row = self._row_for_photo(photo)
        if row is None or row >= self._model.rowCount() - 1:
            return None
        new_rows = self._move_rows_to([row], row + 2)
        if not new_rows:
            return None
        return new_rows[0]

    # ── 追加操作 ──────────────────────────────────────────

    def _add_photos(self) -> None:
        """ファイル選択ダイアログを開き、画像を追加する。"""

        # 追加処理はバックグラウンドスレッドで走るので、同時実行は避ける。
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

        # Step 5 と同じワーカーを再利用し、圧縮パラメータも import 側の現在値に揃える。
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
        # ワーカーからバッチ単位で追加アイテムが届く。到着順を保ってモデルへ挿入する。
        import_page = self._add_import_page
        if import_page is None:
            return

        # 連続挿入中のちらつきを抑えるため、一時的に view 更新を止める。
        self._view.setUpdatesEnabled(False)
        try:
            for item in items:
                pos = self._add_insert_pos + self._add_counter
                self._insert_item(pos, item)
                self._add_counter += 1

            # 新規追加後は表示番号とアイコンを現在の状態へ即同期する。
            self._refresh_item_labels()
            self._refresh_item_icons()
        finally:
            self._view.setUpdatesEnabled(True)

        # 実データ本体も import 側へ反映し、ページ間で同じ写真集合を共有する。
        import_page.add_photo_items(items)
        self._update_info_label()

    def _cancel_add_photos(self) -> None:
        # プログレスダイアログのキャンセルから呼ばれる。
        if self._add_worker is not None:
            self._add_worker.cancel()

    def _on_add_worker_finished(self) -> None:
        # worker 自身の run 完了時には thread を終了方向へ持っていく。
        if self._add_thread is not None:
            self._add_thread.quit()

    def _on_add_thread_finished(self) -> None:
        # スレッド停止後に後始末と失敗通知を行う。
        self._cleanup_add_state()
        self._show_add_failures()

    def _cleanup_add_state(self) -> None:
        # 追加処理専用の一時オブジェクトを安全に破棄する。
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
        # ウィザード終了時などに、裏で動いている追加処理を安全に止めるための入口。
        if self._add_worker is not None:
            self._add_worker.cancel()
        if self._add_thread is not None and self._add_thread.isRunning():
            self._add_thread.quit()
            if not self._add_thread.wait(2000):
                return False
        self._cleanup_add_state()
        return True

    def _record_add_failures(self, failures: list[tuple[str, str]]) -> None:
        # 失敗は都度 UI に出さず、最後にまとめて通知する。
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

        # 削除はユーザーへの確認付きで行う。
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

        # 実体辞書とアイコンキャッシュからも忘れさせておく。
        for photo in items_to_remove:
            self._photo_items_by_key.pop(self._photo_key(photo), None)

        # モデルから逆順に除去
        for row in reversed(rows):
            self._model.removeRow(row)
        for photo in items_to_remove:
            self._icon_cache.pop(self._photo_key(photo), None)
        self._refresh_item_labels()
        self._update_info_label()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Delete キーで選択中のアイテムを削除する。"""

        # ページ自身がキーイベントを受けた場合の保険。通常は QListView 側の
        # keyPressEvent が拾うが、フォーカス位置次第ではこちらへ来ることもある。
        if event.key() == Qt.Key.Key_Delete:
            self._delete_selected()
        elif event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Left:
                self._move_single_selection_left()
                return
            if event.key() == Qt.Key.Key_Right:
                self._move_single_selection_right()
                return
        else:
            super().keyPressEvent(event)

    # ── データ収集 ────────────────────────────────────────

    def collect_photo_items(self) -> list[PhotoItem]:
        """並び順に PhotoItem リストを返す。"""

        # PDF 生成側へ渡す順序は、現在モデルに見えている順そのものに揃える。
        items: list[PhotoItem] = []
        for row in range(self._model.rowCount()):
            photo = self._photo_for_row(row)
            if photo is not None:
                items.append(photo)
        return items

    # ── 情報表示 ──────────────────────────────────────────

    def _update_info_label(self) -> None:
        # 下部の情報ラベルには、総枚数と 3 枚区切りでのページ数を表示する。
        total = self._model.rowCount()
        pages = (total + _PHOTOS_PER_PAGE - 1) // _PHOTOS_PER_PAGE if total else 0
        self._info_label.setText(
            f"写真 {total} 枚 / {pages} ページ "
            f"（1ページあたり {_PHOTOS_PER_PAGE} 枚）"
        )
