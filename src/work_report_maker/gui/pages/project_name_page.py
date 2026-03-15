"""ウィザード Step 1: プロジェクト名入力ページ。

ユーザーにプロジェクト名を入力してもらう。
のちにプロジェクトの保存機能を追加する際、この名前がファイル名等の識別子となる想定。
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWizardPage


class ProjectNamePage(QWizardPage):
    """プロジェクト名入力用のウィザードページ。

    - QLineEdit でプロジェクト名を入力
    - registerField("project_name*", ...) により必須フィールドとして登録
      → 空欄のままでは「次へ」ボタンが無効化される

    このページの責務は入力値の妥当性検査ではなく、以降のページや保存機能が参照する
    識別子を 1 つ確定させることにある。詳細な保存形式やファイル名変換はここでは扱わない。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("プロジェクト名")
        self.setSubTitle("報告書プロジェクトの名前を入力してください。")

        # プロジェクト名入力フィールド
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("例: ロワジールホテル グリストラップ清掃 2025-03")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("プロジェクト名"))
        layout.addWidget(self._name_edit)
        layout.addStretch()
        self.setLayout(layout)

        # フィールド名の末尾 "*" は QWizard の必須フィールド指定
        # → 空欄のままでは「次へ」ボタンが押せなくなる
        self.registerField("project_name*", self._name_edit)
