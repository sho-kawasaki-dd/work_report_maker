"""報告書作成ウィザード（メインウィンドウ）。

QWizard ベースのウィザード形式 UI。ページ遷移:
    Step 1: ProjectNamePage   — プロジェクト名入力
    Step 2: CoverFormPage     — 表紙情報フォーム
    Step 3: OverviewFormPage  — 工事概要フォーム
    Step 4: WorkContentPage   — 作業内容フォーム

ウィザード完了時（「完了」ボタン押下）に全フォームデータを
raw_report.json の cover/overview 構造に合わせた JSON として stderr に出力する。
（Phase 1 の確認用。後続フェーズで PDF 生成連携に置き換え予定。）
"""

from __future__ import annotations

import json
import sys

from PySide6.QtWidgets import QWizard

from work_report_maker.gui.pages.cover_form_page import CoverFormPage
from work_report_maker.gui.pages.overview_form_page import OverviewFormPage
from work_report_maker.gui.pages.project_name_page import ProjectNamePage
from work_report_maker.gui.pages.work_content_page import WorkContentPage


class ReportWizard(QWizard):
    """報告書作成のメインウィザード。

    ページ構成:
        1. ProjectNamePage  — プロジェクト名（必須、空欄で「次へ」無効化）
        2. CoverFormPage    — 表紙情報（日付、提出先、報告書名、建物名、住所、日時等）
        3. OverviewFormPage — 工事概要（施工担当等）
        4. WorkContentPage  — 作業内容（グループ＋サブグループ）
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("報告書作成")
        self.setMinimumSize(640, 520)

        # ウィザードページのインスタンスを作成
        self._project_page = ProjectNamePage()
        self._cover_page = CoverFormPage()
        self._overview_page = OverviewFormPage()
        self._work_content_page = WorkContentPage()

        # ページ順に追加（QWizard が自動的に「次へ」「戻る」「完了」ボタンを管理）
        self.addPage(self._project_page)
        self.addPage(self._cover_page)
        self.addPage(self._overview_page)
        self.addPage(self._work_content_page)

    def accept(self) -> None:
        """ウィザード完了時の処理。

        全ページのフォームデータを収集し、raw_report.json の cover 構造に合わせた
        JSON を stderr に出力する。Phase 1 ではこの出力で動作確認を行う。
        """
        # QWizard の registerField で登録したフィールドは field() で取得可能
        project_name = self.field("project_name")
        # CoverFormPage の collect_cover_data() でフォーム入力値を dict に集約
        cover = self._cover_page.collect_cover_data()
        # OverviewFormPage の collect_overview_data() で工事概要データを dict に集約
        overview = self._overview_page.collect_overview_data()
        result = {
            "project_name": project_name,
            "cover": cover,
            "overview": overview,
        }
        # 確認用に stderr へ JSON ダンプ（PDF 生成連携は後続フェーズ）
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        super().accept()
