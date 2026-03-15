from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QImage, QKeyEvent
from PySide6.QtWidgets import QMessageBox

from work_report_maker.gui.main_window import ReportWizard
from work_report_maker.gui.pages.photo_import_page import PhotoItem
from tests.gui.wizard_stubs import make_photo_item


_make_photo_item = make_photo_item


def _bound_editor_photo_nos(page) -> list[str]:
    return [editor.photo_no_text() for editor in page._editor_widgets if editor.bound_photo() is not None]


def _active_editor_photo_nos(page) -> list[str]:
    return [editor.photo_no_text() for editor in page._editor_widgets if editor.is_active()]


def _show_photo_description_page(wizard: ReportWizard, page, qtbot) -> None:
    wizard.show()
    wizard.setCurrentId(6)
    qtbot.wait(50)


def test_photo_description_page_is_added_after_arrange_page(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    assert wizard.pageIds() == [0, 1, 2, 3, 4, 5, 6]
    assert wizard.page(6) is wizard._photo_description_page


def test_photo_description_page_reflects_arranged_order(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    wizard._photo_import_page.add_photo_items(
        [
            _make_photo_item("a.jpg", site="現場A", work_date="2025年 3月 27日(木)", location="1階厨房"),
            _make_photo_item("b.jpg", site="現場B", work_date="2025年 3月 28日(金)", location="2階厨房"),
            _make_photo_item("c.jpg", site="現場C", work_date="2025年 3月 29日(土)", location="3階厨房"),
        ]
    )
    wizard._photo_arrange_page.initializePage()
    wizard._photo_arrange_page._move_rows_to([2], 0)

    page = wizard._photo_description_page
    page.initializePage()

    assert page.photo_count() == 3
    assert page.current_photo() is wizard._photo_arrange_page.collect_photo_items()[0]
    assert page.current_photo_no() == 1
    assert page.visible_photo_items() == [wizard._photo_arrange_page.collect_photo_items()[0]]
    assert page._editor_widgets[0].photo_no_text() == "1"
    assert page._editor_widgets[0]._site_edit.text() == "現場C"
    assert page._editor_widgets[0]._work_date_edit.date() == QDate(2025, 3, 29)
    assert page._editor_widgets[0]._location_edit.text() == "3階厨房"


def test_photo_description_page_edits_all_visible_fields(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    photo = _make_photo_item(
        "a.jpg",
        site="現場A",
        work_date="2025年 3月 27日(木)",
        location="1階厨房",
        work_content="作業前",
        remarks="初期備考",
    )
    wizard._photo_import_page.add_photo_items([photo])
    wizard._photo_arrange_page.initializePage()

    page = wizard._photo_description_page
    page.initializePage()
    editor = page._editor_widgets[0]

    assert editor._site_edit.text() == "現場A"
    assert editor._work_date_edit.date() == QDate(2025, 3, 27)
    assert editor._location_edit.text() == "1階厨房"
    assert editor._work_content_edit.toPlainText() == "作業前"
    assert editor._remarks_edit.toPlainText() == "初期備考"

    editor._site_edit.setText("現場B")
    editor._work_date_edit.setDate(QDate(2025, 3, 28))
    editor._location_edit.setText("2階厨房")
    editor._work_content_edit.setPlainText("清掃箇所遠景")
    editor._remarks_edit.setPlainText("作業後")

    assert photo.site == "現場B"
    assert photo.work_date == "2025年 3月 28日(金)"
    assert photo.location == "2階厨房"
    assert photo.work_content == "清掃箇所遠景"
    assert photo.remarks == "作業後"


def test_photo_description_page_preserves_current_photo_when_reinitialized(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    photo_a = _make_photo_item("a.jpg")
    photo_b = _make_photo_item("b.jpg")
    photo_c = _make_photo_item("c.jpg")
    wizard._photo_import_page.add_photo_items([photo_a, photo_b, photo_c])
    wizard._photo_arrange_page.initializePage()
    wizard._photo_arrange_page._move_rows_to([2], 0)

    page = wizard._photo_description_page
    page.initializePage()
    page._current_photo_key = id(photo_b)

    wizard._photo_arrange_page._move_rows_to([2], 0)
    page.initializePage()

    assert page.current_photo() is photo_b
    assert page.current_photo_no() == 1
    assert page._editor_widgets[0].photo_no_text() == "1"


def test_photo_description_page_switches_between_1_2_4_view_modes(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    wizard._photo_import_page.add_photo_items(
        [
            _make_photo_item("a.jpg"),
            _make_photo_item("b.jpg"),
            _make_photo_item("c.jpg"),
            _make_photo_item("d.jpg"),
        ]
    )
    wizard._photo_arrange_page.initializePage()

    page = wizard._photo_description_page
    page.initializePage()
    page.set_view_mode(2)

    assert _bound_editor_photo_nos(page) == ["1", "2"]

    page.set_view_mode(4)

    assert _bound_editor_photo_nos(page) == ["1", "2", "3", "4"]


def test_photo_description_page_prev_next_and_page_keys_move_current_anchor(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    wizard._photo_import_page.add_photo_items(
        [
            _make_photo_item("a.jpg"),
            _make_photo_item("b.jpg"),
            _make_photo_item("c.jpg"),
            _make_photo_item("d.jpg"),
        ]
    )
    wizard._photo_arrange_page.initializePage()

    page = wizard._photo_description_page
    page.initializePage()
    page.set_view_mode(2)

    page._show_next_photo()
    assert page.current_photo_no() == 2
    assert _bound_editor_photo_nos(page) == ["2", "3"]

    page._shortcut_next.activated.emit()
    assert page.current_photo_no() == 3
    assert _bound_editor_photo_nos(page) == ["3", "4"]

    page._shortcut_previous.activated.emit()
    assert page.current_photo_no() == 2
    assert _bound_editor_photo_nos(page) == ["2", "3"]


def test_photo_description_page_moves_current_photo_but_keeps_same_anchor_item(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    photo_a = _make_photo_item("a.jpg")
    photo_b = _make_photo_item("b.jpg")
    photo_c = _make_photo_item("c.jpg")
    photo_d = _make_photo_item("d.jpg")
    wizard._photo_import_page.add_photo_items([photo_a, photo_b, photo_c, photo_d])
    wizard._photo_arrange_page.initializePage()

    page = wizard._photo_description_page
    page.initializePage()
    page.set_view_mode(2)
    _show_photo_description_page(wizard, page, qtbot)

    assert page.current_photo() is photo_a
    assert page.current_photo_no() == 1
    assert _active_editor_photo_nos(page) == ["1"]

    page._editor_widgets[1]._site_edit.setFocus()
    qtbot.waitUntil(lambda: page.focused_photo() is photo_b)

    assert page.focused_photo() is photo_b
    assert _active_editor_photo_nos(page) == ["2"]

    page._btn_move_previous.click()

    assert wizard._photo_arrange_page.collect_photo_items() == [photo_b, photo_a, photo_c, photo_d]
    assert page.current_photo() is photo_b
    assert page.current_photo_no() == 1
    assert _bound_editor_photo_nos(page) == ["1", "2"]
    assert _active_editor_photo_nos(page) == ["1"]

    page._btn_move_next.click()

    assert wizard._photo_arrange_page.collect_photo_items() == [photo_a, photo_b, photo_c, photo_d]
    assert page.current_photo() is photo_b
    assert page.current_photo_no() == 2


def test_photo_description_page_focus_switch_updates_highlight_and_move_target(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    wizard._photo_import_page.add_photo_items(
        [
            _make_photo_item("a.jpg"),
            _make_photo_item("b.jpg"),
            _make_photo_item("c.jpg"),
        ]
    )
    wizard._photo_arrange_page.initializePage()

    page = wizard._photo_description_page
    page.initializePage()
    page.set_view_mode(2)
    _show_photo_description_page(wizard, page, qtbot)

    assert _active_editor_photo_nos(page) == ["1"]

    page._editor_widgets[1]._work_content_edit.setFocus()
    qtbot.waitUntil(lambda: page.focused_photo() is wizard._photo_arrange_page.collect_photo_items()[1])

    assert page.focused_photo() is wizard._photo_arrange_page.collect_photo_items()[1]
    assert _active_editor_photo_nos(page) == ["2"]

    page._editor_widgets[0]._location_edit.setFocus()
    qtbot.waitUntil(lambda: page.focused_photo() is wizard._photo_arrange_page.collect_photo_items()[0])

    assert page.focused_photo() is wizard._photo_arrange_page.collect_photo_items()[0]
    assert _active_editor_photo_nos(page) == ["1"]


def test_photo_description_page_reinitialization_resyncs_only_unedited_default_fields(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    wizard._cover_page._building_edit.setText("現場A")
    wizard._cover_page._subtitle_edit.setText("1階厨房")
    wizard._cover_page._start_date.setDate(QDate(2025, 3, 27))

    photo_a = _make_photo_item("a.jpg")
    photo_b = _make_photo_item("b.jpg")
    wizard._photo_import_page.add_photo_items([photo_a, photo_b])
    wizard._photo_arrange_page.initializePage()

    page = wizard._photo_description_page
    page.initializePage()

    photo_a.set_description_field("site", "手入力の現場")
    photo_b.set_description_field("location", "手入力の施工箇所")

    wizard._cover_page._building_edit.setText("現場B")
    wizard._cover_page._subtitle_edit.setText("2階厨房")
    wizard._cover_page._start_date.setDate(QDate(2025, 4, 1))

    page.initializePage()

    assert photo_a.site == "手入力の現場"
    assert photo_a.work_date == "2025年 4月 01日(火)"
    assert photo_a.location == "2階厨房"

    assert photo_b.site == "現場B"
    assert photo_b.work_date == "2025年 4月 01日(火)"
    assert photo_b.location == "手入力の施工箇所"


def test_build_photos_reflects_arranged_order_and_description_values(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    photo_a = _make_photo_item(
        "a.jpg",
        site="現場A",
        work_date="2025年 3月 27日(木)",
        location="1階厨房",
        work_content="清掃前",
        remarks="備考A",
    )
    photo_b = _make_photo_item(
        "b.jpg",
        site="現場B",
        work_date="2025年 3月 28日(金)",
        location="2階厨房",
        work_content="清掃後",
        remarks="備考B",
    )
    wizard._photo_import_page.add_photo_items([photo_a, photo_b])
    wizard._photo_arrange_page.initializePage()
    wizard._photo_arrange_page.move_photo_item_left(photo_b)

    photos = wizard._build_photos()

    assert [item["no"] for item in photos] == [1, 2]
    assert [item["site"] for item in photos] == ["現場B", "現場A"]
    assert [item["work_date"] for item in photos] == ["2025年 3月 28日(金)", "2025年 3月 27日(木)"]
    assert [item["location"] for item in photos] == ["2階厨房", "1階厨房"]
    assert [item["work_content"] for item in photos] == ["清掃後", "清掃前"]
    assert [item["remarks"] for item in photos] == ["備考B", "備考A"]
    assert photos[0]["photo_path"].startswith("file:///")


def test_accept_generates_pdf_with_description_values(qtbot, tmp_path, monkeypatch) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)
    wizard._project_page._name_edit.setText("京都三条ホテル")

    photo = _make_photo_item(
        "a.jpg",
        site="京都三条ホテル",
        work_date="2025年 3月 27日(木)",
        location="1階厨房",
        work_content="グリストラップ清掃",
        remarks="異常なし",
    )
    wizard._photo_import_page.add_photo_items([photo])
    wizard._photo_arrange_page.initializePage()

    output_path = tmp_path / "exported.pdf"
    captured: dict[str, object] = {}
    accepted: list[bool] = []
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "work_report_maker.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(output_path), "PDF (*.pdf)"),
    )

    def _generate(*, report_data=None, json_path=None, output_path=None, optimize_pdf=True) -> None:
        captured["report_data"] = report_data
        captured["json_path"] = json_path
        captured["output_path"] = output_path
        captured["optimize_pdf"] = optimize_pdf

    monkeypatch.setattr("work_report_maker.gui.main_window.generate_full_report", _generate)
    monkeypatch.setattr(
        "work_report_maker.gui.main_window.QWizard.accept",
        lambda self: accepted.append(True),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: messages.append((title, text)),
    )

    wizard.accept()
    payload = captured["report_data"]

    assert len(payload["photos"]) == 1
    assert payload["photos"][0]["site"] == "京都三条ホテル"
    assert payload["photos"][0]["work_date"] == "2025年 3月 27日(木)"
    assert payload["photos"][0]["location"] == "1階厨房"
    assert payload["photos"][0]["work_content"] == "グリストラップ清掃"
    assert payload["photos"][0]["remarks"] == "異常なし"
    assert captured["output_path"] == output_path
    assert captured["optimize_pdf"] is True
    assert accepted == [True]
    assert messages == [("PDF 生成完了", f"PDF を保存しました。\n{output_path}")]


def test_accept_does_not_generate_pdf_when_save_dialog_is_cancelled(qtbot, monkeypatch) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)
    wizard._project_page._name_edit.setText("京都三条ホテル")

    generated: list[bool] = []
    accepted: list[bool] = []

    monkeypatch.setattr(
        "work_report_maker.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )
    monkeypatch.setattr(
        "work_report_maker.gui.main_window.generate_full_report",
        lambda **kwargs: generated.append(True),
    )
    monkeypatch.setattr(
        "work_report_maker.gui.main_window.QWizard.accept",
        lambda self: accepted.append(True),
    )

    wizard.accept()

    assert generated == []
    assert accepted == []