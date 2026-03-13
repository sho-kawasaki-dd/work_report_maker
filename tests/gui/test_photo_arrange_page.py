from __future__ import annotations

import os
import pickle

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QDate, QIODevice, QSize, Qt
from PySide6.QtGui import QImage, QKeyEvent
from PySide6.QtWidgets import QMessageBox, QWizard

from work_report_maker.gui.main_window import ReportWizard
from work_report_maker.gui.pages.photo_arrange_page import PhotoArrangePage
from work_report_maker.gui.pages.photo_import_page import PhotoDescriptionDefaults, PhotoImportPage, PhotoItem


def _make_photo_item(name: str) -> PhotoItem:
    image = QImage(240, 180, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return PhotoItem(
        filename=name,
        data=bytes(encoded),
        format="png",
        thumbnail=image.scaled(
            128,
            128,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ),
    )


def _photo_names(page: PhotoArrangePage) -> list[str]:
    return [photo.filename for photo in page.collect_photo_items()]


def _item_labels(page: PhotoArrangePage) -> list[str]:
    return [page._model.item(row).text() for row in range(page._model.rowCount())]


def _create_page(photo_names: list[str], qtbot) -> tuple[QWizard, PhotoImportPage, PhotoArrangePage]:
    wizard = QWizard()
    import_page = PhotoImportPage()
    import_page.add_photo_items([_make_photo_item(name) for name in photo_names])
    arrange_page = PhotoArrangePage()

    wizard._photo_import_page = import_page
    wizard.addPage(import_page)
    wizard.addPage(arrange_page)
    qtbot.addWidget(wizard)

    arrange_page.initializePage()
    return wizard, import_page, arrange_page


def test_model_user_role_stores_picklable_key(qtbot) -> None:
    wizard, _, arrange_page = _create_page(["a.jpg", "b.jpg"], qtbot)

    stored_value = arrange_page._model.item(0).data(Qt.ItemDataRole.UserRole)

    assert isinstance(stored_value, int)
    assert pickle.loads(pickle.dumps(stored_value)) == stored_value


def test_move_selection_to_treats_non_contiguous_selection_as_block(qtbot) -> None:
    wizard, _, arrange_page = _create_page(
        ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"],
        qtbot,
    )

    arrange_page._select_rows([1, 3])
    arrange_page._move_selection_to(arrange_page._model.rowCount())

    assert _photo_names(arrange_page) == [
        "a.jpg",
        "c.jpg",
        "e.jpg",
        "b.jpg",
        "d.jpg",
    ]
    assert arrange_page._selected_rows_sorted() == [3, 4]


def test_initialize_page_preserves_arranged_order_and_appends_new_items(qtbot) -> None:
    wizard, import_page, arrange_page = _create_page(["a.jpg", "b.jpg", "c.jpg"], qtbot)

    arrange_page._move_rows_to([2], 0)
    import_page.add_photo_items([_make_photo_item("d.jpg")])

    arrange_page.initializePage()

    assert _photo_names(arrange_page) == ["c.jpg", "a.jpg", "b.jpg", "d.jpg"]


def test_delete_selected_removes_items_from_import_page_and_arrange_page(qtbot, monkeypatch) -> None:
    wizard, import_page, arrange_page = _create_page(
        ["a.jpg", "b.jpg", "c.jpg", "d.jpg"],
        qtbot,
    )

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    arrange_page._select_rows([1, 2])
    arrange_page._delete_selected()

    assert _photo_names(arrange_page) == ["a.jpg", "d.jpg"]
    assert [photo.filename for photo in import_page.photo_items] == ["a.jpg", "d.jpg"]


def test_ctrl_right_moves_only_single_selected_item(qtbot) -> None:
    wizard, _, arrange_page = _create_page(["a.jpg", "b.jpg", "c.jpg"], qtbot)

    arrange_page._select_rows([1])
    arrange_page._view.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Right,
            Qt.KeyboardModifier.ControlModifier,
        )
    )

    assert _photo_names(arrange_page) == ["a.jpg", "c.jpg", "b.jpg"]
    assert arrange_page._selected_rows_sorted() == [2]


def test_ctrl_left_and_right_do_nothing_for_multi_selection_or_edges(qtbot) -> None:
    wizard, _, arrange_page = _create_page(["a.jpg", "b.jpg", "c.jpg"], qtbot)

    arrange_page._select_rows([0, 1])
    arrange_page._view.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Right,
            Qt.KeyboardModifier.ControlModifier,
        )
    )
    assert _photo_names(arrange_page) == ["a.jpg", "b.jpg", "c.jpg"]

    arrange_page._select_rows([0])
    arrange_page._view.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Left,
            Qt.KeyboardModifier.ControlModifier,
        )
    )
    assert _photo_names(arrange_page) == ["a.jpg", "b.jpg", "c.jpg"]

    arrange_page._select_rows([2])
    arrange_page._view.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Right,
            Qt.KeyboardModifier.ControlModifier,
        )
    )
    assert _photo_names(arrange_page) == ["a.jpg", "b.jpg", "c.jpg"]


def test_item_labels_track_current_order_after_rearrange(qtbot) -> None:
    wizard, _, arrange_page = _create_page(["a.jpg", "b.jpg", "c.jpg"], qtbot)

    assert _item_labels(arrange_page) == ["1", "2", "3"]

    arrange_page._move_rows_to([2], 0)

    assert _photo_names(arrange_page) == ["c.jpg", "a.jpg", "b.jpg"]
    assert _item_labels(arrange_page) == ["1", "2", "3"]


def test_zoom_slider_uses_percentage_range(qtbot) -> None:
    wizard, _, arrange_page = _create_page(["a.jpg"], qtbot)

    arrange_page._zoom_slider.setValue(50)
    assert arrange_page._view.iconSize() == QSize(64, 64)
    assert arrange_page._view.gridSize() == QSize(104, 104)

    arrange_page._zoom_slider.setValue(200)
    assert arrange_page._view.iconSize() == QSize(256, 256)
    assert arrange_page._view.gridSize() == QSize(296, 296)
    assert arrange_page._zoom_label.text() == "サムネイルサイズ: 200%"


def test_zoom_slider_snaps_to_25_percent_steps(qtbot) -> None:
    wizard, _, arrange_page = _create_page(["a.jpg"], qtbot)

    arrange_page._zoom_slider.setValue(63)

    assert arrange_page._zoom_slider.value() == 75
    assert arrange_page._view.iconSize() == QSize(96, 96)
    assert arrange_page._view.gridSize() == QSize(136, 136)
    assert arrange_page._zoom_label.text() == "サムネイルサイズ: 75%"


def test_zoom_slider_rescales_item_icon_pixels(qtbot) -> None:
    wizard, _, arrange_page = _create_page(["a.jpg"], qtbot)

    initial_icon = arrange_page._model.item(0).icon().pixmap(arrange_page._view.iconSize())
    assert initial_icon.size() == QSize(128, 96)

    arrange_page._zoom_slider.setValue(200)

    zoomed_icon = arrange_page._model.item(0).icon().pixmap(arrange_page._view.iconSize())
    assert zoomed_icon.size() == QSize(256, 192)


def test_icon_cache_tracks_only_current_zoom_size(qtbot) -> None:
    wizard, _, arrange_page = _create_page(["a.jpg", "b.jpg"], qtbot)

    assert arrange_page._icon_cache_size == 128
    assert len(arrange_page._icon_cache) == 2

    arrange_page._zoom_slider.setValue(150)

    assert arrange_page._zoom_slider.value() == 150
    assert arrange_page._icon_cache_size == 192
    assert len(arrange_page._icon_cache) == 2


def test_photo_item_syncs_unedited_default_fields_only() -> None:
    item = _make_photo_item("a.jpg")
    item.apply_initial_description_defaults(
        PhotoDescriptionDefaults(site="現場A", work_date="2025年 3月 27日(木)", location="1階厨房")
    )

    assert item.site == "現場A"
    assert item.work_date == "2025年 3月 27日(木)"
    assert item.location == "1階厨房"

    item.set_description_field("site", "手入力の現場")
    item.sync_description_defaults(
        PhotoDescriptionDefaults(site="現場B", work_date="2025年 4月 01日(火)", location="2階厨房")
    )

    assert item.site == "手入力の現場"
    assert item.work_date == "2025年 4月 01日(火)"
    assert item.location == "2階厨房"
    assert item.is_description_field_user_edited("site") is True
    assert item.is_description_field_user_edited("work_date") is False


def test_import_page_applies_wizard_photo_description_defaults(qtbot) -> None:
    wizard = QWizard()
    import_page = PhotoImportPage()
    wizard.addPage(import_page)
    wizard.photo_description_defaults = lambda: PhotoDescriptionDefaults(
        site="現場A",
        work_date="2025年 3月 27日(木)",
        location="1階厨房",
    )
    qtbot.addWidget(wizard)

    item = _make_photo_item("a.jpg")
    import_page.add_photo_items([item])

    assert item.site == "現場A"
    assert item.work_date == "2025年 3月 27日(木)"
    assert item.location == "1階厨房"


def test_report_wizard_photo_description_defaults_reflect_current_form_values(qtbot) -> None:
    wizard = ReportWizard()
    qtbot.addWidget(wizard)

    wizard._cover_page._building_edit.setText("京都三条ホテル")
    wizard._cover_page._subtitle_edit.setText("1階厨房")
    wizard._cover_page._start_date.setDate(QDate(2025, 3, 27))

    defaults = wizard.photo_description_defaults()

    assert defaults.site == "京都三条ホテル"
    assert defaults.work_date == "2025年 3月 27日(木)"
    assert defaults.location == "1階厨房"