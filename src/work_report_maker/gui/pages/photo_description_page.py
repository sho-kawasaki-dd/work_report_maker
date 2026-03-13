"""ウィザード Step 7: 写真説明ページ。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QDate, QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QGridLayout,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QWidget,
    QVBoxLayout,
    QWizardPage,
)

from work_report_maker.gui.pages.photo_import_page import PhotoItem

if TYPE_CHECKING:
    from work_report_maker.gui.main_window import ReportWizard


_WORK_DATE_PATTERN = re.compile(r"^(?P<year>\d{4})年\s*(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日(?:\([^)]*\))?$")
_WEEKDAY_MAP: dict[int, str] = {
    1: "月",
    2: "火",
    3: "水",
    4: "木",
    5: "金",
    6: "土",
    7: "日",
}


def _parse_work_date(value: str) -> QDate | None:
    match = _WORK_DATE_PATTERN.match(value.strip())
    if match is None:
        return None
    date = QDate(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
    )
    return date if date.isValid() else None


def _format_work_date(date: QDate) -> str:
    weekday = _WEEKDAY_MAP.get(date.dayOfWeek(), "")
    return f"{date.year()}年 {date.month()}月 {date.day():02d}日({weekday})"


class _PhotoDescriptionEditor(QGroupBox):
    """単一写真の説明入力を担当する編集ブロック。"""

    focus_received = Signal(object)

    _DEFAULT_STYLE = (
        "QGroupBox {"
        " background-color: #ffffff;"
        " border: 1px solid #c9d5e0;"
        " border-radius: 6px;"
        " margin-top: 12px;"
        " padding: 10px 8px 8px 8px;"
        "}"
        "QGroupBox::title {"
        " subcontrol-origin: margin;"
        " left: 10px;"
        " padding: 0 4px;"
        "}"
    )
    _ACTIVE_STYLE = (
        "QGroupBox {"
        " background-color: #eef6ff;"
        " border: 1px solid #8fb8f2;"
        " border-radius: 6px;"
        " margin-top: 12px;"
        " padding: 10px 8px 8px 8px;"
        "}"
        "QGroupBox::title {"
        " subcontrol-origin: margin;"
        " left: 10px;"
        " padding: 0 4px;"
        "}"
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._photo: PhotoItem | None = None
        self._active = False

        self._thumbnail_label = QLabel()
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setMinimumSize(220, 165)
        self._thumbnail_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._thumbnail_label.setFrameShape(QFrame.Shape.StyledPanel)
        self._thumbnail_label.setText("写真がありません")

        self._photo_no_label = QLabel("-")
        self._photo_no_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._site_edit = QLineEdit()
        self._work_date_edit = QDateEdit(QDate.currentDate())
        self._work_date_edit.setCalendarPopup(True)
        self._work_date_edit.setDisplayFormat("yyyy/MM/dd")
        self._location_edit = QLineEdit()
        self._work_content_edit = QTextEdit()
        self._work_content_edit.setPlaceholderText("施工内容を入力")
        self._work_content_edit.setAcceptRichText(False)
        self._remarks_edit = QTextEdit()
        self._remarks_edit.setPlaceholderText("備考を入力")
        self._remarks_edit.setAcceptRichText(False)
        self._focus_widgets = [
            self,
            self._site_edit,
            self._work_date_edit,
            self._location_edit,
            self._work_content_edit,
            self._remarks_edit,
        ]
        date_line_edit = self._work_date_edit.lineEdit()
        if date_line_edit is not None:
            self._focus_widgets.append(date_line_edit)
        for widget in self._focus_widgets:
            widget.installEventFilter(self)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(self._DEFAULT_STYLE)

        self._site_edit.textChanged.connect(self._on_site_changed)
        self._work_date_edit.dateChanged.connect(self._on_work_date_changed)
        self._location_edit.textChanged.connect(self._on_location_changed)
        self._work_content_edit.textChanged.connect(self._on_work_content_changed)
        self._remarks_edit.textChanged.connect(self._on_remarks_changed)

        form = QFormLayout()
        form.addRow("写真No", self._photo_no_label)
        form.addRow("現場", self._site_edit)
        form.addRow("施工日", self._work_date_edit)
        form.addRow("施工箇所", self._location_edit)
        form.addRow("施工内容", self._work_content_edit)
        form.addRow("備考", self._remarks_edit)

        layout = QVBoxLayout()
        layout.addWidget(self._thumbnail_label)
        layout.addLayout(form)
        self.setLayout(layout)

        self.clear()

    def bind_photo(self, photo: PhotoItem, photo_no: int) -> None:
        self._photo = photo
        self.setTitle(f"写真 {photo_no}")
        self._photo_no_label.setText(str(photo_no))
        self._set_line_edit_text(self._site_edit, photo.site)
        self._set_date_edit_value(self._work_date_edit, photo.work_date)
        self._set_line_edit_text(self._location_edit, photo.location)
        self._set_text_edit_text(self._work_content_edit, photo.work_content)
        self._set_text_edit_text(self._remarks_edit, photo.remarks)
        self._update_thumbnail()
        self.show()

    def clear(self) -> None:
        self._photo = None
        self.setTitle("写真")
        self._photo_no_label.setText("-")
        self._set_line_edit_text(self._site_edit, "")
        self._set_date_edit_value(self._work_date_edit, "")
        self._set_line_edit_text(self._location_edit, "")
        self._set_text_edit_text(self._work_content_edit, "")
        self._set_text_edit_text(self._remarks_edit, "")
        self._thumbnail_label.setPixmap(QPixmap())
        self._thumbnail_label.setText("写真がありません")
        self.set_active(False)
        self.hide()

    def photo_no_text(self) -> str:
        return self._photo_no_label.text()

    def bound_photo(self) -> PhotoItem | None:
        return self._photo

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setStyleSheet(self._ACTIVE_STYLE if active else self._DEFAULT_STYLE)

    def is_active(self) -> bool:
        return self._active

    def focus_primary_field(self) -> None:
        self._site_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FocusIn and watched in self._focus_widgets and self._photo is not None:
            self.focus_received.emit(self)
        return super().eventFilter(watched, event)

    def _set_line_edit_text(self, edit: QLineEdit, value: str) -> None:
        edit.blockSignals(True)
        edit.setText(value)
        edit.blockSignals(False)

    def _set_date_edit_value(self, edit: QDateEdit, value: str) -> None:
        edit.blockSignals(True)
        parsed = _parse_work_date(value)
        edit.setDate(parsed or QDate.currentDate())
        edit.blockSignals(False)

    def _set_text_edit_text(self, edit: QTextEdit, value: str) -> None:
        edit.blockSignals(True)
        edit.setPlainText(value)
        edit.blockSignals(False)

    def _on_site_changed(self, value: str) -> None:
        if self._photo is not None:
            self._photo.set_description_field("site", value)

    def _on_work_date_changed(self, value: QDate) -> None:
        if self._photo is not None:
            self._photo.set_description_field("work_date", _format_work_date(value))

    def _on_location_changed(self, value: str) -> None:
        if self._photo is not None:
            self._photo.set_description_field("location", value)

    def _on_work_content_changed(self) -> None:
        if self._photo is not None:
            self._photo.set_description_field("work_content", self._work_content_edit.toPlainText())

    def _on_remarks_changed(self) -> None:
        if self._photo is not None:
            self._photo.set_description_field("remarks", self._remarks_edit.toPlainText())

    def _update_thumbnail(self) -> None:
        if self._photo is None:
            self._thumbnail_label.setPixmap(QPixmap())
            self._thumbnail_label.setText("写真がありません")
            return

        pixmap = QPixmap()
        pixmap.loadFromData(self._photo.data)
        if pixmap.isNull() and self._photo.thumbnail is not None and not self._photo.thumbnail.isNull():
            pixmap = QPixmap.fromImage(self._photo.thumbnail)

        if pixmap.isNull():
            self._thumbnail_label.setPixmap(QPixmap())
            self._thumbnail_label.setText("プレビューを読み込めません")
            return

        scaled = pixmap.scaled(
            self._thumbnail_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail_label.setText("")
        self._thumbnail_label.setPixmap(scaled)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._photo is not None:
            self._update_thumbnail()


class PhotoDescriptionPage(QWizardPage):
    """PhotoArrangePage の現在順を確認し、説明項目を編集するページ。"""

    _SUPPORTED_VIEW_MODES = (1, 2, 4)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("写真説明")
        self.setSubTitle("並び順を確認しながら、写真ごとの説明を入力します。")

        self._photo_items: list[PhotoItem] = []
        self._current_photo_key: int | None = None
        self._focused_photo_key: int | None = None
        self._view_mode = 1

        self._position_label = QLabel("現在位置: 0 / 0")
        self._position_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._btn_previous = QPushButton("前の写真")
        self._btn_previous.clicked.connect(self._show_previous_photo)
        self._btn_next = QPushButton("次の写真")
        self._btn_next.clicked.connect(self._show_next_photo)
        self._btn_move_previous = QPushButton("写真を一つ前に移動")
        self._btn_move_previous.clicked.connect(self._move_current_photo_left)
        self._btn_move_next = QPushButton("写真を一つ後ろに移動")
        self._btn_move_next.clicked.connect(self._move_current_photo_right)

        self._view_mode_group = QButtonGroup(self)
        self._view_mode_group.setExclusive(True)
        self._mode_buttons: dict[int, QPushButton] = {}
        for mode in self._SUPPORTED_VIEW_MODES:
            button = QPushButton(f"{mode}枚表示")
            button.setCheckable(True)
            button.clicked.connect(lambda checked, current_mode=mode: self.set_view_mode(current_mode))
            self._view_mode_group.addButton(button, mode)
            self._mode_buttons[mode] = button
        self._mode_buttons[self._view_mode].setChecked(True)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self._btn_previous)
        controls_layout.addWidget(self._btn_next)
        controls_layout.addSpacing(16)
        controls_layout.addWidget(self._btn_move_previous)
        controls_layout.addWidget(self._btn_move_next)
        controls_layout.addSpacing(16)
        for mode in self._SUPPORTED_VIEW_MODES:
            controls_layout.addWidget(self._mode_buttons[mode])
        controls_layout.addStretch()

        self._editors_container = QWidget()
        self._editors_layout = QGridLayout()
        self._editors_layout.setContentsMargins(0, 0, 0, 0)
        self._editors_layout.setHorizontalSpacing(12)
        self._editors_layout.setVerticalSpacing(12)
        self._editors_container.setLayout(self._editors_layout)
        self._editor_widgets = [_PhotoDescriptionEditor(self._editors_container) for _ in range(4)]
        for editor in self._editor_widgets:
            editor.focus_received.connect(self._on_editor_focus_received)
            self._editors_layout.addWidget(editor)

        self._shortcut_previous = QShortcut(QKeySequence(Qt.Key.Key_PageUp), self)
        self._shortcut_previous.activated.connect(self._show_previous_photo)
        self._shortcut_next = QShortcut(QKeySequence(Qt.Key.Key_PageDown), self)
        self._shortcut_next.activated.connect(self._show_next_photo)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self._position_label)
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self._editors_container, 1)
        self.setLayout(main_layout)

    def _wizard(self) -> ReportWizard:
        from work_report_maker.gui.main_window import ReportWizard

        return cast(ReportWizard, self.wizard())

    def initializePage(self) -> None:
        """PhotoArrangePage の現在順を取り込み、表示対象を同期する。"""
        self._wizard()._photo_import_page.sync_photo_item_defaults()
        arranged_items = self._wizard()._photo_arrange_page.collect_photo_items()
        previous_key = self._current_photo_key
        self._photo_items = list(arranged_items)

        if not self._photo_items:
            self._current_photo_key = None
            self._focused_photo_key = None
            self._refresh_display()
            return

        if previous_key is not None:
            for item in self._photo_items:
                if self._photo_key(item) == previous_key:
                    self._current_photo_key = previous_key
                    self._refresh_display()
                    return

        self._current_photo_key = self._photo_key(self._photo_items[0])
        self._refresh_display()

    def current_photo(self) -> PhotoItem | None:
        """現在表示中の PhotoItem を返す。"""
        if self._current_photo_key is None:
            return None
        for item in self._photo_items:
            if self._photo_key(item) == self._current_photo_key:
                return item
        return None

    def current_photo_no(self) -> int | None:
        """現在表示中の写真 No を返す。"""
        current = self.current_photo()
        if current is None:
            return None
        for index, item in enumerate(self._photo_items, start=1):
            if item is current:
                return index
        return None

    def photo_count(self) -> int:
        """現在の写真件数を返す。"""
        return len(self._photo_items)

    def visible_photo_items(self) -> list[PhotoItem]:
        """現在の表示モードで見えている PhotoItem 群を返す。"""
        current = self.current_photo()
        if current is None:
            return []
        start_index = self._photo_items.index(current)
        end_index = min(start_index + self._view_mode, len(self._photo_items))
        return self._photo_items[start_index:end_index]

    def set_view_mode(self, mode: int) -> None:
        """表示モードを 1, 2, 4 枚表示に切り替える。"""
        if mode not in self._SUPPORTED_VIEW_MODES:
            raise ValueError(f"Unsupported view mode: {mode}")
        self._view_mode = mode
        self._mode_buttons[mode].setChecked(True)
        self._refresh_display()

    def _photo_key(self, photo: PhotoItem) -> int:
        return id(photo)

    def focused_photo(self) -> PhotoItem | None:
        if self._focused_photo_key is None:
            return None
        for item in self._photo_items:
            if self._photo_key(item) == self._focused_photo_key:
                return item
        return None

    def _find_editor_for_photo_key(self, photo_key: int | None) -> _PhotoDescriptionEditor | None:
        if photo_key is None:
            return None
        for editor in self._editor_widgets:
            photo = editor.bound_photo()
            if photo is not None and self._photo_key(photo) == photo_key:
                return editor
        return None

    def _sync_focused_photo(self) -> None:
        focused = self.focused_photo()
        if focused is None or focused not in self.visible_photo_items():
            current = self.current_photo()
            self._focused_photo_key = self._photo_key(current) if current is not None else None

        for editor in self._editor_widgets:
            photo = editor.bound_photo()
            is_active = photo is not None and self._focused_photo_key == self._photo_key(photo)
            editor.set_active(is_active)

    def _on_editor_focus_received(self, editor: _PhotoDescriptionEditor) -> None:
        photo = editor.bound_photo()
        if photo is None:
            return
        self._focused_photo_key = self._photo_key(photo)
        self._sync_focused_photo()
        self._update_navigation_buttons(self.current_photo_no() - 1 if self.current_photo_no() else None, len(self._photo_items))

    def _refresh_display(self) -> None:
        current = self.current_photo()
        total = len(self._photo_items)
        current_no = self.current_photo_no()

        if current is None or current_no is None:
            self._position_label.setText(f"現在位置: 0 / {total}")
            for editor in self._editor_widgets:
                editor.clear()
            self._relayout_visible_editors(0)
            self._update_navigation_buttons(None, total)
            return

        visible_items = self.visible_photo_items()
        self._position_label.setText(f"現在位置: {current_no} / {total}")
        for index, editor in enumerate(self._editor_widgets):
            if index < len(visible_items):
                photo = visible_items[index]
                photo_no = self._photo_items.index(photo) + 1
                editor.bind_photo(photo, photo_no)
            else:
                editor.clear()

        self._sync_focused_photo()
        self._relayout_visible_editors(len(visible_items))
        self._update_navigation_buttons(current_no - 1, total)

    def _relayout_visible_editors(self, visible_count: int) -> None:
        while self._editors_layout.count():
            self._editors_layout.takeAt(0)

        if visible_count == 1:
            self._editors_layout.addWidget(self._editor_widgets[0], 0, 0, 1, 2)
            return

        for index in range(visible_count):
            row = index // 2
            col = index % 2
            self._editors_layout.addWidget(self._editor_widgets[index], row, col)

    def _update_navigation_buttons(self, current_index: int | None, total: int) -> None:
        has_previous = current_index is not None and current_index > 0
        has_next = current_index is not None and current_index < total - 1
        self._btn_previous.setEnabled(has_previous)
        self._btn_next.setEnabled(has_next)

        focused = self.focused_photo() or self.current_photo()
        if focused is None:
            self._btn_move_previous.setEnabled(False)
            self._btn_move_next.setEnabled(False)
            return

        focused_index = self._photo_items.index(focused)
        self._btn_move_previous.setEnabled(focused_index > 0)
        self._btn_move_next.setEnabled(focused_index < total - 1)

    def _show_previous_photo(self) -> None:
        current = self.current_photo()
        if current is None:
            return
        current_index = self._photo_items.index(current)
        if current_index <= 0:
            return
        self._current_photo_key = self._photo_key(self._photo_items[current_index - 1])
        self._refresh_display()

    def _show_next_photo(self) -> None:
        current = self.current_photo()
        if current is None:
            return
        current_index = self._photo_items.index(current)
        if current_index >= len(self._photo_items) - 1:
            return
        self._current_photo_key = self._photo_key(self._photo_items[current_index + 1])
        self._refresh_display()

    def _move_current_photo_left(self) -> None:
        target = self.focused_photo() or self.current_photo()
        if target is None:
            return

        arrange_page = self._wizard()._photo_arrange_page
        if arrange_page.move_photo_item_left(target) is None:
            return

        self._photo_items = list(arrange_page.collect_photo_items())
        self._current_photo_key = self._photo_key(target)
        self._focused_photo_key = self._photo_key(target)
        self._refresh_display()

        active_editor = self._find_editor_for_photo_key(self._focused_photo_key)
        if active_editor is not None:
            active_editor.focus_primary_field()

    def _move_current_photo_right(self) -> None:
        target = self.focused_photo() or self.current_photo()
        if target is None:
            return

        arrange_page = self._wizard()._photo_arrange_page
        if arrange_page.move_photo_item_right(target) is None:
            return

        self._photo_items = list(arrange_page.collect_photo_items())
        self._current_photo_key = self._photo_key(target)
        self._focused_photo_key = self._photo_key(target)
        self._refresh_display()

        active_editor = self._find_editor_for_photo_key(self._focused_photo_key)
        if active_editor is not None:
            active_editor.focus_primary_field()