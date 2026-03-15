from __future__ import annotations

from pathlib import Path
from typing import Callable, TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from work_report_maker.gui.pages.photo_models import PhotoItem
from work_report_maker.services.image_processor import process_image

if TYPE_CHECKING:
    from collections.abc import Iterable


_THUMBNAIL_SIZE = 128
_ITEM_BATCH_SIZE = 8


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


class _ImportWorker(QObject):
    """画像読み込み・圧縮をバックグラウンドで実行するワーカー。

    UI スレッドへ 1 件ずつ signal を返すと QListWidget 再描画と PhotoItem 追加が過剰に発生する。
    そのため、この worker は一定件数をまとめて `items_ready` で返し、進捗だけを細かく通知する。
    """

    progress = Signal(int)
    items_ready = Signal(object)
    failures_ready = Signal(object)
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
        """画像変換を順次実行し、成功分はバッチ単位で UI へ返す。"""

        failures: list[tuple[str, str]] = []
        pending_items: list[PhotoItem] = []
        try:
            for index, path in enumerate(self._paths):
                if self._cancelled:
                    break
                try:
                    data, fmt = process_image(
                        path,
                        dpi=self._dpi,
                        jpeg_quality=self._jpeg_quality,
                        png_quality_max=self._png_quality_max,
                    )
                    pending_items.append(
                        PhotoItem(
                            filename=path.name,
                            data=data,
                            format=fmt,
                            thumbnail=_make_thumbnail(data),
                        )
                    )
                    if len(pending_items) >= _ITEM_BATCH_SIZE:
                        # 8 件ずつ UI へ渡すことで、進捗は滑らかに保ちつつモデル更新の頻度を抑える。
                        self.items_ready.emit(pending_items)
                        pending_items = []
                except Exception as exc:
                    reason = str(exc).strip() or exc.__class__.__name__
                    failures.append((path.name, reason))
                self.progress.emit(index + 1)
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


class PhotoImportOperationController:
    """PhotoImportPage の import 実行状態を管理する。

    page 側は「開始できたか」「停止できたか」「失敗を表示するか」だけを扱い、
    thread / worker / progress dialog のライフサイクル管理はこの controller に閉じ込める。
    """

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._thread: QThread | None = None
        self._worker: _ImportWorker | None = None
        self._progress: QProgressDialog | None = None
        self._failures: list[tuple[str, str]] = []

    @property
    def thread(self) -> QThread | None:
        return self._thread

    @thread.setter
    def thread(self, value: QThread | None) -> None:
        self._thread = value

    @property
    def worker(self) -> _ImportWorker | None:
        return self._worker

    @worker.setter
    def worker(self, value: _ImportWorker | None) -> None:
        self._worker = value

    @property
    def progress(self) -> QProgressDialog | None:
        return self._progress

    @progress.setter
    def progress(self, value: QProgressDialog | None) -> None:
        self._progress = value

    @property
    def failures(self) -> list[tuple[str, str]]:
        return self._failures

    @failures.setter
    def failures(self, value: list[tuple[str, str]]) -> None:
        self._failures = value

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(
        self,
        paths: list[Path],
        *,
        dpi: int,
        jpeg_quality: int,
        png_quality_max: int,
        on_items_ready: Callable[[list[PhotoItem]], None],
    ) -> bool:
        """新しい import ジョブを開始する。既に実行中なら False を返す。"""

        if self.is_running():
            return False

        self._failures.clear()

        worker = _ImportWorker(
            paths,
            dpi=dpi,
            jpeg_quality=jpeg_quality,
            png_quality_max=png_quality_max,
        )
        thread = QThread(self._parent)
        worker.moveToThread(thread)

        progress = QProgressDialog("画像を読み込んでいます...", "キャンセル", 0, len(paths), self._parent)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        self._thread = thread
        self._worker = worker
        self._progress = progress

        worker.progress.connect(progress.setValue, Qt.ConnectionType.QueuedConnection)
        worker.items_ready.connect(on_items_ready, Qt.ConnectionType.QueuedConnection)
        worker.failures_ready.connect(self.record_failures, Qt.ConnectionType.QueuedConnection)
        progress.canceled.connect(self.request_cancel)

        worker.finished.connect(self.handle_worker_finished, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(self.handle_thread_finished, Qt.ConnectionType.QueuedConnection)
        thread.started.connect(worker.run, Qt.ConnectionType.QueuedConnection)
        thread.start()
        return True

    def request_cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def handle_worker_finished(self) -> None:
        if self._thread is not None:
            self._thread.quit()

    def handle_thread_finished(self) -> None:
        # worker 完了時点では dialog/worker/thread がまだ生きているため、UI 後始末と
        # 失敗通知は thread 終了シグナル側でまとめて行う。
        self.cleanup()
        self.show_failures()

    def cleanup(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress.deleteLater()
            self._progress = None

        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def cancel_active(self) -> bool:
        """実行中ジョブの停止を試み、完全停止できたかを返す。"""

        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(2000):
                return False
        self.cleanup()
        return True

    def record_failures(self, failures: list[tuple[str, str]]) -> None:
        self._failures.extend(failures)

    def show_failures(self) -> None:
        if not self._failures:
            return

        message = _format_failure_message(self._failures)
        self._failures.clear()
        QMessageBox.warning(self._parent, "画像読み込みエラー", message)