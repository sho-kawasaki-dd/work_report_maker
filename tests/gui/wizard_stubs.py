from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWizard

from work_report_maker.gui.pages.photo_arrange_page import PhotoArrangePage
from work_report_maker.gui.pages.photo_import_page import PhotoDescriptionDefaults, PhotoImportPage, PhotoItem


def make_photo_item(
    name: str,
    *,
    site: str = "",
    work_date: str = "",
    location: str = "",
    work_content: str = "",
    remarks: str = "",
) -> PhotoItem:
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
        site=site,
        work_date=work_date,
        location=location,
        work_content=work_content,
        remarks=remarks,
    )


def create_import_wizard(
    *,
    qtbot=None,
    defaults: PhotoDescriptionDefaults | None = None,
) -> tuple[QWizard, PhotoImportPage]:
    wizard = QWizard()
    page = PhotoImportPage()
    if defaults is not None:
        wizard.photo_description_defaults = lambda: defaults
    wizard.addPage(page)
    if qtbot is not None:
        qtbot.addWidget(wizard)
    return wizard, page


def create_arrange_wizard(
    photo_names: list[str],
    *,
    qtbot,
) -> tuple[QWizard, PhotoImportPage, PhotoArrangePage]:
    wizard, import_page = create_import_wizard(qtbot=qtbot)
    import_page.add_photo_items([make_photo_item(name) for name in photo_names])
    arrange_page = PhotoArrangePage()

    wizard._photo_import_page = import_page
    wizard.addPage(arrange_page)
    arrange_page.initializePage()
    return wizard, import_page, arrange_page