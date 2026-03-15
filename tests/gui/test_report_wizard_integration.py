from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox, QWizard

from work_report_maker.gui.main_window import ReportWizard
from work_report_maker.gui.pages.project_name_page import ProjectNamePage


@pytest.fixture(autouse=True)
def _stub_close_after_generation_setting(monkeypatch) -> None:
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_close_after_pdf_generation",
        lambda: False,
    )


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


def test_back_button_is_hidden_on_first_page_and_visible_after_next(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)
    wizard._project_page._name_edit.setText("京都三条ホテル")
    wizard.show()
    try:
        qtbot.waitUntil(lambda: wizard.currentId() == 0)

        back_button = wizard.button(QWizard.WizardButton.BackButton)
        next_button = wizard.button(QWizard.WizardButton.NextButton)

        assert back_button.isVisible() is False
        assert back_button.text() == "Back"

        wizard.next()
        qtbot.waitUntil(lambda: wizard.currentId() == 1)

        assert back_button.isVisible() is True
        assert back_button.isEnabled() is True
        assert back_button.x() < next_button.x()
    finally:
        wizard.hide()


def test_reject_cancel_shows_confirmation_and_stays_open_on_no(qtbot, monkeypatch) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    questions: list[tuple[str, str]] = []
    rejected: list[bool] = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda parent, title, text, buttons, default: (
            questions.append((title, text))
            or QMessageBox.StandardButton.No
        ),
    )
    monkeypatch.setattr(QWizard, "reject", lambda self: rejected.append(True))

    wizard.reject()

    assert questions == [("終了確認", "プロジェクトを破棄してアプリを終了しますか？")]
    assert rejected == []


def test_reject_cancel_confirms_and_calls_base_reject_on_yes(qtbot, monkeypatch) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(wizard, "stop_active_photo_operations", lambda: True)

    rejected: list[bool] = []
    monkeypatch.setattr(QWizard, "reject", lambda self: rejected.append(True))

    wizard.reject()

    assert rejected == [True]


def test_close_event_confirmation_no_keeps_window_open(qtbot, monkeypatch) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    questions: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda parent, title, text, buttons, default: (
            questions.append((title, text))
            or QMessageBox.StandardButton.No
        ),
    )

    event = QCloseEvent()
    wizard.closeEvent(event)

    assert event.isAccepted() is False
    assert questions == [("終了確認", "プロジェクトを破棄してアプリを終了しますか？")]


def test_close_event_ignores_when_photo_operations_are_still_stopping(qtbot, monkeypatch) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
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


def test_close_event_ignores_while_pdf_generation_is_running(qtbot, monkeypatch) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(wizard._pdf_generation_controller, "is_running", lambda: True)

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
            "PDF 生成中",
            "報告書PDFを生成しています。中断または完了後に閉じてください。",
        )
    ]


def test_project_name_page_loads_default_output_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_close_after_pdf_generation",
        lambda: False,
    )
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_default_output_dir",
        lambda: tmp_path,
    )

    page = ProjectNamePage()

    assert page._output_dir_edit.text() == str(tmp_path)
    assert page._close_after_generation_check.isChecked() is False


def test_project_name_page_browse_updates_and_saves_output_directory(monkeypatch, tmp_path) -> None:
    selected_dir = tmp_path / "exports"
    selected_dir.mkdir()
    saved_paths: list[Path] = []

    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_close_after_pdf_generation",
        lambda: False,
    )
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_default_output_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(selected_dir),
    )

    def _save(path: str | Path) -> Path:
        resolved = Path(path)
        saved_paths.append(resolved)
        return resolved

    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.save_default_output_dir",
        _save,
    )

    page = ProjectNamePage()
    page._choose_output_directory()

    assert page._output_dir_edit.text() == str(selected_dir)
    assert saved_paths == [selected_dir]


def test_project_name_page_toggle_saves_close_after_generation_preference(monkeypatch, tmp_path) -> None:
    saved_values: list[bool] = []

    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_close_after_pdf_generation",
        lambda: False,
    )
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_default_output_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.save_close_after_pdf_generation",
        lambda value: saved_values.append(value),
    )

    page = ProjectNamePage()
    page._close_after_generation_check.setChecked(True)

    assert saved_values == [True]