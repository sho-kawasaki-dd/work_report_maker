"""ウィザード Step 4: 作業内容フォームページ。

テンプレート 2 枚目「工事完了報告書」の作業内容セクションを入力する:
    - 先頭グループ（固定ヘッダ: ◎ + 工事・作業名）＋ lines
    - 追加グループ（動的追加、サブグループ 1 階層対応）

先頭グループの title は表紙の工事・作業名を自動流用する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

if TYPE_CHECKING:
    from work_report_maker.gui.main_window import ReportWizard

_FIRST_MARKER = "◎"


# ── ヘルパー: 固定高さ QTextEdit ─────────────────────────

def _make_text_edit(*, lines: int = 3, placeholder: str = "") -> QTextEdit:
    """行数を制限した QTextEdit を生成する。"""
    te = QTextEdit()
    te.setPlaceholderText(placeholder)
    line_height = te.fontMetrics().lineSpacing()
    margin = te.contentsMargins().top() + te.contentsMargins().bottom() + 8
    te.setFixedHeight(line_height * lines + margin)
    return te


# ── サブグループ ウィジェット ──────────────────────────────

class _SubGroupWidget(QWidget):
    """作業内容サブグループ（1 階層目の子）。

    UI 構成: [marker QLineEdit] [title QLineEdit] [×削除] + lines QTextEdit
    """

    def __init__(self, marker: str = "", title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.marker_edit = QLineEdit(marker)
        self.marker_edit.setFixedWidth(60)
        self.marker_edit.setPlaceholderText("1-a)")

        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("サブグループ名")

        self._btn_delete = QPushButton("×")
        self._btn_delete.setFixedWidth(28)
        self._btn_delete.setToolTip("このサブグループを削除")

        header = QHBoxLayout()
        header.setContentsMargins(16, 0, 0, 0)
        header.addWidget(QLabel("┗"))
        header.addWidget(self.marker_edit)
        header.addWidget(self.title_edit, 1)
        header.addWidget(self._btn_delete)

        self.lines_edit = _make_text_edit(lines=2, placeholder="サブグループの作業内容（改行区切り）")

        lines_indent = QHBoxLayout()
        lines_indent.setContentsMargins(32, 0, 0, 0)
        lines_indent.addWidget(self.lines_edit)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.addLayout(header)
        layout.addLayout(lines_indent)
        self.setLayout(layout)

        self._btn_delete.clicked.connect(self._request_delete)

    def _request_delete(self) -> None:
        self.setParent(None)
        self.deleteLater()

    def collect(self) -> dict:
        """work_groups 1 エントリ分の dict を返す。"""
        raw_lines = self.lines_edit.toPlainText().split("\n")
        return {
            "marker": self.marker_edit.text().strip(),
            "title": self.title_edit.text().strip(),
            "lines": [ln for ln in raw_lines if ln.strip()],
        }


# ── 追加グループ ウィジェット ─────────────────────────────

class _WorkGroupWidget(QWidget):
    """作業内容グループ（追加グループ）。サブグループを 1 階層持てる。"""

    def __init__(
        self,
        group_index: int,
        marker: str = "",
        title: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._group_index = group_index

        self.marker_edit = QLineEdit(marker)
        self.marker_edit.setFixedWidth(60)
        self.marker_edit.setPlaceholderText(f"{group_index})")

        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("グループ名")

        self._btn_delete = QPushButton("×")
        self._btn_delete.setFixedWidth(28)
        self._btn_delete.setToolTip("このグループを削除")

        header = QHBoxLayout()
        header.addWidget(self.marker_edit)
        header.addWidget(self.title_edit, 1)
        header.addWidget(self._btn_delete)

        self.lines_edit = _make_text_edit(lines=3, placeholder="作業内容（改行区切り）")

        self._sub_layout = QVBoxLayout()
        self._sub_layout.setContentsMargins(0, 0, 0, 0)

        btn_add_sub = QPushButton("+ サブグループ追加")
        btn_add_sub.clicked.connect(self._add_sub_group)

        sub_area = QVBoxLayout()
        sub_area.setContentsMargins(0, 0, 0, 0)
        sub_area.addLayout(self._sub_layout)
        sub_area.addWidget(btn_add_sub, 0, Qt.AlignmentFlag.AlignLeft)

        frame = QGroupBox()
        inner = QVBoxLayout()
        inner.addLayout(header)
        inner.addWidget(self.lines_edit)
        inner.addLayout(sub_area)
        frame.setLayout(inner)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 4, 0, 4)
        outer.addWidget(frame)
        self.setLayout(outer)

        self._btn_delete.clicked.connect(self._request_delete)

    def _next_sub_marker(self) -> str:
        count = self._sub_layout.count()
        letter = chr(ord("a") + count)
        return f"{self._group_index}-{letter})"

    def _add_sub_group(self) -> None:
        sub = _SubGroupWidget(marker=self._next_sub_marker())
        self._sub_layout.addWidget(sub)

    def _request_delete(self) -> None:
        self.setParent(None)
        self.deleteLater()

    def collect(self) -> list[dict]:
        """このグループ＋サブグループをフラット展開した list を返す。"""
        raw_lines = self.lines_edit.toPlainText().split("\n")
        entries: list[dict] = [
            {
                "marker": self.marker_edit.text().strip(),
                "title": self.title_edit.text().strip(),
                "lines": [ln for ln in raw_lines if ln.strip()],
            }
        ]
        for i in range(self._sub_layout.count()):
            item = self._sub_layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, _SubGroupWidget):
                entries.append(widget.collect())
        return entries


# ── メインページ ──────────────────────────────────────────

class WorkContentPage(QWizardPage):
    """作業内容入力用のウィザードページ。

    先頭固定グループ（◎ + 工事・作業名）＋ 動的追加グループ（サブグループ対応）。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("作業内容")
        self.setSubTitle("工事完了報告書の作業内容を入力してください。")

        # ── 先頭グループ（固定ヘッダ: ◎ + 工事・作業名） ──
        self._first_group_title_label = QLabel()
        self._first_group_lines = _make_text_edit(
            lines=3,
            placeholder="例:\n1）作業内容\n① 厨房グリストラップ清掃\nグリストラップ内部の高圧洗浄及び汚泥・バキューム処理。",
        )

        first_header = QHBoxLayout()
        first_header.addWidget(QLabel(_FIRST_MARKER))
        first_header.addWidget(self._first_group_title_label, 1)

        first_group_layout = QVBoxLayout()
        first_group_layout.addLayout(first_header)
        first_group_layout.addWidget(self._first_group_lines)

        # ── 追加グループ領域 ──
        self._groups_layout = QVBoxLayout()
        self._groups_layout.setContentsMargins(0, 0, 0, 0)
        self._group_counter = 0

        btn_add_group = QPushButton("+ グループ追加")
        btn_add_group.clicked.connect(self._add_work_group)

        work_inner = QVBoxLayout()
        work_inner.addLayout(first_group_layout)
        work_inner.addLayout(self._groups_layout)
        work_inner.addWidget(btn_add_group, 0, Qt.AlignmentFlag.AlignLeft)

        # ── スクロール可能なコンテンツ ──
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.addLayout(work_inner)
        content_layout.addStretch()
        content_widget.setLayout(content_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    # ── ページ遷移時の自動更新 ─────────────────────────────

    def _wizard(self) -> ReportWizard:
        from work_report_maker.gui.main_window import ReportWizard

        return cast(ReportWizard, self.wizard())

    def initializePage(self) -> None:
        """表紙の工事・作業名を先頭グループの title に反映する。"""
        cover = self._wizard()._cover_page
        self._first_group_title_label.setText(cover.title_text())

    # ── グループ操作 ──────────────────────────────────────

    def _add_work_group(self) -> None:
        self._group_counter += 1
        marker = f"{self._group_counter})"
        group = _WorkGroupWidget(group_index=self._group_counter, marker=marker)
        self._groups_layout.addWidget(group)

    # ── データ収集 ────────────────────────────────────────

    def collect_work_groups(self) -> list[dict]:
        """先頭固定グループ + 追加グループをフラット展開して返す。"""
        cover = self._wizard()._cover_page

        raw_lines = self._first_group_lines.toPlainText().split("\n")
        groups: list[dict] = [
            {
                "marker": _FIRST_MARKER,
                "title": cover.title_text(),
                "lines": [ln for ln in raw_lines if ln.strip()],
            }
        ]

        for i in range(self._groups_layout.count()):
            item = self._groups_layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, _WorkGroupWidget):
                groups.extend(widget.collect())

        return groups
