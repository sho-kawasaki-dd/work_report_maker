from __future__ import annotations

import os
import pickle

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QMessageBox, QWizard

from work_report_maker.gui.pages.photo_arrange_page import PhotoArrangePage
from work_report_maker.gui.pages.photo_import_page import PhotoImportPage, PhotoItem


def _make_photo_item(name: str) -> PhotoItem:
    image = QImage(24, 24, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    return PhotoItem(
        filename=name,
        data=name.encode("utf-8"),
        format="jpeg",
        thumbnail=image,
    )


def _photo_names(page: PhotoArrangePage) -> list[str]:
    return [photo.filename for photo in page.collect_photo_items()]


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