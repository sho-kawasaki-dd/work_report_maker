from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.gui.wizard_stubs import create_import_wizard, make_photo_item

from work_report_maker.gui.pages.photo_import_page import PhotoDescriptionDefaults, PhotoImportPage, PhotoItem


class _FakeWorker:
    def __init__(self) -> None:
        self.cancel_called = False
        self.deleted = False

    def cancel(self) -> None:
        self.cancel_called = True

    def deleteLater(self) -> None:
        self.deleted = True


class _FakeThread:
    def __init__(self, *, wait_result: bool = True) -> None:
        self.quit_called = False
        self.wait_called_with: int | None = None
        self.deleted = False
        self._wait_result = wait_result

    def isRunning(self) -> bool:
        return True

    def quit(self) -> None:
        self.quit_called = True

    def wait(self, timeout: int) -> bool:
        self.wait_called_with = timeout
        return self._wait_result

    def deleteLater(self) -> None:
        self.deleted = True


class _FakeProgress:
    def __init__(self) -> None:
        self.closed = False
        self.deleted = False

    def close(self) -> None:
        self.closed = True

    def deleteLater(self) -> None:
        self.deleted = True


def test_add_photo_items_updates_list_and_applies_current_defaults(qtbot) -> None:
    wizard, page = create_import_wizard(
        qtbot=qtbot,
        defaults=PhotoDescriptionDefaults(
            site="現場A",
            work_date="2025年 3月 27日(木)",
            location="1階厨房",
        ),
    )

    photo_a = make_photo_item("a.jpg")
    photo_b = make_photo_item("b.jpg")
    page.add_photo_items([photo_a, photo_b])

    assert [item.filename for item in page.photo_items] == ["a.jpg", "b.jpg"]
    assert page._list_widget.count() == 2
    assert page._count_label.text() == "2 枚の画像を読み込みました"
    assert photo_a.site == "現場A"
    assert photo_a.work_date == "2025年 3月 27日(木)"
    assert photo_a.location == "1階厨房"


def test_remove_photo_items_rebuilds_internal_state_and_list(qtbot) -> None:
    page = PhotoImportPage()
    qtbot.addWidget(page)

    photo_a = make_photo_item("a.jpg")
    photo_b = make_photo_item("b.jpg")
    photo_c = make_photo_item("c.jpg")
    page.add_photo_items([photo_a, photo_b, photo_c])

    page.remove_photo_items([photo_b])

    assert [item.filename for item in page.photo_items] == ["a.jpg", "c.jpg"]
    assert page._list_widget.count() == 2
    assert page._count_label.text() == "2 枚の画像を読み込みました"
    assert page.isComplete() is True


def test_cancel_active_import_cleans_up_progress_worker_and_thread(qtbot) -> None:
    page = PhotoImportPage()
    qtbot.addWidget(page)

    worker = _FakeWorker()
    thread = _FakeThread()
    progress = _FakeProgress()
    page._import_worker = worker
    page._import_thread = thread
    page._import_progress = progress

    stopped = page.cancel_active_import()

    assert stopped is True
    assert worker.cancel_called is True
    assert thread.quit_called is True
    assert thread.wait_called_with == 2000
    assert progress.closed is True
    assert progress.deleted is True
    assert worker.deleted is True
    assert thread.deleted is True
    assert page._import_progress is None
    assert page._import_worker is None
    assert page._import_thread is None