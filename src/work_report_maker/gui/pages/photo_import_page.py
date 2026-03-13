"""ウィザード Step 5: 画像インポートページ。

フォルダ一括読み込み / ファイル選択 / ZIP 対応の画像インポート機能と、
圧縮設定 (DPI / JPEG品質 / PNG品質) の UI を提供する。

読み込んだ画像は image_processor.process_image() で圧縮し、
PhotoItem データクラスとしてメモリ上に保持する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWizardPage,
)

from work_report_maker.services.image_processor import (
    collect_image_paths,
    is_pngquant_available,
    process_image,
)

if TYPE_CHECKING:
    from work_report_maker.gui.main_window import ReportWizard

# サムネイルの一辺サイズ (px)
_THUMBNAIL_SIZE = 128
_ITEM_BATCH_SIZE = 8
_SYNCED_DESCRIPTION_FIELDS = ("site", "work_date", "location")


@dataclass(frozen=True)
class PhotoDescriptionDefaults:
    """写真説明欄へ注入する既定値セット。"""

    site: str = ""
    work_date: str = ""
    location: str = ""


@dataclass
class PhotoItem:
    """圧縮済み画像データを保持するデータクラス。"""

    filename: str
    data: bytes  # 圧縮済みバイト列
    format: str  # "jpeg" or "png"
    thumbnail: QImage | None = None  # サムネイル用 (ワーカースレッドで生成可能)
    site: str = ""
    work_date: str = ""
    location: str = ""
    work_content: str = ""
    remarks: str = ""
    _default_description_values: dict[str, str] = field(default_factory=dict, repr=False)
    _user_edited_description_fields: set[str] = field(default_factory=set, repr=False)

    def apply_initial_description_defaults(self, defaults: PhotoDescriptionDefaults) -> None:
        """取り込み直後の既定値を注入する。"""
        self.sync_description_defaults(defaults, force=True)

    def sync_description_defaults(
        self,
        defaults: PhotoDescriptionDefaults,
        *,
        force: bool = False,
    ) -> None:
        """未編集項目にだけ既定値を反映し、最新の既定値スナップショットを保持する。"""
        for field_name, value in {
            "site": defaults.site,
            "work_date": defaults.work_date,
            "location": defaults.location,
        }.items():
            current_value = getattr(self, field_name)
            previous_default = self._default_description_values.get(field_name, "")
            should_update = force or (
                field_name not in self._user_edited_description_fields
                and (current_value == "" or current_value == previous_default)
            )
            if should_update:
                setattr(self, field_name, value)
            self._default_description_values[field_name] = value

    def set_description_field(self, field_name: str, value: str) -> None:
        """説明項目を更新し、ユーザー編集済みとして扱う。"""
        if field_name not in {"site", "work_date", "location", "work_content", "remarks"}:
            raise ValueError(f"Unsupported description field: {field_name}")
        setattr(self, field_name, value)
        self._user_edited_description_fields.add(field_name)

    def is_description_field_user_edited(self, field_name: str) -> bool:
        """指定した説明項目がユーザー編集済みかどうかを返す。"""
        return field_name in self._user_edited_description_fields


def _make_thumbnail(data: bytes, size: int = _THUMBNAIL_SIZE) -> QImage:
    """圧縮済みバイト列からサムネイル QImage を生成する。"""
    img = QImage()
    img.loadFromData(data)
    if img.isNull():
        return QImage()
    return img.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# ── QThread ワーカー ──────────────────────────────────────


class _ImportWorker(QObject):
    """画像読み込み・圧縮をバックグラウンドで実行するワーカー。"""

    progress = Signal(int)  # 処理済み件数
    items_ready = Signal(object)  # list[PhotoItem]
    failures_ready = Signal(object)  # list[tuple[str, str]]
    finished = Signal()
    error = Signal(str)

    def __init__(
        self,
        paths: list[Path],
        dpi: int,
        jpeg_quality: int,
        png_quality_max: int,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._dpi = dpi
        self._jpeg_quality = jpeg_quality
        self._png_quality_max = png_quality_max
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        failures: list[tuple[str, str]] = []
        pending_items: list[PhotoItem] = []
        try:
            for i, path in enumerate(self._paths):
                if self._cancelled:
                    break
                try:
                    data, fmt = process_image(
                        path,
                        dpi=self._dpi,
                        jpeg_quality=self._jpeg_quality,
                        png_quality_max=self._png_quality_max,
                    )
                    item = PhotoItem(
                        filename=path.name,
                        data=data,
                        format=fmt,
                        thumbnail=_make_thumbnail(data),
                    )
                    pending_items.append(item)
                    if len(pending_items) >= _ITEM_BATCH_SIZE:
                        self.items_ready.emit(pending_items)
                        pending_items = []
                except Exception as exc:
                    # 個別の画像が読み込めなくても他の画像は継続
                    reason = str(exc).strip() or exc.__class__.__name__
                    failures.append((path.name, reason))
                self.progress.emit(i + 1)
        finally:
            if pending_items:
                self.items_ready.emit(pending_items)
            if failures:
                self.failures_ready.emit(failures)
            self.finished.emit()


def _format_failure_message(failures: list[tuple[str, str]]) -> str:
    """失敗したファイル一覧をユーザー向けの短いメッセージに整形する。"""
    preview = failures[:3]
    lines = [f"{len(failures)} 件の画像を読み込めませんでした。"]
    for filename, reason in preview:
        lines.append(f"- {filename}: {reason}")
    remaining = len(failures) - len(preview)
    if remaining > 0:
        lines.append(f"...ほか {remaining} 件")
    return "\n".join(lines)


# ── メインページ ──────────────────────────────────────────


class PhotoImportPage(QWizardPage):
    """画像インポートウィザードページ。

    UI 構成:
        - 読み込みボタン群 (フォルダ読込 / ファイル選択)
        - 圧縮設定グループ (DPI / JPEG品質 / PNG品質)
        - 読み込み済みリスト (QListWidget)
        - クリアボタン
        - アスペクト比に関する注意書き
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("写真インポート")
        self.setSubTitle("報告書に含める写真を読み込んでください。")

        self._photo_items: list[PhotoItem] = []
        self._import_thread: QThread | None = None
        self._import_worker: _ImportWorker | None = None
        self._import_progress: QProgressDialog | None = None
        self._import_failures: list[tuple[str, str]] = []

        # ── 読み込みボタン群 ──
        btn_folder = QPushButton("フォルダ読込")
        btn_folder.clicked.connect(self._import_folder)
        btn_files = QPushButton("ファイル選択")
        btn_files.clicked.connect(self._import_files)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_folder)
        btn_layout.addWidget(btn_files)
        btn_layout.addStretch()

        # ── 圧縮設定グループ ──
        self._dpi_slider = QSlider(Qt.Orientation.Horizontal)
        self._dpi_slider.setRange(72, 300)
        self._dpi_slider.setValue(150)
        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 300)
        self._dpi_spin.setValue(150)
        self._dpi_slider.valueChanged.connect(self._dpi_spin.setValue)
        self._dpi_spin.valueChanged.connect(self._dpi_slider.setValue)

        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("DPI:"))
        dpi_row.addWidget(self._dpi_slider, 1)
        dpi_row.addWidget(self._dpi_spin)

        self._jpeg_slider = QSlider(Qt.Orientation.Horizontal)
        self._jpeg_slider.setRange(10, 100)
        self._jpeg_slider.setValue(75)
        self._jpeg_spin = QSpinBox()
        self._jpeg_spin.setRange(10, 100)
        self._jpeg_spin.setValue(75)
        self._jpeg_slider.valueChanged.connect(self._jpeg_spin.setValue)
        self._jpeg_spin.valueChanged.connect(self._jpeg_slider.setValue)

        jpeg_row = QHBoxLayout()
        jpeg_row.addWidget(QLabel("JPEG品質:"))
        jpeg_row.addWidget(self._jpeg_slider, 1)
        jpeg_row.addWidget(self._jpeg_spin)

        self._png_slider = QSlider(Qt.Orientation.Horizontal)
        self._png_slider.setRange(10, 100)
        self._png_slider.setValue(75)
        self._png_spin = QSpinBox()
        self._png_spin.setRange(10, 100)
        self._png_spin.setValue(75)
        self._png_slider.valueChanged.connect(self._png_spin.setValue)
        self._png_spin.valueChanged.connect(self._png_slider.setValue)

        self._png_label = QLabel("PNG品質:")
        if not is_pngquant_available():
            self._png_slider.setEnabled(False)
            self._png_spin.setEnabled(False)
            self._png_label.setText("PNG品質 (Pillow減色):")

        png_row = QHBoxLayout()
        png_row.addWidget(self._png_label)
        png_row.addWidget(self._png_slider, 1)
        png_row.addWidget(self._png_spin)

        compress_layout = QVBoxLayout()
        compress_layout.addLayout(dpi_row)
        compress_layout.addLayout(jpeg_row)
        compress_layout.addLayout(png_row)

        compress_group = QGroupBox("圧縮設定")
        compress_group.setLayout(compress_layout)

        # ── 読み込み済みリスト ──
        self._list_widget = QListWidget()
        self._count_label = QLabel("0 枚の画像を読み込みました")

        # ── クリアボタン ──
        btn_clear = QPushButton("すべてクリア")
        btn_clear.clicked.connect(self._clear_all)

        clear_row = QHBoxLayout()
        clear_row.addWidget(self._count_label, 1)
        clear_row.addWidget(btn_clear)

        # ── 注意書き ──
        notice = QLabel(
            "※ アスペクト比が 4:3 でない画像は中央を基準にクロップされます。\n"
            "　 画像の端が途切れる可能性があります。"
        )
        notice.setStyleSheet("color: #666; font-size: 11px;")

        # ── レイアウト組立 ──
        main_layout = QVBoxLayout()
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(compress_group)
        main_layout.addWidget(notice)
        main_layout.addWidget(self._list_widget, 1)
        main_layout.addLayout(clear_row)
        self.setLayout(main_layout)

    # ── 公開アクセサ ──────────────────────────────────────

    @property
    def photo_items(self) -> list[PhotoItem]:
        return self._photo_items

    def dpi(self) -> int:
        return self._dpi_spin.value()

    def jpeg_quality(self) -> int:
        return self._jpeg_spin.value()

    def png_quality_max(self) -> int:
        return self._png_spin.value()

    def current_photo_description_defaults(self) -> PhotoDescriptionDefaults:
        """現在のウィザード状態から写真説明の既定値を取得する。"""
        wizard = self.wizard()
        defaults_getter = getattr(wizard, "photo_description_defaults", None)
        if callable(defaults_getter):
            defaults = defaults_getter()
            if isinstance(defaults, PhotoDescriptionDefaults):
                return defaults
        return PhotoDescriptionDefaults()

    def sync_photo_item_defaults(self) -> None:
        """保持中の PhotoItem に最新の既定値を同期する。"""
        defaults = self.current_photo_description_defaults()
        for item in self._photo_items:
            item.sync_description_defaults(defaults)

    # ── バリデーション ────────────────────────────────────

    def isComplete(self) -> bool:
        return len(self._photo_items) > 0

    def initializePage(self) -> None:
        """前ページから戻った際に一覧表示を内部状態へ同期する。"""
        self._rebuild_photo_list()

    # ── 読み込み操作 ──────────────────────────────────────

    def _import_folder(self) -> None:
        """フォルダ選択ダイアログを開き、フォルダ内の画像を一括読み込み。"""
        folder = QFileDialog.getExistingDirectory(self, "画像フォルダを選択")
        if not folder:
            return
        paths = collect_image_paths(Path(folder))
        if paths:
            self._run_import(paths)

    def _import_files(self) -> None:
        """ファイル選択ダイアログを開き、選択された画像を読み込み。"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "画像ファイルを選択",
            "",
            "画像/ZIP (*.jpg *.jpeg *.png *.zip)",
        )
        if not files:
            return
        all_paths: list[Path] = []
        for f in files:
            all_paths.extend(collect_image_paths(Path(f)))
        if all_paths:
            self._run_import(all_paths)

    def _run_import(self, paths: list[Path]) -> None:
        """画像読み込み・圧縮をワーカースレッドで実行する。"""
        if self._import_thread is not None and self._import_thread.isRunning():
            return

        self._import_failures.clear()

        total = len(paths)
        worker = _ImportWorker(
            paths,
            dpi=self._dpi_spin.value(),
            jpeg_quality=self._jpeg_spin.value(),
            png_quality_max=self._png_spin.value(),
        )

        thread = QThread(self)
        worker.moveToThread(thread)

        # モーダルプログレスダイアログ
        progress = QProgressDialog("画像を読み込んでいます...", "キャンセル", 0, total, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        self._import_thread = thread
        self._import_worker = worker
        self._import_progress = progress

        # シグナル接続
        worker.progress.connect(progress.setValue, Qt.ConnectionType.QueuedConnection)
        worker.items_ready.connect(self._add_photo_items, Qt.ConnectionType.QueuedConnection)
        worker.failures_ready.connect(self._record_import_failures, Qt.ConnectionType.QueuedConnection)
        progress.canceled.connect(self._cancel_import)

        worker.finished.connect(self._on_import_worker_finished, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(self._on_import_thread_finished, Qt.ConnectionType.QueuedConnection)
        thread.started.connect(worker.run, Qt.ConnectionType.QueuedConnection)
        thread.start()

    def _cancel_import(self) -> None:
        if self._import_worker is not None:
            self._import_worker.cancel()

    def _on_import_worker_finished(self) -> None:
        if self._import_thread is not None:
            self._import_thread.quit()

    def _on_import_thread_finished(self) -> None:
        self._cleanup_import_state()
        self._show_import_failures()

    def _cleanup_import_state(self) -> None:
        if self._import_progress is not None:
            self._import_progress.close()
            self._import_progress.deleteLater()
            self._import_progress = None

        if self._import_worker is not None:
            self._import_worker.deleteLater()
            self._import_worker = None

        if self._import_thread is not None:
            self._import_thread.deleteLater()
            self._import_thread = None

    def cancel_active_import(self) -> bool:
        if self._import_worker is not None:
            self._import_worker.cancel()
        if self._import_thread is not None and self._import_thread.isRunning():
            self._import_thread.quit()
            if not self._import_thread.wait(2000):
                return False
        self._cleanup_import_state()
        return True

    def _record_import_failures(self, failures: list[tuple[str, str]]) -> None:
        self._import_failures.extend(failures)

    def _show_import_failures(self) -> None:
        if not self._import_failures:
            return

        message = _format_failure_message(self._import_failures)
        self._import_failures.clear()
        QMessageBox.warning(self, "画像読み込みエラー", message)

    def add_photo_items(self, items: list[PhotoItem]) -> None:
        """外部ページからの追加も含め、一覧と内部状態をまとめて更新する。"""
        self._add_photo_items(items)

    def remove_photo_items(self, items: list[PhotoItem]) -> None:
        """指定した PhotoItem 群を内部状態と一覧から取り除く。"""
        removed = False
        for item in items:
            if item in self._photo_items:
                self._photo_items.remove(item)
                removed = True

        if removed:
            self._rebuild_photo_list()

    def _add_photo_items(self, items: list[PhotoItem]) -> None:
        """PhotoItem 群をまとめてリストへ追加し、UI 更新回数を抑える。"""
        defaults = self.current_photo_description_defaults()
        for item in items:
            item.sync_description_defaults(defaults)
        self._photo_items.extend(items)
        self._append_list_items(items)
        self._update_count_label()
        self.completeChanged.emit()

    def _append_list_items(self, items: list[PhotoItem]) -> None:
        from PySide6.QtGui import QIcon

        self._list_widget.setUpdatesEnabled(False)
        try:
            for item in items:
                list_item = QListWidgetItem(item.filename)
                if item.thumbnail is not None and not item.thumbnail.isNull():
                    list_item.setIcon(QIcon(QPixmap.fromImage(item.thumbnail)))
                self._list_widget.addItem(list_item)
        finally:
            self._list_widget.setUpdatesEnabled(True)

    def _rebuild_photo_list(self) -> None:
        self._list_widget.clear()
        self._append_list_items(self._photo_items)
        self._update_count_label()
        self.completeChanged.emit()

    def _clear_all(self) -> None:
        """読み込み済み画像をすべてクリアする。"""
        self._photo_items.clear()
        self._list_widget.clear()
        self._update_count_label()
        self.completeChanged.emit()

    def _update_count_label(self) -> None:
        count = len(self._photo_items)
        self._count_label.setText(f"{count} 枚の画像を読み込みました")
