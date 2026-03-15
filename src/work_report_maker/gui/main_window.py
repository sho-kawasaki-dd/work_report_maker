"""報告書作成ウィザード（メインウィンドウ）。

QWizard ベースのウィザード形式 UI。ページ遷移:
    Step 1: ProjectNamePage   — プロジェクト名入力
    Step 2: CoverFormPage     — 表紙情報フォーム
    Step 3: OverviewFormPage  — 工事概要フォーム
    Step 4: WorkContentPage   — 作業内容フォーム
    Step 5: PhotoImportPage   — 写真インポート
    Step 6: PhotoArrangePage  — 写真並び替え・追加・削除
    Step 7: PhotoDescriptionPage — 写真説明の確認・入力

ウィザード完了時（「完了」ボタン押下）に全フォームデータを raw report 互換 payload へ束ね、
保存ダイアログで確定した出力先へ PDF を生成する。PDF 生成本体は services 層の
`generate_full_report(...)` を再利用し、GUI は保存先選択とエラー表示だけを担う。
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWizard

from work_report_maker.gui.pages.cover_form_page import CoverFormPage
from work_report_maker.gui.pages.overview_form_page import OverviewFormPage
from work_report_maker.gui.pages.photo_arrange_page import PhotoArrangePage
from work_report_maker.gui.pages.photo_description_page import PhotoDescriptionPage
from work_report_maker.gui.pages.photo_import_page import PhotoDescriptionDefaults, PhotoImportPage, PhotoItem
from work_report_maker.gui.pages.project_name_page import ProjectNamePage
from work_report_maker.gui.project_store import (
    ProjectNotFoundError,
    ProjectStoreError,
    delete_project,
    load_project,
    project_exists,
    save_project,
)
from work_report_maker.gui.report_generation_operation import PDFGenerationController
from work_report_maker.gui.pages.work_content_page import WorkContentPage
from work_report_maker.gui.preset_manager import load_default_output_dir
from work_report_maker.gui.report_build_helper import build_photos_payload, build_report_payload
from work_report_maker.gui.wizard_contexts import (
    CoverDisplayInfo,
    OverviewDefaults,
    PhotoImportSettings,
    WizardPhotoContext,
    WorkContentDefaults,
    load_company_lines,
)


_INVALID_PDF_STEM_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_pdf_stem(name: str) -> str:
    """保存ダイアログの初期提案に使う安全な stem 文字列を返す。"""

    # ここでは初期値だけを安全化し、ユーザーがダイアログで最終的に選んだ名前はそのまま尊重する。
    sanitized = _INVALID_PDF_STEM_CHARS.sub("_", name).strip().rstrip(". ")
    return sanitized or "report"


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
        self.setMinimumSize(1000, 800)
        # Windows の AeroStyle は Back を左上の小さな矢印として描画するため、
        # 今回求められている「Next の左側に並ぶ Back」を安定して出すには、
        # 下部のボタン列を使う ClassicStyle へ固定しておく必要がある。
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        self.setButtonText(QWizard.WizardButton.CustomButton1, "プロジェクトを保存")
        self.setButtonLayout(
            [
                QWizard.WizardButton.CustomButton1,
                QWizard.WizardButton.Stretch,
                QWizard.WizardButton.BackButton,
                QWizard.WizardButton.NextButton,
                QWizard.WizardButton.FinishButton,
                QWizard.WizardButton.CancelButton,
            ]
        )
        # reject() → close() → closeEvent() → super().closeEvent() → reject() のように
        # Qt 内部で再入が起きると確認ダイアログが二重表示される。_close_guard で
        # closeEvent 処理中の再入を検出し、確認ダイアログは必ず 1 回だけにする。
        self._close_guard = False

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
        self._pdf_generation_controller = self._create_pdf_generation_controller()

        # ページ順に追加（QWizard が自動的に「次へ」「戻る」「完了」ボタンを管理）
        self.addPage(self._project_page)
        self.addPage(self._cover_page)
        self.addPage(self._overview_page)
        self.addPage(self._work_content_page)
        self.addPage(self._photo_import_page)
        self.addPage(self._photo_arrange_page)
        self.addPage(self._photo_description_page)
        # ボタン文言と表示状態は wizard style の再構築時に上書きされることがあるため、
        # currentIdChanged と初期反映の両方で同期しておく。
        self.setButtonText(QWizard.WizardButton.BackButton, "Back")
        custom_save_button = self.button(QWizard.WizardButton.CustomButton1)
        if custom_save_button is not None:
            custom_save_button.clicked.connect(self.save_current_project)
        self.currentIdChanged.connect(self._sync_navigation_buttons)
        self._sync_navigation_buttons(self.currentId())

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

    def project_name_text(self) -> str:
        project_name = self.field("project_name")
        if isinstance(project_name, str):
            return project_name.strip()
        return ""

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

    def save_current_project(self) -> bool:
        """現在の入力状態を任意保存する。"""

        project_name = self.project_name_text()
        if not project_name:
            QMessageBox.warning(self, "保存エラー", "プロジェクト名を入力してください。")
            return False

        if project_exists(project_name):
            answer = QMessageBox.question(
                self,
                "上書き確認",
                f"プロジェクト「{project_name}」は既に存在します。上書きしますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False

        try:
            project_dir = save_project(**self._collect_project_save_kwargs())
        except ProjectStoreError as exc:
            QMessageBox.critical(self, "保存エラー", str(exc))
            return False

        QMessageBox.information(self, "保存完了", f"プロジェクトを保存しました。\n{project_dir}")
        return True

    def load_project_named(self, project_name: str) -> bool:
        """指定名のプロジェクトを読み込み、wizard 状態へ反映する。"""

        try:
            state = load_project(project_name)
        except (ProjectNotFoundError, ProjectStoreError) as exc:
            QMessageBox.critical(self, "読込エラー", str(exc))
            return False

        self._apply_project_state(state)
        return True

    def delete_project_named(self, project_name: str) -> bool:
        """指定名の保存済みプロジェクトを削除する。"""

        try:
            delete_project(project_name)
        except (ProjectNotFoundError, ProjectStoreError) as exc:
            QMessageBox.critical(self, "削除エラー", str(exc))
            return False

        if self.project_name_text() == project_name:
            self.reset_project_state(clear_project_name=True)
        QMessageBox.information(self, "削除完了", f"プロジェクト「{project_name}」を削除しました。")
        return True

    def reject(self) -> None:
        """Cancel ボタン経由の終了要求。closeEvent() へ一本化する。

        QWizard の Cancel ボタンは reject() を呼ぶが、確認ダイアログの表示は
        closeEvent() 側に集約する。reject() 自体は close() を呼ぶだけにすることで、
        Qt 内部の reject → closeEvent → reject 再入によるダイアログ二重表示を防ぐ。
        """
        self.close()

    def reset_project_state(self, *, clear_project_name: bool) -> None:
        self._cover_page.clear_form_state()
        self._overview_page.clear_form_state()
        self._work_content_page.clear_form_state()
        self._photo_import_page.clear_project_state()
        self._photo_arrange_page.reset_items_from_context()
        if clear_project_name:
            self._project_page.set_project_name("")
        self._cover_page.initializePage()

    def _apply_project_state(self, state: dict) -> None:
        self.reset_project_state(clear_project_name=False)
        self._project_page.set_project_name(str(state.get("project_name", "")))
        self._cover_page.apply_form_state(dict(state.get("cover_state", {})))
        self._overview_page.apply_form_state(dict(state.get("overview_state", {})))
        self._work_content_page.apply_form_state(dict(state.get("work_content_state", {})))
        self._photo_import_page.apply_import_settings_state(dict(state.get("photo_import_settings", {})))
        self._photo_import_page.replace_photo_items(list(state.get("photo_items", [])))
        self._photo_arrange_page.reset_items_from_context()
        self._cover_page.initializePage()

    def _collect_project_save_kwargs(self) -> dict:
        photo_items = self.arranged_photo_items()
        if not photo_items:
            photo_items = self.imported_photo_items()
        return {
            "project_name": self.project_name_text(),
            "cover_state": self._cover_page.form_state(),
            "overview_state": self._overview_page.form_state(),
            "work_content_state": self._work_content_page.form_state(),
            "photo_import_settings": self._photo_import_page.import_settings_state(),
            "photo_items": photo_items,
        }

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cancel・×ボタン・Alt+F4 すべての終了経路の一本化ゲート。

        Qt 内部では closeEvent 完了後に reject() が呼ばれるケースがあり、
        reject() → close() → closeEvent() の再入が起きうる。_close_guard で
        確認ダイアログが複数回表示されるのを防ぐ。

        super().closeEvent() は呼ばず event を直接操作することで、
        Qt のコールバック連鎖を一切発生させない。
        """
        if self._close_guard:
            event.accept()
            return
        self._close_guard = True
        try:
            if not self._confirm_project_discard():
                event.ignore()
                return
            if not self._can_close_wizard():
                event.ignore()
                return
            self.setResult(int(QDialog.DialogCode.Rejected))
            event.accept()
        finally:
            # 終了が成立しなかった場合のみガードを解除し、再試行を許可する。
            # 終了が成立した場合はガードを立てたまま再入に備える。
            if not event.isAccepted():
                self._close_guard = False

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # QWizard は show 後に内部ボタンを作り直すことがあるため、初回表示直後にも
        # Back の可視状態と文言を再適用する。
        self._sync_navigation_buttons(self.currentId())

    def accept(self) -> None:
        """ウィザード完了時の処理。

        保存ダイアログで出力先を確定し、共通の PDF 生成サービスへ入力を渡す。

        PDF 生成はバックグラウンドで実行し、成功時だけ一時ディレクトリを回収する。
        失敗時や中断時は編集状態を保持したまま再実行できるよう、ウィザード自体は閉じない。
        """
        if self._pdf_generation_controller.is_running():
            return

        output_path = self._choose_output_path()
        if output_path is None:
            return

        try:
            result = self._build_report_payload()
        except Exception as exc:
            QMessageBox.critical(self, "PDF 生成エラー", f"PDF の生成に失敗しました。\n{exc}")
            return

        self._pdf_generation_controller.start(
            report_data=result,
            output_path=output_path,
            on_success=lambda: self._handle_pdf_generation_success(output_path),
            on_error=self._handle_pdf_generation_error,
            on_cancelled=self._handle_pdf_generation_cancelled,
        )

    def _create_pdf_generation_controller(self) -> PDFGenerationController:
        return PDFGenerationController(self)

    def _handle_pdf_generation_success(self, output_path: Path) -> None:
        # 成功後は一時ファイルを確実に掃除したうえで、終了するかどうかだけを
        # Step 1 の永続設定へ委ねる。再生成ニーズがあるため、既定は閉じない。
        self._cleanup_photo_tmp_dir()
        QMessageBox.information(self, "PDF 生成完了", f"PDF を保存しました。\n{output_path}")
        if self.field("close_after_pdf_generation") is True:
            super().accept()

    def _handle_pdf_generation_error(self, message: str) -> None:
        QMessageBox.critical(self, "PDF 生成エラー", f"PDF の生成に失敗しました。\n{message}")

    def _handle_pdf_generation_cancelled(self) -> None:
        QMessageBox.information(
            self,
            "PDF 生成を中断しました",
            "PDF の生成を中断しました。入力内容は保持されているため、そのまま再実行できます。",
        )

    def _build_report_payload(self) -> dict:
        """各 page の入力値を raw report 互換 payload へ束ねる。"""

        # build_report_payload() は photos 用の TemporaryDirectory も返すため、wizard 側では
        # その所有権だけ保持し、schema 組み立ての詳細には立ち入らない。
        self._cleanup_photo_tmp_dir()
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

    def _selected_output_directory(self) -> Path:
        """保存ダイアログの初期フォルダとして使うディレクトリを返す。"""

        # field() は文字列で返るため、未設定や空文字のときだけ永続設定の fallback へ戻す。
        field_value = self.field("output_dir")
        if isinstance(field_value, str) and field_value.strip():
            return Path(field_value)
        return load_default_output_dir()

    def _choose_output_path(self) -> Path | None:
        """保存ダイアログを開き、最終的な PDF 出力パスを返す。"""

        project_name = self.field("project_name")
        project_name_text = project_name if isinstance(project_name, str) else ""
        initial_path = self._selected_output_directory() / f"{_sanitize_pdf_stem(project_name_text)}.pdf"

        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存する PDF ファイルを選択",
            str(initial_path),
            "PDF (*.pdf)",
        )
        if not selected_path:
            return None

        output_path = Path(selected_path)
        if output_path.suffix.lower() != ".pdf":
            # ユーザーが拡張子を省略しても PDF 保存であることは固定する。
            output_path = output_path.with_suffix(".pdf")
        if not output_path.parent.exists():
            QMessageBox.warning(self, "保存先エラー", "指定した保存先フォルダが存在しません。")
            return None
        return output_path

    def _cleanup_photo_tmp_dir(self) -> None:
        """report payload 構築中に確保した一時ディレクトリを解放する。"""

        if self._photo_tmp_dir is None:
            return
        self._photo_tmp_dir.cleanup()
        self._photo_tmp_dir = None

    def _sync_navigation_buttons(self, page_id: int) -> None:
        """Back ボタンの文言と可視状態をページ位置に合わせて再同期する。

        ClassicStyle でも Qt 側の再レイアウト時に文言や表示状態が既定値へ戻ることがある。
        そのため page 遷移時と初回 show 時の両方でこのメソッドを通し、
        1 ページ目では非表示、2 ページ目以降では Next の左側に表示する状態を保つ。
        """

        back_button = self.button(QWizard.WizardButton.BackButton)
        if back_button is None:
            return
        # 日本語 UI でも、今回の要求ではラベルが明示的に "Back" / "Next" 指定なので固定する。
        back_button.setText("Back")
        is_visible = page_id > 0
        back_button.setVisible(is_visible)
        back_button.setEnabled(is_visible)

        save_button = self.button(QWizard.WizardButton.CustomButton1)
        if save_button is None:
            return
        save_button.setText("プロジェクトを保存")
        show_save_button = page_id >= 1
        save_button.setVisible(show_save_button)
        save_button.setEnabled(show_save_button and bool(self.project_name_text()))

    def _confirm_project_discard(self) -> bool:
        """入力中プロジェクトを破棄して終了するか確認する。

        ここでいう「プロジェクト破棄」は、未保存の GUI 入力状態を捨ててウィザードを閉じる意味で、
        既存ファイルの削除までは行わない。Yes/No を返す純粋な確認関数として分離しておくことで、
        Cancel ボタンとタイトルバー close の両方から同じ文言を再利用できる。
        """

        answer = QMessageBox.question(
            self,
            "終了確認",
            "プロジェクトを破棄してアプリを終了しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _can_close_wizard(self) -> bool:
        """終了前にバックグラウンド処理の状態を確認する。

        ユーザーが終了を了承しても、実際には PDF 生成中や画像 import 停止待ちの可能性がある。
        その場合は終了を保留して理由だけを表示し、処理の整合性を優先する。
        """

        if self._pdf_generation_controller.is_running():
            QMessageBox.information(
                self,
                "PDF 生成中",
                "報告書PDFを生成しています。中断または完了後に閉じてください。",
            )
            return False
        if not self.stop_active_photo_operations():
            QMessageBox.information(
                self,
                "画像処理を停止中",
                "画像の読み込み処理を停止しています。数秒待ってから再度閉じてください。",
            )
            return False
        return True
