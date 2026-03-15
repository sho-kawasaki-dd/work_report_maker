from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QMessageBox, QWizard

from work_report_maker.gui.main_window import ReportWizard
from work_report_maker.gui.project_store import load_project, project_exists
from work_report_maker.gui.pages.project_name_page import ProjectNamePage
from tests.gui.wizard_stubs import make_photo_item


@pytest.fixture(autouse=True)
def _stub_close_after_generation_setting(monkeypatch) -> None:
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_close_after_pdf_generation",
        lambda: False,
    )


@pytest.fixture(autouse=True)
def _stub_default_message_boxes(monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )


@pytest.fixture
def project_store_root(monkeypatch, tmp_path) -> Path:
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr("work_report_maker.gui.project_store._PROJECTS_DIR", projects_dir)
    return projects_dir


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


def test_reject_delegates_to_close(qtbot, monkeypatch) -> None:
    """Cancel ボタン (reject) は close() に委譲するだけ。"""
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    close_calls: list[bool] = []
    monkeypatch.setattr(wizard, "close", lambda: close_calls.append(True))

    wizard.reject()

    assert close_calls == [True]


def test_close_event_confirmation_yes_closes_with_rejected_result(qtbot, monkeypatch) -> None:
    """確認 Yes → event accepted + result = Rejected。"""
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(wizard, "stop_active_photo_operations", lambda: True)

    result_codes: list[int] = []
    monkeypatch.setattr(wizard, "setResult", lambda code: result_codes.append(code))

    event = QCloseEvent()
    wizard.closeEvent(event)

    assert event.isAccepted() is True
    assert result_codes == [int(QDialog.DialogCode.Rejected)]


def test_close_guard_prevents_reentrant_dialog(qtbot, monkeypatch) -> None:
    """再入ガード: _close_guard が立っている間は確認なしで即 accept。"""
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    wizard._close_guard = True

    questions: list[tuple] = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: (questions.append(args) or QMessageBox.StandardButton.No),
    )

    event = QCloseEvent()
    wizard.closeEvent(event)

    assert event.isAccepted() is True
    assert questions == []


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


def test_project_name_page_loads_default_output_directory(qtbot, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_close_after_pdf_generation",
        lambda: False,
    )
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.load_default_output_dir",
        lambda: tmp_path,
    )

    page = ProjectNamePage()
    qtbot.addWidget(page)

    assert page._output_dir_edit.text() == str(tmp_path)
    assert page._close_after_generation_check.isChecked() is False


def test_project_name_page_browse_updates_and_saves_output_directory(qtbot, monkeypatch, tmp_path) -> None:
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
    qtbot.addWidget(page)
    page._choose_output_directory()

    assert page._output_dir_edit.text() == str(selected_dir)
    assert saved_paths == [selected_dir]


def test_project_name_page_toggle_saves_close_after_generation_preference(qtbot, monkeypatch, tmp_path) -> None:
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
    qtbot.addWidget(page)
    page._close_after_generation_check.setChecked(True)

    assert saved_values == [True]


def test_cover_page_save_button_saves_project_only_on_demand(qtbot, monkeypatch, project_store_root: Path) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)
    wizard._project_page._name_edit.setText("京都三条ホテル")
    wizard._cover_page._title_edit.setText("グリストラップ清掃")

    info_messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: info_messages.append((title, text)),
    )

    wizard.show()
    wizard.next()
    qtbot.waitUntil(lambda: wizard.currentId() == 1)

    save_button = wizard.button(QWizard.WizardButton.CustomButton1)

    assert save_button.isVisible() is True
    assert save_button.isEnabled() is True
    assert save_button.x() < wizard.button(QWizard.WizardButton.BackButton).x()
    assert project_exists("京都三条ホテル") is False

    save_button.click()

    assert project_exists("京都三条ホテル") is True
    assert info_messages[-1][0] == "保存完了"
    loaded = load_project("京都三条ホテル")
    assert loaded["cover_state"]["title"] == "グリストラップ清掃"


def test_project_save_button_remains_visible_after_cover_page(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)
    wizard._project_page._name_edit.setText("京都三条ホテル")

    wizard.show()
    wizard.next()
    qtbot.waitUntil(lambda: wizard.currentId() == 1)

    save_button = wizard.button(QWizard.WizardButton.CustomButton1)
    assert save_button.isVisible() is True

    wizard.next()
    qtbot.waitUntil(lambda: wizard.currentId() == 2)

    assert save_button.isVisible() is True
    assert save_button.isEnabled() is True


def test_project_save_overwrite_removes_deleted_photo_files(qtbot, monkeypatch, project_store_root: Path) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)
    wizard._project_page._name_edit.setText("京都三条ホテル")

    photo_a = make_photo_item("a.jpg")
    photo_b = make_photo_item("b.jpg")
    wizard._photo_import_page.add_photo_items([photo_a, photo_b])
    wizard._photo_arrange_page.initializePage()

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    wizard.save_current_project()
    loaded_once = load_project("京都三条ホテル")
    assert len(loaded_once["photo_items"]) == 2

    wizard._photo_import_page.remove_photo_items([photo_b])
    wizard._photo_arrange_page.reset_items_from_context()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    wizard.save_current_project()

    loaded_twice = load_project("京都三条ホテル")
    assert len(loaded_twice["photo_items"]) == 1
    photos_dir = next(project_store_root.iterdir()) / "photos"
    remaining_files = sorted(path.name for path in photos_dir.iterdir() if path.is_file())
    assert len(remaining_files) == 1


def test_project_name_page_load_restores_state_and_moves_to_cover(qtbot, monkeypatch, project_store_root: Path) -> None:
    source_wizard = ReportWizard()
    qtbot.addWidget(source_wizard)
    source_wizard._project_page._name_edit.setText("京都三条ホテル")
    source_wizard._cover_page._title_edit.setText("グリストラップ清掃")
    source_wizard._cover_page._building_edit.setText("京都三条ホテル")
    source_wizard._overview_page._manager_edit.setText("川崎　潤")
    source_wizard._work_content_page._first_group_lines.setPlainText("作業内容1")
    source_wizard._photo_import_page.add_photo_items([make_photo_item("a.jpg", site="現場A")])
    source_wizard._photo_arrange_page.initializePage()

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    assert source_wizard.save_current_project() is True

    wizard = ReportWizard()
    qtbot.addWidget(wizard)
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.QInputDialog.getItem",
        lambda *args, **kwargs: ("京都三条ホテル", True),
    )

    wizard.show()
    qtbot.waitUntil(lambda: wizard.currentId() == 0)
    wizard._project_page._load_project()
    qtbot.waitUntil(lambda: wizard.currentId() == 1)

    assert wizard._project_page._name_edit.text() == "京都三条ホテル"
    assert wizard._cover_page._title_edit.text() == "グリストラップ清掃"
    assert wizard._cover_page._building_edit.text() == "京都三条ホテル"
    assert wizard._overview_page._manager_edit.text() == "川崎　潤"
    assert wizard._work_content_page._first_group_lines.toPlainText() == "作業内容1"
    assert len(wizard._photo_import_page.photo_items) == 1
    assert wizard._photo_import_page.photo_items[0].site == "現場A"


def test_project_name_page_delete_removes_saved_project_and_clears_current_name(qtbot, monkeypatch, project_store_root: Path) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)
    wizard._project_page._name_edit.setText("京都三条ホテル")

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    assert wizard.save_current_project() is True
    assert project_exists("京都三条ホテル") is True

    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        "work_report_maker.gui.pages.project_name_page.QInputDialog.getItem",
        lambda *args, **kwargs: ("京都三条ホテル", True),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: messages.append((title, text)),
    )

    wizard._project_page._delete_project()

    assert project_exists("京都三条ホテル") is False
    assert wizard._project_page._name_edit.text() == ""
    assert messages[-1][0] == "削除完了"