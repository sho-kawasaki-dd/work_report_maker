from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox

from work_report_maker.gui.main_window import ReportWizard


def test_overview_and_work_content_follow_cover_accessors(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    wizard._cover_page._building_edit.setText("京都三条ホテル")
    wizard._cover_page._subtitle_edit.setText("1階厨房")
    wizard._cover_page._title_edit.setText("グリストラップ清掃")

    wizard._overview_page.initializePage()
    wizard._work_content_page.initializePage()

    assert wizard._overview_page._lbl_target.text() == "京都三条ホテル"
    assert wizard._overview_page._lbl_location.text() == "1階厨房"
    assert wizard._overview_page._lbl_content.text() == "グリストラップ清掃"
    assert wizard._work_content_page._first_group_title_label.text() == "グリストラップ清掃"


def test_close_event_ignores_when_photo_operations_are_still_stopping(qtbot, monkeypatch) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    monkeypatch.setattr(wizard, "stop_active_photo_operations", lambda: False)

    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: messages.append((title, text)),
    )

    event = QCloseEvent()
    wizard.closeEvent(event)

    assert event.isAccepted() is False
    assert messages == [
        (
            "画像処理を停止中",
            "画像の読み込み処理を停止しています。数秒待ってから再度閉じてください。",
        )
    ]