from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import QProgressDialog, QWidget

from work_report_maker.services.pdf_generator import generate_full_report


class _PDFGenerationWorker(QObject):
    succeeded = Signal()
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        report_data: dict[str, Any],
        output_path: Path,
        *,
        optimize_pdf: bool = True,
    ) -> None:
        super().__init__()
        self._report_data = report_data
        self._output_path = output_path
        self._optimize_pdf = optimize_pdf
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        if self._cancel_requested:
            self.cancelled.emit()
            return

        try:
            generate_full_report(
                report_data=self._report_data,
                output_path=self._output_path,
                optimize_pdf=self._optimize_pdf,
            )
        except Exception as exc:
            if self._cancel_requested:
                self._remove_output_if_exists()
                self.cancelled.emit()
                return
            message = str(exc).strip() or exc.__class__.__name__
            self.failed.emit(message)
            return

        if self._cancel_requested:
            self._remove_output_if_exists()
            self.cancelled.emit()
            return

        self.succeeded.emit()

    def _remove_output_if_exists(self) -> None:
        try:
            if self._output_path.exists():
                self._output_path.unlink()
        except OSError:
            # 中断後に生成物が残ると成功と誤認されやすいため削除を試みるが、削除失敗は
            # 元の編集状態保持より優先度が低いので例外にはしない。
            pass


class PDFGenerationController:
    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._thread: QThread | None = None
        self._worker: _PDFGenerationWorker | None = None
        self._progress: QProgressDialog | None = None
        self._cancel_requested = False
        self._outcome: tuple[str, str | None] | None = None
        self._on_success: Callable[[], None] | None = None
        self._on_error: Callable[[str], None] | None = None
        self._on_cancelled: Callable[[], None] | None = None

    @property
    def progress(self) -> QProgressDialog | None:
        return self._progress

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(
        self,
        *,
        report_data: dict[str, Any],
        output_path: Path,
        on_success: Callable[[], None],
        on_error: Callable[[str], None],
        on_cancelled: Callable[[], None],
        optimize_pdf: bool = True,
    ) -> bool:
        if self.is_running():
            return False

        self._cancel_requested = False
        self._outcome = None
        self._on_success = on_success
        self._on_error = on_error
        self._on_cancelled = on_cancelled

        worker = _PDFGenerationWorker(
            report_data=report_data,
            output_path=output_path,
            optimize_pdf=optimize_pdf,
        )
        thread = QThread(self._parent)
        worker.moveToThread(thread)

        progress = QProgressDialog("報告書PDFを生成中です...", "中断", 0, 0, self._parent)
        progress.setWindowTitle("PDF 生成中")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)

        self._thread = thread
        self._worker = worker
        self._progress = progress

        progress.canceled.connect(self.request_cancel)
        worker.succeeded.connect(self._record_success, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._record_error, Qt.ConnectionType.QueuedConnection)
        worker.cancelled.connect(self._record_cancelled, Qt.ConnectionType.QueuedConnection)
        worker.succeeded.connect(self._quit_thread, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._quit_thread, Qt.ConnectionType.QueuedConnection)
        worker.cancelled.connect(self._quit_thread, Qt.ConnectionType.QueuedConnection)
        thread.started.connect(worker.run, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(self._handle_thread_finished, Qt.ConnectionType.QueuedConnection)
        thread.start()
        return True

    def request_cancel(self) -> None:
        if self._worker is None or self._cancel_requested:
            return

        self._cancel_requested = True
        if self._progress is not None:
            self._progress.setLabelText("報告書PDFの中断を待っています...")
        self._worker.request_cancel()

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

    def _record_success(self) -> None:
        self._outcome = ("success", None)

    def _record_error(self, message: str) -> None:
        self._outcome = ("error", message)

    def _record_cancelled(self) -> None:
        self._outcome = ("cancelled", None)

    def _quit_thread(self, *_args: object) -> None:
        if self._thread is not None:
            self._thread.quit()

    def _handle_thread_finished(self) -> None:
        outcome = self._outcome
        on_success = self._on_success
        on_error = self._on_error
        on_cancelled = self._on_cancelled

        self.cleanup()
        self._outcome = None
        self._on_success = None
        self._on_error = None
        self._on_cancelled = None

        if outcome is None:
            return
        if outcome[0] == "success":
            if on_success is not None:
                on_success()
            return
        if outcome[0] == "error":
            if on_error is not None:
                on_error(outcome[1] or "Unknown error")
            return
        if on_cancelled is not None:
            on_cancelled()