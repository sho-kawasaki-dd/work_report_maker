"""ウィザード Step 2: 表紙情報フォームページ。

報告書の表紙に記載する以下の項目を入力する:
    (1) 報告書作成年月日  — QDateEdit（カレンダーポップアップ付き）
    (2) 提出先            — QLineEdit + 「御中」自動付与
    (3) 工事・作業名      — QLineEdit（出力時に末尾へ「完了報告書」を自動付与）
    (4) 作業場所名        — QLineEdit（テンプレートの subtitle に対応）
    (5) 建物名            — QLineEdit（建物プリセットから呼び出し可能）
    (6) 住所              — QLineEdit（建物プリセットから呼び出し可能）
    (7) 日時              — 開始日 QDateEdit + 終了日 QDateEdit（期間指定チェックボックス）

また、建物プリセットの読込/保存ボタンと、会社情報編集ボタンを配置する。
"""

from __future__ import annotations

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWizardPage,
)

from work_report_maker.gui.dialogs.building_preset_dialog import BuildingPresetDialog
from work_report_maker.gui.dialogs.company_editor_dialog import CompanyEditorDialog
from work_report_maker.gui.preset_manager import add_building_preset

# 日本語ロケール（将来的にロケール依存の書式が必要になった場合に使用）
_JA_LOCALE = QLocale(QLocale.Language.Japanese, QLocale.Country.Japan)

# QDate.dayOfWeek() の戻り値 (1=月曜 ～ 7=日曜) を日本語曜日に変換するマップ
_WEEKDAY_MAP: dict[int, str] = {
    1: "月",
    2: "火",
    3: "水",
    4: "木",
    5: "金",
    6: "土",
    7: "日",
}


def _format_date_jp(date: QDate) -> str:
    """日付を ``'2025年 3月 27日'`` 形式の文字列に変換する。

    報告書作成年月日など、曜日を含まない用途に使用。
    """
    return f"{date.year()}年 {date.month()}月 {date.day():02d}日"


def _format_date_with_dow(date: QDate) -> str:
    """日付を ``'2025年 3月 27日(木)'`` 形式の文字列に変換する。

    表紙の「日時」欄で使用。曜日は _WEEKDAY_MAP から取得する。
    """
    dow = _WEEKDAY_MAP.get(date.dayOfWeek(), "")
    return f"{_format_date_jp(date)}({dow})"


class CoverFormPage(QWizardPage):
    """表紙情報入力用のウィザードページ。

    フォーム項目:
        (1) 報告書作成年月日 — QDateEdit (カレンダーポップアップ、デフォルト=今日)
        (2) 提出先          — QLineEdit + 右端に「御中」ラベルを固定表示
        (3) 工事・作業名    — QLineEdit (出力時に末尾へ「完了報告書」を自動付与)
        (4) 作業場所名      — QLineEdit (テンプレートの subtitle に対応)
        (5) 建物名          — QLineEdit
        (6) 住所            — QLineEdit
        (7) 日時 (開始日/終了日) — QDateEdit × 2 + 期間指定チェックボックス

    追加ボタン:
        - 「建物プリセット読込」→ BuildingPresetDialog を表示、選択で (2)(5)(6) を自動入力
        - 「建物プリセット保存」→ 現在の (2)(5)(6) をプリセットとして保存
        - 「会社情報編集...」  → CompanyEditorDialog を表示
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("表紙情報")
        self.setSubTitle("報告書の表紙に記載する情報を入力してください。")

        # ── (1) 報告書作成年月日 ──
        # カレンダーポップアップ付きの日付選択。デフォルトは今日の日付。
        self._report_date = QDateEdit(QDate.currentDate())
        self._report_date.setCalendarPopup(True)
        self._report_date.setDisplayFormat("yyyy/MM/dd")

        # ── (2) 提出先 ──
        # テキスト入力の右端に「御中」ラベルを配置。
        # 出力時に「○○　御中」を自動生成するため、ユーザーは「御中」を入力しなくてよい。
        self._recipient_edit = QLineEdit()
        recipient_row = QHBoxLayout()
        recipient_row.addWidget(self._recipient_edit, 1)
        recipient_row.addWidget(QLabel("御中"))

        # ── (3) 工事・作業名 ──
        # 出力時に末尾へ「完了報告書」を自動付与する。
        # 例: 入力「厨房グリストラップ清掃」→ 表紙タイトル「厨房グリストラップ清掃完了報告書」
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("例: 厨房グリストラップ清掃")

        # ── (4) 作業場所名 ──
        # テンプレート HTML の cover.subtitle に対応する項目。
        self._subtitle_edit = QLineEdit()
        self._subtitle_edit.setPlaceholderText("例: ホテル1階厨房")

        # ── (5) 建物名 ──
        self._building_edit = QLineEdit()

        # ── (6) 住所 ──
        self._address_edit = QLineEdit()

        # ── (7) 日時 ──
        # 開始日: 常に有効。カレンダーポップアップ付き。
        self._start_date = QDateEdit(QDate.currentDate())
        self._start_date.setCalendarPopup(True)
        self._start_date.setDisplayFormat("yyyy/MM/dd")

        # 「期間指定」チェックボックス: ON にすると終了日フィールドが有効になる。
        # OFF の場合は開始日のみの単日表示 (例: "2025年 3月 27日(木)")、
        # ON の場合は期間表示 (例: "2025年 3月 27日(木) ～ 2025年 3月 29日(土)") になる。
        self._range_check = QCheckBox("期間指定")
        self._end_date = QDateEdit(QDate.currentDate())
        self._end_date.setCalendarPopup(True)
        self._end_date.setDisplayFormat("yyyy/MM/dd")
        self._end_date.setEnabled(False)  # デフォルトは無効 (単日モード)
        # チェックボックスの ON/OFF に連動して終了日フィールドの有効/無効を切り替え
        self._range_check.toggled.connect(self._end_date.setEnabled)

        # 日時欄のレイアウト: 開始日 | 期間指定チェック | 終了日 を横並び
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("開始日"))
        date_row.addWidget(self._start_date)
        date_row.addWidget(self._range_check)
        date_row.addWidget(QLabel("終了日"))
        date_row.addWidget(self._end_date)
        date_row.addStretch()

        # ── 建物プリセット ボタン ──
        # 「読込」: 保存済みプリセット一覧ダイアログを表示し、選択で提出先・建物名・住所を自動入力
        btn_preset_load = QPushButton("建物プリセット読込")
        btn_preset_load.clicked.connect(self._load_building_preset)
        # 「保存」: 現在入力中の提出先・建物名・住所をプリセットとして保存
        btn_preset_save = QPushButton("建物プリセット保存")
        btn_preset_save.clicked.connect(self._save_building_preset)

        preset_btn_row = QHBoxLayout()
        preset_btn_row.addWidget(btn_preset_load)
        preset_btn_row.addWidget(btn_preset_save)
        preset_btn_row.addStretch()

        # ── 会社情報 ボタン ──
        # 押下で別ウィンドウ (CompanyEditorDialog) を開き、社名・〒・住所・TEL・FAX を編集
        btn_company = QPushButton("会社情報編集...")
        btn_company.clicked.connect(self._edit_company)

        # ── レイアウト組立 ──
        # QFormLayout でラベルとフィールドを対にして配置
        form = QFormLayout()
        form.addRow("報告書作成年月日", self._report_date)
        form.addRow("提出先", recipient_row)
        form.addRow("工事・作業名", self._title_edit)
        form.addRow("作業場所名", self._subtitle_edit)
        form.addRow("建物名", self._building_edit)
        form.addRow("住所", self._address_edit)

        # 日時欄は QGroupBox で囲んで視覚的にグループ化
        date_group = QGroupBox("日時")
        date_group.setLayout(date_row)

        # 全体を縦に配置: フォーム → プリセットボタン → 日時グループ → 会社情報ボタン
        main_layout = QVBoxLayout()
        main_layout.addLayout(form)
        main_layout.addLayout(preset_btn_row)
        main_layout.addWidget(date_group)
        main_layout.addWidget(btn_company)
        main_layout.addStretch()
        self.setLayout(main_layout)

    # ── プリセット操作 ──────────────────────────────────────

    def _load_building_preset(self) -> None:
        """建物プリセット読込ダイアログを開き、選択結果をフォームに反映する。

        BuildingPresetDialog で「選択」を押すと (building_name, recipient, address) が返り、
        それぞれ建物名・提出先・住所フィールドに自動入力される。
        """
        dlg = BuildingPresetDialog(self)
        if dlg.exec() != BuildingPresetDialog.DialogCode.Accepted:
            return
        data = dlg.selected_data()
        if data is None:
            return
        building_name, recipient, address = data
        self._building_edit.setText(building_name)
        self._recipient_edit.setText(recipient)
        self._address_edit.setText(address)

    def _save_building_preset(self) -> None:
        """現在の提出先・建物名・住所をプリセットとして保存する。

        建物名が空の場合は警告を表示して中断する。
        同名の建物名が既にあれば上書きされる。
        """
        building = self._building_edit.text().strip()
        if not building:
            QMessageBox.warning(self, "保存エラー", "建物名を入力してください。")
            return
        add_building_preset(
            building_name=building,
            recipient=self._recipient_edit.text().strip(),
            address=self._address_edit.text().strip(),
        )
        QMessageBox.information(self, "保存完了", f"建物プリセット「{building}」を保存しました。")

    def _edit_company(self) -> None:
        """会社情報編集ダイアログを開く。保存はダイアログ内で完結する。"""
        CompanyEditorDialog(self).exec()

    # ── 公開アクセサ（OverviewFormPage から参照） ─────────────

    def building_name(self) -> str:
        """建物名フィールドの現在値を返す。"""
        return self._building_edit.text().strip()

    def subtitle(self) -> str:
        """作業場所名フィールドの現在値を返す。"""
        return self._subtitle_edit.text().strip()

    def title_text(self) -> str:
        """工事・作業名フィールドの現在値を返す（「完了報告書」なし）。"""
        return self._title_edit.text().strip()

    def recipient_text(self) -> str:
        """提出先フィールドの現在値を返す（「御中」なし）。"""
        return self._recipient_edit.text().strip()

    def format_start_date(self) -> str:
        """開始日だけを写真説明用の文字列として返す。"""
        return _format_date_with_dow(self._start_date.date())

    # ── データ収集 ────────────────────────────────────────

    def format_work_date(self) -> str:
        """日時欄の値をフォーマット済み文字列に変換して返す。

        期間指定 OFF: "2025年 3月 27日(木)" 形式
        期間指定 ON:  "2025年 3月 27日(木) ～ 2025年 3月 29日(土)" 形式
        """
        start = self._start_date.date()
        if self._range_check.isChecked():
            end = self._end_date.date()
            return f"{_format_date_with_dow(start)} ～ {_format_date_with_dow(end)}"
        return _format_date_with_dow(start)

    def collect_cover_data(self) -> dict:
        """フォーム入力値を ``raw_report.json`` の ``cover`` 構造に合わせた dict で返す。

        戻り値の構造は data/raw_report.json の "cover" キーと同じ形式:
            {
                "date": "2025年 3月 29日",
                "recipient": "○○　御中",
                "title": "報告書名",
                "subtitle": "作業場所名",
                "detail_rows": [{"label": "建物名", "value": ...}, ...],
                "company": { "name": ..., "postal_code": ..., ... }
            }

        提出先には自動で「　御中」(全角スペース+御中) を付与する。
        会社情報は ~/.work_report_maker/company_info.json から読み込む。
        """
        from work_report_maker.gui.preset_manager import load_company_info

        company = load_company_info()
        # 提出先に「　御中」を自動付与（空欄の場合は付与しない）
        recipient_text = self._recipient_edit.text().strip()
        if recipient_text:
            recipient_text += "　御中"

        return {
            "date": _format_date_jp(self._report_date.date()),
            "recipient": recipient_text,
            # 工事・作業名の末尾に「完了報告書」を自動付与してタイトルを生成
            "title": self._title_edit.text().strip() + "完了報告書" if self._title_edit.text().strip() else "",
            "subtitle": self._subtitle_edit.text().strip(),
            "detail_rows": [
                {"label": "建物名", "value": self._building_edit.text().strip()},
                {"label": "住　所", "value": self._address_edit.text().strip()},
                {"label": "日　時", "value": self.format_work_date()},
            ],
            "company": {
                "name": company.get("name", ""),
                "postal_code": company.get("postal_code", ""),
                "address_lines": company.get("address_lines", [""]),
                "tel_label": "TEL：",
                "tel": company.get("tel", ""),
                "fax_label": "FAX：",
                "fax": company.get("fax", ""),
            },
        }
