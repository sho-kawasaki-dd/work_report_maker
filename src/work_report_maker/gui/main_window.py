"""報告書作成ウィザード（メインウィンドウ）。

QWizard ベースのウィザード形式 UI。ページ遷移:
    Step 1: ProjectNamePage   — プロジェクト名入力
    Step 2: CoverFormPage     — 表紙情報フォーム
    Step 3: OverviewFormPage  — 工事概要フォーム
    Step 4: WorkContentPage   — 作業内容フォーム
    Step 5: PhotoImportPage   — 写真インポート
    Step 6: PhotoArrangePage  — 写真並び替え・追加・削除
    Step 7: PhotoDescriptionPage — 写真説明の確認・入力

ウィザード完了時（「完了」ボタン押下）に全フォームデータを
raw_report.json の cover/overview 構造に合わせた JSON として stderr に出力する。
（Phase 1 の確認用。後続フェーズで PDF 生成連携に置き換え予定。）
"""

from __future__ import annotations

import json
import sys

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox, QWizard

from work_report_maker.gui.pages.cover_form_page import CoverFormPage
from work_report_maker.gui.pages.overview_form_page import OverviewFormPage
from work_report_maker.gui.pages.photo_arrange_page import PhotoArrangePage
from work_report_maker.gui.pages.photo_description_page import PhotoDescriptionPage
from work_report_maker.gui.pages.photo_import_page import PhotoDescriptionDefaults, PhotoImportPage, PhotoItem
from work_report_maker.gui.pages.project_name_page import ProjectNamePage
from work_report_maker.gui.pages.work_content_page import WorkContentPage
from work_report_maker.gui.report_build_helper import build_photos_payload, build_report_payload
from work_report_maker.gui.wizard_contexts import (
    CoverDisplayInfo,
    OverviewDefaults,
    PhotoImportSettings,
    WizardPhotoContext,
    WorkContentDefaults,
    load_company_lines,
)


class ReportWizard(QWizard):
    """報告書作成のメインウィザード。

    ページ構成:
        1. ProjectNamePage  — プロジェクト名（必須、空欄で「次へ」無効化）
        2. CoverFormPage    — 表紙情報（日付、提出先、報告書名、建物名、住所、日時等）
        3. OverviewFormPage — 工事概要（施工担当等）
        4. WorkContentPage  — 作業内容（グループ＋サブグループ）
        5. PhotoImportPage  — 写真インポート（フォルダ/ファイル/ZIP 対応）
        6. PhotoArrangePage — 写真並び替え・追加・削除
        7. PhotoDescriptionPage — 写真説明の確認・入力

    このクラスは「各 page の生成と遷移制御」「Cover 由来の共有既定値の提供」
    「完了時の最終 payload 組み立て orchestration」に責務を限定する。
    個別の photo 操作や payload の詳細変換は、page や helper へ委譲する。
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
        self._photo_description_page = PhotoDescriptionPage()
        self._photo_context = WizardPhotoContext(
            photo_import_page=self._photo_import_page,
            photo_arrange_page=self._photo_arrange_page,
        )
        self._photo_tmp_dir = None

        # ページ順に追加（QWizard が自動的に「次へ」「戻る」「完了」ボタンを管理）
        self.addPage(self._project_page)
        self.addPage(self._cover_page)
        self.addPage(self._overview_page)
        self.addPage(self._work_content_page)
        self.addPage(self._photo_import_page)
        self.addPage(self._photo_arrange_page)
        self.addPage(self._photo_description_page)

    def photo_description_defaults(self) -> PhotoDescriptionDefaults:
        """写真説明欄へ注入する既定値を返す。"""

        # Cover page は photo 系ページにとっての source of truth なので、PhotoItem へ
        # 初期反映する既定値は常に最新の cover 表示値から再構築する。
        cover = self.cover_display_info()
        return PhotoDescriptionDefaults(
            site=cover.photo_site,
            work_date=self._cover_page.format_start_date(),
            location=cover.photo_location,
        )

    def cover_display_info(self) -> CoverDisplayInfo:
        """Cover page から他ページ向けの表示値セットを切り出す。"""

        cover = self._cover_page
        return CoverDisplayInfo(
            building_name=cover.building_name(),
            subtitle=cover.subtitle(),
            title_text=cover.title_text(),
            work_date_text=cover.format_work_date(),
            recipient_text=cover.recipient_text(),
        )

    def cover_info(self) -> CoverDisplayInfo:
        return self.cover_display_info()

    def overview_defaults(self) -> OverviewDefaults:
        """Overview page が必要とする cover 由来の既定値を返す。"""

        cover = self.cover_display_info()
        recipient = cover.recipient_text
        if recipient:
            recipient += "　御中"
        return OverviewDefaults(
            recipient=recipient,
            target=cover.photo_site,
            location=cover.photo_location,
            content=cover.title_text,
            work_date_text=cover.work_date_text,
            company_lines=load_company_lines(),
        )

    def work_content_defaults(self) -> WorkContentDefaults:
        """WorkContent page の先頭固定グループに使う既定値を返す。"""
        return WorkContentDefaults(first_group_title=self.cover_display_info().title_text)

    def photo_context(self) -> WizardPhotoContext:
        """photo 系 page へ渡す共有 context の単一入口。"""
        return self._photo_context

    def default_photo_site(self) -> str:
        return self.cover_display_info().photo_site

    def default_photo_location(self) -> str:
        return self.cover_display_info().photo_location

    def collect_work_groups(self) -> list[dict]:
        return self._work_content_page.collect_work_groups()

    def collect_cover_data(self) -> dict:
        return self._cover_page.collect_cover_data()

    def collect_overview_data(self) -> dict:
        return self._overview_page.collect_overview_data()

    def imported_photo_items(self) -> list[PhotoItem]:
        return self._photo_context.imported_photo_items()

    def photo_import_settings(self) -> PhotoImportSettings:
        return self._photo_context.photo_import_settings()

    def add_imported_photo_items(self, items: list[PhotoItem]) -> None:
        self._photo_context.add_imported_photo_items(items)

    def remove_imported_photo_items(self, items: list[PhotoItem]) -> None:
        self._photo_context.remove_imported_photo_items(items)

    def sync_imported_photo_defaults(self) -> None:
        self._photo_context.sync_imported_photo_defaults()

    def arranged_photo_items(self) -> list[PhotoItem]:
        return self._photo_context.arranged_photo_items()

    def move_arranged_photo_left(self, photo: PhotoItem) -> int | None:
        return self._photo_context.move_arranged_photo_left(photo)

    def move_arranged_photo_right(self, photo: PhotoItem) -> int | None:
        return self._photo_context.move_arranged_photo_right(photo)

    def stop_active_photo_operations(self) -> bool:
        """PhotoImport/Arrange が抱えるバックグラウンド処理を停止する。"""

        # closeEvent 側では「まだ停止中かどうか」だけ知りたいため、個別 page の停止詳細は
        # この集約メソッドへ隠蔽する。
        arrange_stopped = self._photo_arrange_page.cancel_active_import()
        import_stopped = self._photo_import_page.cancel_active_import()
        return arrange_stopped and import_stopped

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.stop_active_photo_operations():
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
        result = self._build_report_payload()
        # 確認用に stderr へ JSON ダンプ（PDF 生成連携は後続フェーズ）
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        super().accept()

    def _build_report_payload(self) -> dict:
        """各 page の入力値を raw report 互換 payload へ束ねる。"""

        # build_report_payload() は photos 用の TemporaryDirectory も返すため、wizard 側では
        # その所有権だけ保持し、schema 組み立ての詳細には立ち入らない。
        build_result = build_report_payload(
            project_name=self.field("project_name"),
            cover=self.collect_cover_data(),
            overview=self.collect_overview_data(),
            photo_items=self.arranged_photo_items(),
        )
        self._photo_tmp_dir = build_result.photo_tmp_dir
        return build_result.payload

    def _build_photos(self) -> list[dict]:
        """PhotoArrangePage の並び順で photos 配列を構築する。

        各 PhotoItem の bytes データを一時ファイルに書き出し、
        photo_path として file:// URI を設定する。
        一時ディレクトリは self._photo_tmp_dir に保持し、
        PDF 生成完了後にクリーンアップされる。
        """
        built_photos = build_photos_payload(self.arranged_photo_items())
        self._photo_tmp_dir = built_photos.temp_dir
        return built_photos.photos
