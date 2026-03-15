"""ウィザード Step 7: 写真説明ページ。"""

from __future__ import annotations

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

from work_report_maker.gui.pages.photo_description_dates import format_work_date, parse_work_date
from work_report_maker.gui.pages.photo_description_focus import is_active_photo_key, resolve_focused_photo_key
from work_report_maker.gui.pages.photo_description_navigation import (
    layout_positions,
    move_button_states,
    photo_index_for_key,
    resolve_current_photo_key,
    shifted_photo_key,
    visible_range,
)
from work_report_maker.gui.pages.photo_import_page import PhotoItem

if TYPE_CHECKING:
    from work_report_maker.gui.main_window import ReportWizard


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
        parsed = parse_work_date(value)
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
            self._photo.set_description_field("work_date", format_work_date(value))

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
        self._photo_items = list(self._wizard()._photo_arrange_page.collect_photo_items())
        self._current_photo_key = resolve_current_photo_key(
            self._photo_items,
            self._current_photo_key,
            self._photo_key,
        )
        if self._current_photo_key is None:
            self._focused_photo_key = None
        self._refresh_display()

    def current_photo(self) -> PhotoItem | None:
        """現在表示中の PhotoItem を返す。"""
        current_index = photo_index_for_key(self._photo_items, self._current_photo_key, self._photo_key)
        if current_index is None:
            return None
        return self._photo_items[current_index]

    def current_photo_no(self) -> int | None:
        """現在表示中の写真 No を返す。"""
        current_index = photo_index_for_key(self._photo_items, self._current_photo_key, self._photo_key)
        return None if current_index is None else current_index + 1

    def photo_count(self) -> int:
        """現在の写真件数を返す。"""
        return len(self._photo_items)

    def visible_photo_items(self) -> list[PhotoItem]:
        """現在の表示モードで見えている PhotoItem 群を返す。"""
        current_index = photo_index_for_key(self._photo_items, self._current_photo_key, self._photo_key)
        start_index, end_index = visible_range(len(self._photo_items), current_index, self._view_mode)
        if start_index == end_index:
            return []
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
        focused_index = photo_index_for_key(self._photo_items, self._focused_photo_key, self._photo_key)
        if focused_index is None:
            return None
        return self._photo_items[focused_index]

    def _find_editor_for_photo_key(self, photo_key: int | None) -> _PhotoDescriptionEditor | None:
        if photo_key is None:
            return None
        for editor in self._editor_widgets:
            photo = editor.bound_photo()
            if photo is not None and self._photo_key(photo) == photo_key:
                return editor
        return None

    def _sync_focused_photo(self) -> None:
        visible_keys = [self._photo_key(photo) for photo in self.visible_photo_items()]
        self._focused_photo_key = resolve_focused_photo_key(
            visible_keys,
            self._focused_photo_key,
            self._current_photo_key,
        )

        for editor in self._editor_widgets:
            photo = editor.bound_photo()
            editor.set_active(
                is_active_photo_key(
                    self._photo_key(photo) if photo is not None else None,
                    self._focused_photo_key,
                )
            )

    def _on_editor_focus_received(self, editor: _PhotoDescriptionEditor) -> None:
        photo = editor.bound_photo()
        if photo is None:
            return
        self._focused_photo_key = self._photo_key(photo)
        self._sync_focused_photo()
        self._update_navigation_buttons()

    def _refresh_display(self) -> None:
        total = len(self._photo_items)
        current_no = self.current_photo_no()

        if current_no is None:
            self._position_label.setText(f"現在位置: 0 / {total}")
            for editor in self._editor_widgets:
                editor.clear()
            self._relayout_visible_editors(0)
            self._update_navigation_buttons()
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
        self._update_navigation_buttons()

    def _relayout_visible_editors(self, visible_count: int) -> None:
        while self._editors_layout.count():
            self._editors_layout.takeAt(0)

        for index, row, col, row_span, col_span in layout_positions(visible_count):
            self._editors_layout.addWidget(self._editor_widgets[index], row, col, row_span, col_span)

    def _update_navigation_buttons(self) -> None:
        total = len(self._photo_items)
        current_index = photo_index_for_key(self._photo_items, self._current_photo_key, self._photo_key)

        focused = self.focused_photo() or self.current_photo()
        focused_index = None
        if focused is not None:
            focused_index = photo_index_for_key(self._photo_items, self._photo_key(focused), self._photo_key)

        has_previous, has_next, can_move_previous, can_move_next = move_button_states(
            total,
            current_index,
            focused_index,
        )
        self._btn_previous.setEnabled(has_previous)
        self._btn_next.setEnabled(has_next)
        self._btn_move_previous.setEnabled(can_move_previous)
        self._btn_move_next.setEnabled(can_move_next)

    def _show_previous_photo(self) -> None:
        previous_key = shifted_photo_key(self._photo_items, self._current_photo_key, -1, self._photo_key)
        if previous_key is None:
            return
        self._current_photo_key = previous_key
        self._refresh_display()

    def _show_next_photo(self) -> None:
        next_key = shifted_photo_key(self._photo_items, self._current_photo_key, 1, self._photo_key)
        if next_key is None:
            return
        self._current_photo_key = next_key
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