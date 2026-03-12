"""会社情報編集ダイアログ。

報告書表紙の下部に記載する会社情報（社名・郵便番号・住所・TEL・FAX）を
編集して ~/.work_report_maker/company_info.json に保存するダイアログ。

ダイアログ起動時に既存の保存データがあれば自動的にフォームにロードされる。
「保存」ボタンで JSON に書き出し、「キャンセル」で変更を破棄する。
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from work_report_maker.gui.preset_manager import load_company_info, save_company_info


class CompanyEditorDialog(QDialog):
    """会社情報を編集・保存するダイアログ。

    フィールド:
        - 社名       (QLineEdit)
        - 郵便番号   (QLineEdit)  例: 〒600-8413
        - 住所       (QTextEdit)  複数行入力可。改行ごとに address_lines の要素に分割される。
        - TEL        (QLineEdit)
        - FAX        (QLineEdit)
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("会社情報編集")
        self.setMinimumWidth(460)

        # 各入力フィールドの初期化
        self._name_edit = QLineEdit()
        self._postal_edit = QLineEdit()
        self._postal_edit.setPlaceholderText("〒000-0000")
        # 住所は複数行入力に対応するため QTextEdit を使用
        self._address_edit = QTextEdit()
        self._address_edit.setFixedHeight(72)
        self._address_edit.setPlaceholderText("住所（複数行可）")
        self._tel_edit = QLineEdit()
        self._tel_edit.setPlaceholderText("000-000-0000")
        self._fax_edit = QLineEdit()
        self._fax_edit.setPlaceholderText("000-000-0000")

        # QFormLayout でラベルとフィールドを対にして配置
        form = QFormLayout()
        form.addRow("社名", self._name_edit)
        form.addRow("郵便番号", self._postal_edit)
        form.addRow("住所", self._address_edit)
        form.addRow("TEL", self._tel_edit)
        form.addRow("FAX", self._fax_edit)

        # 操作ボタン
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # ダイアログ表示時に既存の会社情報をフォームにロード
        self._load_existing()

    def _load_existing(self) -> None:
        """保存済みの会社情報を JSON から読み込み、各フィールドにセットする。

        ファイルが存在しない場合はすべて空欄のまま表示される。
        """
        info = load_company_info()
        self._name_edit.setText(info.get("name", ""))
        self._postal_edit.setText(info.get("postal_code", ""))
        # address_lines (リスト) を改行で結合して QTextEdit に表示
        lines = info.get("address_lines", [""])
        self._address_edit.setPlainText("\n".join(lines))
        self._tel_edit.setText(info.get("tel", ""))
        self._fax_edit.setText(info.get("fax", ""))

    def _on_save(self) -> None:
        """「保存」ボタン押下時の処理。

        フォームの入力値を dict にまとめ、preset_manager.save_company_info() で
        JSON ファイルに書き出した後、ダイアログを Accepted で閉じる。

        住所欄は改行で分割し、空行を除外して address_lines リストに変換する。
        """
        address_text = self._address_edit.toPlainText().strip()
        # 改行で分割し、空行を除外。全体が空の場合は [""] (空文字列1要素) にする
        address_lines = [line for line in address_text.split("\n") if line] if address_text else [""]
        info = {
            "name": self._name_edit.text().strip(),
            "postal_code": self._postal_edit.text().strip(),
            "address_lines": address_lines,
            "tel": self._tel_edit.text().strip(),
            "fax": self._fax_edit.text().strip(),
        }
        save_company_info(info)
        self.accept()
