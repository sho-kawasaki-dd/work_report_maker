# Plan: 工事概要ページ GUI 制作

テンプレート2枚目「工事完了報告書（概要）」の入力GUIをウィザード Step 3 として追加する。表紙と重複する4項目は CoverFormPage から自動取得し、施工担当と作業内容グループを新規入力UI、company_lines は会社情報から自動導出する。

---

### Phase 1: OverviewFormPage の新規作成

1. `src/work_report_maker/gui/pages/overview_form_page.py` を新規作成 — `QWizardPage` を継承した `OverviewFormPage` クラス。`initializePage()` で CoverFormPage の値を取得して自動入力欄に反映

2. **自動入力欄（読み取り専用表示）** を配置:
   - 施工対象・名称 → QLabel（CoverFormPage `_building_edit` の値）
   - 施工場所 → QLabel（CoverFormPage `_subtitle_edit` の値）
   - 施工内容 → QLabel（CoverFormPage `_title_edit` の値、「完了報告書」**なし**）
   - 施工日時 → QLabel（CoverFormPage `format_work_date()` の値）
   - QFormLayout で「表紙から流用」セクションとして表示

3. **施工担当** 入力欄:
   - QTextEdit（高さ2行制限）
   - 1行目 → `info_rows[4].value`、2行目以降 → `info_rows[4].extra_values`
   - プレースホルダー例: `"現場責任者　川崎　潤\n現場作業者　他 2 名"`

4. **作業内容グループ** セクション（QGroupBox「作業内容」）:
   - **先頭グループ（固定ヘッダ）**: marker=`"◎"`、title=工事・作業名（自動設定）、lines → QTextEdit で自由入力（改行区切り）
   - **追加グループ**: 「グループ追加」ボタンで動的追加。各グループに marker QLineEdit + title QLineEdit + lines QTextEdit + 「削除」ボタン
   - **サブグループ（1階層まで）**: 各追加グループ内に「サブグループ追加」ボタン。サブグループも marker QLineEdit + title QLineEdit + lines QTextEdit + 「削除」ボタン
   - **marker 自動採番**: グループ追加時に `1)`, `2)`, ... を自動設定。サブグループ追加時に `1-a)`, `1-b)`, ... を自動設定。QLineEdit なのでユーザーが手動で自由に変更可能
   - **collect 時のフラット展開**: GUI上の親子構造を `work_groups` のフラットなリストに展開する（親→子の順）。入れ子の階層はmarker文字列で表現されるだけで、テンプレートHTML側の変更は不要
   - 内部で `list[dict]` 管理（子グループは親の `children` キーに格納） → collect時にフラット展開して `work_groups` 形式へ変換

5. **`collect_overview_data()`** メソッド実装:
   - CoverFormPage の値 + 新規入力値から `raw_report.json` の `overview` 構造を dict で返す
   - `company_lines` は `preset_manager.load_company_info()` から自動導出（住所・社名・TEL・FAX）
   - 固定値: `title="工 事 完 了 報 告 書"`, `work_section_title="作業内容"`, `note_line="※ 仕上り品質報告書 『別紙写真参照』"`, `ending="以上"`, `blank_line_count=12`

### Phase 2: ウィザードへの統合 (*depends on Phase 1*)

6. `src/work_report_maker/gui/main_window.py` を更新:
   - `OverviewFormPage` を import し Step 3 として `addPage()`
   - `accept()` で `collect_overview_data()` を呼び、出力 JSON に `overview` キーを追加

### Phase 3: CoverFormPage のアクセサ追加 (*parallel with Phase 1*)

7. `src/work_report_maker/gui/pages/cover_form_page.py` に公開アクセサを追加:
   - `building_name() -> str` / `subtitle() -> str` / `title_text() -> str`（「完了報告書」なしの生テキスト）/ `format_work_date() -> str`（既存）
   - OverviewFormPage から `self.wizard()._cover_page.building_name()` 等で参照

---

### Relevant files
- `src/work_report_maker/gui/pages/overview_form_page.py` — **新規作成**: OverviewFormPage 全体
- `src/work_report_maker/gui/pages/cover_form_page.py` — 公開アクセサ 3件追加
- `src/work_report_maker/gui/main_window.py` — Step 3 追加 + accept() 拡張
- `src/work_report_maker/gui/preset_manager.py` — `load_company_info()` 参照のみ（変更なし）
- `data/raw_report.json` — overview 構造の仕様リファレンス（変更なし）
- `templates/report_tmp.html` — overview-page Jinja 構造リファレンス（変更なし）

### Verification
1. ウィザード起動 → Step 1→2→3 と遷移可能か
2. Step 2 入力値（建物名・作業場所名・工事作業名・日時）が Step 3 に自動反映されるか
3. Step 2 に戻って値変更 → 再度 Step 3 で更新されるか
4. 施工担当2行入力 → `collect_overview_data()` の `info_rows[4]` に `value` / `extra_values` 正しく入るか
5. 作業内容グループの追加・削除・編集が動作するか
6. 「完了」時の stderr JSON に `overview` セクションが含まれ、`raw_report.json` の構造と一致するか

### Decisions
- `overview.title` は `"工 事 完 了 報 告 書"` 固定（GUI入力なし）
- `note_line` / `ending` / `blank_line_count` / `work_section_title` はデフォルト値固定
- `company_lines` は会社情報 JSON から自動導出
- CoverFormPage アクセスは wizard インスタンス経由の直接参照
- 先頭作業グループの marker=`"◎"` / title=工事・作業名 は固定（自動設定）
