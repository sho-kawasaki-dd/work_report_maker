"""報告書作成ウィザード（メインウィンドウ）。

QWizard ベースのウィザード形式 UI。ページ遷移:
    Step 1: ProjectNamePage   — プロジェクト名入力
    Step 2: CoverFormPage     — 表紙情報フォーム
    Step 3: OverviewFormPage  — 工事概要フォーム
    Step 4: WorkContentPage   — 作業内容フォーム
    Step 5: PhotoImportPage   — 写真インポート
    Step 6: PhotoArrangePage  — 写真並び替え・追加・削除

ウィザード完了時（「完了」ボタン押下）に全フォームデータを
raw_report.json の cover/overview 構造に合わせた JSON として stderr に出力する。
（Phase 1 の確認用。後続フェーズで PDF 生成連携に置き換え予定。）
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox, QWizard

from work_report_maker.gui.pages.cover_form_page import CoverFormPage
from work_report_maker.gui.pages.overview_form_page import OverviewFormPage
from work_report_maker.gui.pages.photo_arrange_page import PhotoArrangePage
from work_report_maker.gui.pages.photo_import_page import PhotoDescriptionDefaults, PhotoImportPage
from work_report_maker.gui.pages.project_name_page import ProjectNamePage
from work_report_maker.gui.pages.work_content_page import WorkContentPage


class ReportWizard(QWizard):
    """報告書作成のメインウィザード。

    ページ構成:
        1. ProjectNamePage  — プロジェクト名（必須、空欄で「次へ」無効化）
        2. CoverFormPage    — 表紙情報（日付、提出先、報告書名、建物名、住所、日時等）
        3. OverviewFormPage — 工事概要（施工担当等）
        4. WorkContentPage  — 作業内容（グループ＋サブグループ）
        5. PhotoImportPage  — 写真インポート（フォルダ/ファイル/ZIP 対応）
        6. PhotoArrangePage — 写真並び替え・追加・削除
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
        self._photo_import_page = PhotoImportPage()
        self._photo_arrange_page = PhotoArrangePage()

        # ページ順に追加（QWizard が自動的に「次へ」「戻る」「完了」ボタンを管理）
        self.addPage(self._project_page)
        self.addPage(self._cover_page)
        self.addPage(self._overview_page)
        self.addPage(self._work_content_page)
        self.addPage(self._photo_import_page)
        self.addPage(self._photo_arrange_page)

    def photo_description_defaults(self) -> PhotoDescriptionDefaults:
        """写真説明欄へ注入する既定値を返す。"""
        return PhotoDescriptionDefaults(
            site=self._overview_page.default_photo_site(),
            work_date=self._cover_page.format_start_date(),
            location=self._overview_page.default_photo_location(),
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        arrange_stopped = self._photo_arrange_page.cancel_active_import()
        import_stopped = self._photo_import_page.cancel_active_import()
        if not arrange_stopped or not import_stopped:
            event.ignore()
            QMessageBox.information(
                self,
                "画像処理を停止中",
                "画像の読み込み処理を停止しています。数秒待ってから再度閉じてください。",
            )
            return
        super().closeEvent(event)

    def accept(self) -> None:
        """ウィザード完了時の処理。

        全ページのフォームデータを収集し、raw_report.json の cover/overview/photos
        構造に合わせた JSON を stderr に出力する。
        写真データは一時ディレクトリに書き出し file:// URI で参照する。
        """
        # QWizard の registerField で登録したフィールドは field() で取得可能
        project_name = self.field("project_name")
        # CoverFormPage の collect_cover_data() でフォーム入力値を dict に集約
        cover = self._cover_page.collect_cover_data()
        # OverviewFormPage の collect_overview_data() で工事概要データを dict に集約
        overview = self._overview_page.collect_overview_data()

        # 写真データを一時ファイルに書き出し、photos 配列を構築
        photos = self._build_photos()

        result = {
            "project_name": project_name,
            "cover": cover,
            "overview": overview,
            "photos": photos,
        }
        # 確認用に stderr へ JSON ダンプ（PDF 生成連携は後続フェーズ）
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        super().accept()

    def _build_photos(self) -> list[dict]:
        """PhotoArrangePage の並び順で photos 配列を構築する。

        各 PhotoItem の bytes データを一時ファイルに書き出し、
        photo_path として file:// URI を設定する。
        一時ディレクトリは self._photo_tmp_dir に保持し、
        PDF 生成完了後にクリーンアップされる。
        """
        photo_items = self._photo_arrange_page.collect_photo_items()
        if not photo_items:
            return []

        self._photo_tmp_dir = tempfile.TemporaryDirectory(prefix="wrm_photos_")
        tmp_path = Path(self._photo_tmp_dir.name)

        photos: list[dict] = []
        for i, item in enumerate(photo_items, start=1):
            ext = "jpg" if item.format == "jpeg" else item.format
            filename = f"{i:04d}.{ext}"
            file_path = tmp_path / filename
            file_path.write_bytes(item.data)

            photos.append({
                "no": i,
                "photo_path": file_path.as_uri(),
                "site": "",
                "work_date": "",
                "location": "",
                "work_content": "",
                "remarks": "",
            })
        return photos
