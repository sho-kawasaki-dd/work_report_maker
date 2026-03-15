"""ウィザード Step 5: 画像インポートページ。

フォルダ一括読み込み / ファイル選択 / ZIP 対応の画像インポート機能と、
圧縮設定 (DPI / JPEG品質 / PNG品質) の UI を提供する。

読み込んだ画像は image_processor.process_image() で圧縮し、
PhotoItem データクラスとしてメモリ上に保持する。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWizardPage,
)

from work_report_maker.gui.pages.photo_import_controls import PhotoImportCompressionControls
from work_report_maker.gui.pages.photo_import_operation import (
    PhotoImportOperationController,
    _format_failure_message,
    _ImportWorker,
)
from work_report_maker.gui.pages.photo_models import PhotoDescriptionDefaults, PhotoItem
from work_report_maker.services.image_processor import collect_image_paths, is_pngquant_available

if TYPE_CHECKING:
    from work_report_maker.gui.main_window import ReportWizard

class _PhotoImportListController:
    """PhotoItem 一覧と QListWidget の同期を扱う。

    PhotoImportPage 本体からは「写真集合の更新」と「完了状態通知」を切り離し、
    list widget 再構築や件数表示の更新はこの controller に集約する。
    """

    def __init__(
        self,
        *,
        list_widget: QListWidget,
        count_label: QLabel,
        defaults_getter,
        notify_complete_changed,
    ) -> None:
        self._list_widget = list_widget
        self._count_label = count_label
        self._defaults_getter = defaults_getter
        self._notify_complete_changed = notify_complete_changed
        self._photo_items: list[PhotoItem] = []

    @property
    def photo_items(self) -> list[PhotoItem]:
        return self._photo_items

    def sync_photo_item_defaults(self) -> None:
        """保持済み PhotoItem に最新の既定値を再同期する。"""

        # Cover page に戻って現場名や施工箇所が変わった場合でも、未編集フィールドだけは
        # 既定値へ追従させる。上書き判定そのものは PhotoItem 側へ委譲する。
        defaults = self._defaults_getter()
        for item in self._photo_items:
            item.sync_description_defaults(defaults)

    def add_items(self, items: list[PhotoItem]) -> None:
        """PhotoItem 群を内部状態と一覧へ追加する。"""

        defaults = self._defaults_getter()
        for item in items:
            # import 時点で既定値を注入しておくことで、Description page は「すでに意味づけ済みの
            # PhotoItem 群」を前提に編集 UI を組み立てられる。
            item.sync_description_defaults(defaults)
        self._photo_items.extend(items)
        self._append_list_items(items)
        self._update_count_label()
        self._notify_complete_changed()

    def remove_items(self, items: list[PhotoItem]) -> None:
        removed = False
        for item in items:
            if item in self._photo_items:
                self._photo_items.remove(item)
                removed = True

        if removed:
            self.rebuild_list()

    def rebuild_list(self) -> None:
        """内部状態を正として一覧全体を描き直す。"""

        self._list_widget.clear()
        self._append_list_items(self._photo_items)
        self._update_count_label()
        self._notify_complete_changed()

    def clear_all(self) -> None:
        self._photo_items.clear()
        self._list_widget.clear()
        self._update_count_label()
        self._notify_complete_changed()

    def _append_list_items(self, items: list[PhotoItem]) -> None:
        self._list_widget.setUpdatesEnabled(False)
        try:
            for item in items:
                list_item = QListWidgetItem(item.filename)
                if item.thumbnail is not None and not item.thumbnail.isNull():
                    list_item.setIcon(QIcon(QPixmap.fromImage(item.thumbnail)))
                self._list_widget.addItem(list_item)
        finally:
            self._list_widget.setUpdatesEnabled(True)

    def _update_count_label(self) -> None:
        count = len(self._photo_items)
        self._count_label.setText(f"{count} 枚の画像を読み込みました")


# ── メインページ ──────────────────────────────────────────


class PhotoImportPage(QWizardPage):
    """画像インポートウィザードページ。

    UI 構成:
        - 読み込みボタン群 (フォルダ読込 / ファイル選択)
        - 圧縮設定グループ (DPI / JPEG品質 / PNG品質)
        - 読み込み済みリスト (QListWidget)
        - クリアボタン
        - アスペクト比に関する注意書き

    この page は「画像ファイルを PhotoItem 集合へ変換する入口」であり、並び替えや説明編集は
    後続ページへ委譲する。ここで確定するのは、圧縮設定と PhotoItem の初期既定値だけである。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("写真インポート")
        self.setSubTitle("報告書に含める写真を読み込んでください。")

        self._import_operation = PhotoImportOperationController(self)

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
        self._compression_controls = PhotoImportCompressionControls(
            pngquant_available=is_pngquant_available()
        )
        self._dpi_slider = self._compression_controls.dpi_slider
        self._dpi_spin = self._compression_controls.dpi_spin
        self._jpeg_slider = self._compression_controls.jpeg_slider
        self._jpeg_spin = self._compression_controls.jpeg_spin
        self._png_slider = self._compression_controls.png_slider
        self._png_spin = self._compression_controls.png_spin
        self._png_label = self._compression_controls.png_label
        self._default_import_settings = self.import_settings_state()

        # ── 読み込み済みリスト ──
        self._list_widget = QListWidget()
        self._count_label = QLabel("0 枚の画像を読み込みました")
        self._list_controller = _PhotoImportListController(
            list_widget=self._list_widget,
            count_label=self._count_label,
            defaults_getter=self.current_photo_description_defaults,
            notify_complete_changed=self.completeChanged.emit,
        )
        self._photo_items = self._list_controller.photo_items

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
        main_layout.addWidget(self._compression_controls.group_box)
        main_layout.addWidget(notice)
        main_layout.addWidget(self._list_widget, 1)
        main_layout.addLayout(clear_row)
        self.setLayout(main_layout)

    # ── 公開アクセサ ──────────────────────────────────────

    @property
    def photo_items(self) -> list[PhotoItem]:
        return self._list_controller.photo_items

    @property
    def _import_thread(self):
        return self._import_operation.thread

    @_import_thread.setter
    def _import_thread(self, value) -> None:
        self._import_operation.thread = value

    @property
    def _import_worker(self):
        return self._import_operation.worker

    @_import_worker.setter
    def _import_worker(self, value) -> None:
        self._import_operation.worker = value

    @property
    def _import_progress(self):
        return self._import_operation.progress

    @_import_progress.setter
    def _import_progress(self, value) -> None:
        self._import_operation.progress = value

    @property
    def _import_failures(self):
        return self._import_operation.failures

    @_import_failures.setter
    def _import_failures(self, value) -> None:
        self._import_operation.failures = value

    def dpi(self) -> int:
        return self._compression_controls.dpi()

    def jpeg_quality(self) -> int:
        return self._compression_controls.jpeg_quality()

    def png_quality_max(self) -> int:
        return self._compression_controls.png_quality_max()

    def current_photo_description_defaults(self) -> PhotoDescriptionDefaults:
        """現在のウィザード状態から写真説明の既定値を取得する。"""

        # full ReportWizard では `photo_description_defaults()` が source of truth になる。
        # 軽量 wizard fixture ではその API が無いこともあるため、空 defaults へ穏当に退避する。
        wizard = self.wizard()
        defaults_getter = getattr(wizard, "photo_description_defaults", None)
        if callable(defaults_getter):
            defaults = defaults_getter()
            if isinstance(defaults, PhotoDescriptionDefaults):
                return defaults
        return PhotoDescriptionDefaults()

    def import_settings_state(self) -> dict:
        return {
            "dpi": self.dpi(),
            "jpeg_quality": self.jpeg_quality(),
            "png_quality_max": self.png_quality_max(),
        }

    def apply_import_settings_state(self, state: dict) -> None:
        self._dpi_spin.setValue(int(state.get("dpi", self._default_import_settings["dpi"])))
        self._jpeg_spin.setValue(int(state.get("jpeg_quality", self._default_import_settings["jpeg_quality"])))
        self._png_spin.setValue(int(state.get("png_quality_max", self._default_import_settings["png_quality_max"])))

    def replace_photo_items(self, items: list[PhotoItem]) -> None:
        self._list_controller.clear_all()
        self._add_photo_items(items)

    def clear_project_state(self) -> None:
        self.apply_import_settings_state(self._default_import_settings)
        self._list_controller.clear_all()

    def sync_photo_item_defaults(self) -> None:
        """保持中の PhotoItem に最新の既定値を同期する。"""
        self._list_controller.sync_photo_item_defaults()

    # ── バリデーション ────────────────────────────────────

    def isComplete(self) -> bool:
        return len(self.photo_items) > 0

    def initializePage(self) -> None:
        """前ページから戻った際に一覧表示を内部状態へ同期する。"""
        # QListWidget 自体は view 状態に過ぎないため、戻り操作のたびに内部状態から再描画して
        # 見た目を正規化する。
        self._list_controller.rebuild_list()

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
        # page 側はジョブ起動条件と現在 UI 設定の受け渡しだけを担い、thread / worker / dialog の
        # ライフサイクルは PhotoImportOperationController へ委譲する。
        self._import_operation.start(
            paths,
            dpi=self.dpi(),
            jpeg_quality=self.jpeg_quality(),
            png_quality_max=self.png_quality_max(),
            on_items_ready=self._add_photo_items,
        )

    def _cancel_import(self) -> None:
        self._import_operation.request_cancel()

    def _on_import_worker_finished(self) -> None:
        self._import_operation.handle_worker_finished()

    def _on_import_thread_finished(self) -> None:
        self._import_operation.handle_thread_finished()

    def _cleanup_import_state(self) -> None:
        self._import_operation.cleanup()

    def cancel_active_import(self) -> bool:
        return self._import_operation.cancel_active()

    def _record_import_failures(self, failures: list[tuple[str, str]]) -> None:
        self._import_operation.record_failures(failures)

    def _show_import_failures(self) -> None:
        self._import_operation.show_failures()

    def add_photo_items(self, items: list[PhotoItem]) -> None:
        """外部ページからの追加も含め、一覧と内部状態をまとめて更新する。"""
        self._add_photo_items(items)

    def remove_photo_items(self, items: list[PhotoItem]) -> None:
        """指定した PhotoItem 群を内部状態と一覧から取り除く。"""
        self._list_controller.remove_items(items)

    def _add_photo_items(self, items: list[PhotoItem]) -> None:
        """PhotoItem 群をまとめてリストへ追加し、UI 更新回数を抑える。"""
        self._list_controller.add_items(items)

    def _append_list_items(self, items: list[PhotoItem]) -> None:
        self._list_controller._append_list_items(items)

    def _rebuild_photo_list(self) -> None:
        self._list_controller.rebuild_list()

    def _clear_all(self) -> None:
        """読み込み済み画像をすべてクリアする。"""
        # Clear は page 内 state のみを対象にし、ファイルシステム上の入力元や一時展開済み ZIP を
        # 巻き戻すものではない。
        self._list_controller.clear_all()

    def _update_count_label(self) -> None:
        self._list_controller._update_count_label()
