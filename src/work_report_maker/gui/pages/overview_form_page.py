"""ウィザード Step 3: 工事概要フォームページ。

テンプレート 2 枚目「工事完了報告書」の概要情報を入力する:
    (1) 施工対象・名称  — 表紙の建物名を自動流用（読み取り専用）
    (2) 施工場所        — 表紙の作業場所名を自動流用（読み取り専用）
    (3) 施工内容        — 表紙の工事・作業名を自動流用（読み取り専用）
    (4) 施工日時        — 表紙の日時を自動流用（読み取り専用）
    (5) 施工担当        — 現場責任者 QLineEdit + 現場作業者 QLineEdit

作業内容グループは Step 4（WorkContentPage）で入力する。

固定値:
    - overview.title = "工 事 完 了 報 告 書"
    - work_section_title / note_line / ending / blank_line_count はデフォルト固定
    - company_lines は会社情報 JSON から自動導出
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWizardPage,
)
from work_report_maker.gui.wizard_contexts import OverviewDefaults

if TYPE_CHECKING:
    from work_report_maker.gui.main_window import ReportWizard


# ── メインページ ──────────────────────────────────────────

class OverviewFormPage(QWizardPage):
    """工事概要情報入力用のウィザードページ。

    表紙から自動流用:
        施工対象・名称 / 施工場所 / 施工内容 / 施工日時

    手動入力:
        施工担当（現場責任者 / 現場作業者）

    表示ラベルと最終 payload の両方が Cover page 由来の同じ既定値を使うため、
    値の意味づけは `OverviewDefaults` に寄せ、この page 自体は UI 更新と追加入力の採取に集中する。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("工事概要")
        self.setSubTitle("工事完了報告書（2 ページ目）の概要情報を入力してください。")

        # ── 表紙から流用（読み取り専用） ──
        self._lbl_target = QLabel()  # 施工対象・名称
        self._lbl_location = QLabel()  # 施工場所
        self._lbl_content = QLabel()  # 施工内容
        self._lbl_date = QLabel()  # 施工日時

        info_form = QFormLayout()
        info_form.addRow("施工対象・名称", self._lbl_target)
        info_form.addRow("施工場所", self._lbl_location)
        info_form.addRow("施工内容", self._lbl_content)
        info_form.addRow("施工日時", self._lbl_date)

        info_group = QGroupBox("表紙から流用")
        info_group.setLayout(info_form)

        # ── 施工担当 ──
        self._manager_edit = QLineEdit()
        self._manager_edit.setPlaceholderText("例: 川崎　潤")
        self._workers_edit = QLineEdit()
        self._workers_edit.setPlaceholderText("例: 他 2 名")

        staff_form = QFormLayout()
        staff_form.addRow("現場責任者", self._manager_edit)
        staff_form.addRow("現場作業者", self._workers_edit)

        # ── レイアウト組立 ──
        main_layout = QVBoxLayout()
        main_layout.addWidget(info_group)
        main_layout.addLayout(staff_form)
        main_layout.addStretch()
        self.setLayout(main_layout)

    # ── ページ遷移時の自動更新 ─────────────────────────────

    def _wizard(self) -> ReportWizard:
        """ReportWizard への型付き参照を返す。"""
        from work_report_maker.gui.main_window import ReportWizard

        return cast(ReportWizard, self.wizard())

    def initializePage(self) -> None:
        """Step 2（CoverFormPage）の入力値を読み取り専用欄へ反映する。

        QWizard が「次へ」で本ページへ遷移するたびに呼ばれるため、
        ユーザーが Step 2 へ戻って値を変更した場合も追従する。
        """
        defaults = self._overview_defaults()
        self._lbl_target.setText(defaults.target)
        self._lbl_location.setText(defaults.location)
        self._lbl_content.setText(defaults.content)
        self._lbl_date.setText(defaults.work_date_text)

    def _overview_defaults(self) -> OverviewDefaults:
        """Cover 由来の overview 既定値を取得する。"""
        return self._wizard().overview_defaults()

    def default_photo_site(self) -> str:
        """写真説明の「現場」に使う既定値を返す。"""
        return self._wizard().default_photo_site()

    def default_photo_location(self) -> str:
        """写真説明の「施工箇所」に使う既定値を返す。"""
        return self._wizard().default_photo_location()

    # ── データ収集 ────────────────────────────────────────
    def _build_info_rows(self) -> list[dict]:
        """info_rows を組み立てる。表紙流用 4 項目 + 施工担当。"""
        manager = self._manager_edit.text().strip()
        workers = self._workers_edit.text().strip()
        return self._overview_defaults().build_info_rows(manager=manager, workers=workers)

    def collect_overview_data(self) -> dict:
        """フォーム入力値を ``raw_report.json`` の ``overview`` 構造に合わせた dict で返す。

        戻り値の構造は data/raw_report.json の "overview" キーと同じ形式。
        """
        # page 側では GUI 入力値だけを supply し、定型タイトルや company_lines などの
        # schema ルールは OverviewDefaults 側へ委譲する。
        defaults = self._overview_defaults()
        return defaults.build_payload(
            work_groups=self._wizard().collect_work_groups(),
            manager=self._manager_edit.text().strip(),
            workers=self._workers_edit.text().strip(),
        )

    def form_state(self) -> dict:
        return {
            "manager": self._manager_edit.text(),
            "workers": self._workers_edit.text(),
        }

    def apply_form_state(self, state: dict) -> None:
        self._manager_edit.setText(str(state.get("manager", "")))
        self._workers_edit.setText(str(state.get("workers", "")))
        self.initializePage()

    def clear_form_state(self) -> None:
        self.apply_form_state({})
