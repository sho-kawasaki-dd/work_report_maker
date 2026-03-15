"""ウィザード Step 1: プロジェクト名入力ページ。

ユーザーにプロジェクト名を入力してもらう。
のちにプロジェクトの保存機能を追加する際、この名前がファイル名等の識別子となる想定。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from PySide6.QtWidgets import QCheckBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWizardPage

from work_report_maker.gui.project_store import list_project_names
from work_report_maker.gui.preset_manager import (
    load_close_after_pdf_generation,
    load_default_output_dir,
    save_close_after_pdf_generation,
    save_default_output_dir,
)

if TYPE_CHECKING:
    from work_report_maker.gui.main_window import ReportWizard


class ProjectNamePage(QWizardPage):
    """プロジェクト名入力用のウィザードページ。

    - QLineEdit でプロジェクト名を入力
        - PDF 保存先フォルダの既定値を表示し、ここで変更できる
        - PDF 生成成功後にアプリを閉じる既定値もここで変更できる
    - registerField("project_name*", ...) により必須フィールドとして登録
      → 空欄のままでは「次へ」ボタンが無効化される

    このページの責務は入力値の妥当性検査ではなく、以降のページや保存機能が参照する
        識別子と出力先の既定値を確定させることにある。最終ファイル名の決定は Finish 時の
        保存ダイアログへ委譲し、このページではフォルダ既定値の管理だけを担う。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("プロジェクト名")
        self.setSubTitle("報告書プロジェクト名と PDF の保存先フォルダを確認してください。")

        # プロジェクト名入力フィールド
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("例: ロワジールホテル グリストラップ清掃 2025-03")
        self._load_button = QPushButton("プロジェクト読込")
        self._load_button.clicked.connect(self._load_project)
        self._delete_button = QPushButton("プロジェクト削除")
        self._delete_button.clicked.connect(self._delete_project)

        project_actions = QHBoxLayout()
        project_actions.addWidget(self._load_button)
        project_actions.addWidget(self._delete_button)
        project_actions.addStretch()

        # 保存先は Step 1 で見せておき、以後のプロジェクトでも再利用できるユーザー設定として扱う。
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setReadOnly(True)
        self._output_dir_edit.setText(str(load_default_output_dir()))

        # PDF 生成成功後に閉じるかどうかも、保存先と同じく「ユーザーごとの既定値」として扱う。
        # report ごとに一時的な選択ではなく、次回起動時にも引き継ぐ前提で preset_manager へ保存する。
        self._close_after_generation_check = QCheckBox("PDF生成後にアプリを閉じる")
        self._close_after_generation_check.setChecked(load_close_after_pdf_generation())
        self._close_after_generation_check.toggled.connect(self._save_close_after_generation_preference)

        browse_button = QPushButton("参照...")
        browse_button.clicked.connect(self._choose_output_directory)

        output_dir_row = QHBoxLayout()
        output_dir_row.addWidget(self._output_dir_edit, 1)
        output_dir_row.addWidget(browse_button)

        output_hint = QLabel("未設定時は Desktop を使い、利用できない場合はプロジェクトルートへ保存します。")
        output_hint.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("プロジェクト名"))
        layout.addWidget(self._name_edit)
        layout.addLayout(project_actions)
        layout.addWidget(QLabel("PDF 保存先フォルダ"))
        layout.addLayout(output_dir_row)
        layout.addWidget(output_hint)
        layout.addWidget(self._close_after_generation_check)
        layout.addStretch()
        self.setLayout(layout)

        # フィールド名の末尾 "*" は QWizard の必須フィールド指定
        # → 空欄のままでは「次へ」ボタンが押せなくなる
        self.registerField("project_name*", self._name_edit)
        self.registerField("output_dir", self._output_dir_edit)
        self.registerField("close_after_pdf_generation", self._close_after_generation_check)

    def output_directory(self) -> Path:
        """現在 UI に表示している保存先フォルダを返す。"""

        return Path(self._output_dir_edit.text())

    def close_after_pdf_generation(self) -> bool:
        """成功後にアプリを閉じる設定値を返す。"""

        return self._close_after_generation_check.isChecked()

    def set_project_name(self, project_name: str) -> None:
        self._name_edit.setText(project_name)

    def _choose_output_directory(self) -> None:
        """保存先フォルダ選択ダイアログを開き、選択結果を永続化する。"""

        current_dir = self._output_dir_edit.text() or str(load_default_output_dir())
        selected_dir = QFileDialog.getExistingDirectory(self, "PDF 保存先フォルダを選択", current_dir)
        if not selected_dir:
            return

        try:
            resolved_dir = save_default_output_dir(selected_dir)
        except ValueError:
            # 永続化層の妥当性検査結果を、そのまま GUI の警告へ変換するだけに留める。
            QMessageBox.warning(self, "保存先エラー", "指定したフォルダは使用できません。")
            return

        self._output_dir_edit.setText(str(resolved_dir))

    def _save_close_after_generation_preference(self, checked: bool) -> None:
        """成功後の終了設定を永続化する。

        registerField 済みなので wizard 内の field 値は Qt が同期してくれるが、
        次回起動時の既定値には別途保存が必要なため、UI 変更のたびに即時永続化する。
        """

        save_close_after_pdf_generation(checked)

    def _wizard(self) -> ReportWizard:
        from work_report_maker.gui.main_window import ReportWizard

        return cast(ReportWizard, self.wizard())

    def _load_project(self) -> None:
        project_name = self._select_project_name(
            title="プロジェクト読込",
            label="読込するプロジェクトを選択してください",
        )
        if project_name is None:
            return
        if not self._wizard().load_project_named(project_name):
            return
        self._wizard().next()

    def _delete_project(self) -> None:
        project_name = self._select_project_name(
            title="プロジェクト削除",
            label="削除するプロジェクトを選択してください",
        )
        if project_name is None:
            return

        answer = QMessageBox.question(
            self,
            "削除確認",
            f"プロジェクト「{project_name}」を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._wizard().delete_project_named(project_name)

    def _select_project_name(self, *, title: str, label: str) -> str | None:
        names = list_project_names()
        if not names:
            QMessageBox.information(self, title, "保存済みプロジェクトがありません。")
            return None
        selected_name, accepted = QInputDialog.getItem(self, title, label, names, 0, False)
        if not accepted or not selected_name:
            return None
        return selected_name
