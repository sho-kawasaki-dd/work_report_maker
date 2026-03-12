# Plan: PySide6 GUI — プロジェクト名入力 & 表紙フォーム（Phase 1）

PySide6 でウィザード形式の GUI を追加し、「プロジェクト名入力」→「表紙情報フォーム」の 2 ステップと、建物プリセット・会社情報プリセットの保存/呼び出し機能を実装する。プリセットは `~/.work_report_maker/` に JSON で永続化する。

---

### Phase A: 基盤セットアップ

1. **pyproject.toml に `PySide6 >=6.6` を追加**
2. **GUI パッケージ構造を新規作成** — `src/work_report_maker/gui/` 以下に9ファイル
3. **GUI エントリーポイントを追加** — `__main__.py` に `--gui` フラグ等

### Phase B: プリセット管理基盤

4. **`gui/preset_manager.py`** — プリセット永続化ロジック
   - 保存先: `~/.work_report_maker/`
   - `building_presets.json`: 複数保存可。建物名 (`building_name`) をキーにした dict 形式:
     ```json
     { "ロワジールホテル …": { "recipient": "…", "address": "…" }, … }
     ```
     - `building_name` が一意キー（一覧表示・検索・上書きの単位）
     - `recipient` は「御中」を含まない純粋名。表示時に自動付与
     - `address` は住所
   - `company_info.json`: `{name, postal_code, address_lines, tel, fax}`
   - 関数: `load_building_presets()`, `save_building_presets()`, `add_building_preset(building_name, recipient, address)`, `delete_building_preset(building_name)`, `load_company_info()`, `save_company_info()`

### Phase C: ウィザード UI

5. **`gui/main_window.py`** — `QWizard` ベースのメインウィンドウ（ページ順: ProjectNamePage → CoverFormPage）

6. **`gui/pages/project_name_page.py`** — Step 1: プロジェクト名入力
   - `QWizardPage` + `QLineEdit`（必須フィールド登録 → 空なら「次へ」無効化）

7. **`gui/pages/cover_form_page.py`** — Step 2: 表紙情報フォーム
   - `QFormLayout` ベースで以下のフィールド:
     - **(1) 報告書作成年月日**: `QDateEdit` (カレンダーポップアップ, デフォルト=今日)
     - **(2) 提出先**: `QLineEdit` + 右に「御中」固定ラベル
     - **(3) 報告書名**: `QLineEdit`
     - **(4) 作業場所名**: `QLineEdit` (テンプレートの `subtitle`)
     - **(5) 建物名**: `QLineEdit`
     - **(6) 住所**: `QLineEdit`
     - **(7) 日時 — 開始日**: `QDateEdit` + **終了日**: `QDateEdit` + `QCheckBox` "期間指定" で有効切替
   - 日時フォーマット:
     - 開始日のみ → `"2025年 3月 27日(木)"`
     - 期間指定 → `"2025年 3月 27日(木) ～ 2025年 3月 29日(土)"`
   - 「建物プリセット読込/保存」「会社情報編集」ボタン付き

### Phase D: ダイアログ (*step 7 と並行実装可*)

8. **`gui/dialogs/building_preset_dialog.py`** — 建物プリセット管理
   - `QListWidget` で一覧表示 → 選択で (recipient, building_name, address) を返す → フォーム自動入力
   - 「削除」ボタンでプリセット除去

9. **`gui/dialogs/company_editor_dialog.py`** — 会社情報編集
   - フィールド: 社名, 〒, 住所 (複数行), TEL, FAX
   - 保存で `company_info.json` に永続化

### Phase E: データ接続

10. **ウィザード完了時のデータ収集**
    - フォームデータを `raw_report.json` の `cover` 構造に合わせた dict に変換
    - Phase 1 ではコンソール出力で確認。PDF 生成連携は後続フェーズ

---

### 新規作成ファイル

| ファイル | 役割 |
|---|---|
| `src/work_report_maker/gui/__init__.py` | パッケージ |
| `src/work_report_maker/gui/main_window.py` | QWizard メインウィンドウ |
| `src/work_report_maker/gui/pages/__init__.py` | パッケージ |
| `src/work_report_maker/gui/pages/project_name_page.py` | プロジェクト名入力ページ |
| `src/work_report_maker/gui/pages/cover_form_page.py` | 表紙フォームページ |
| `src/work_report_maker/gui/dialogs/__init__.py` | パッケージ |
| `src/work_report_maker/gui/dialogs/building_preset_dialog.py` | 建物プリセットダイアログ |
| `src/work_report_maker/gui/dialogs/company_editor_dialog.py` | 会社情報編集ダイアログ |
| `src/work_report_maker/gui/preset_manager.py` | プリセット永続化 |

### 既存ファイル変更

- `pyproject.toml` — PySide6 依存追加
- `src/work_report_maker/__main__.py` — GUI 起動パス追加

### リファレンス

- `data/raw_report.json` — `cover` セクションの構造
- `templates/report_tmp.html` — テンプレート変数 `report.cover.*`
- `src/work_report_maker/config.py` — `PROJECT_ROOT` などパス定義の再利用

---

### Verification

1. `pip install -e .` で PySide6 含む依存が入ること
2. GUI ウィザードが起動し、プロジェクト名が空なら「次へ」が無効化されること
3. 日時フォーマット: 開始日のみ → `"2025年 3月 27日(木)"` / 期間指定 → `"…(木) ～ …(土)"` 形式
4. 建物プリセットの保存・読込・削除が `~/.work_report_maker/building_presets.json` で機能すること
5. 会社情報の編集・保存が `~/.work_report_maker/company_info.json` で機能すること
6. ウィザード完了時にコンソールへ収集データ dict を出力し、`raw_report.json` の cover 構造と一致すること

---

### Decisions

- **ウィザード形式** (ユーザー選択)
- **プリセット保存先**: `~/.work_report_maker/` (ユーザーホーム)
- **提出先と建物名は別データ**: プリセットに `recipient` (御中なし) と `building_name` を別フィールドで保持
- **Phase 1 スコープ**: GUI表示・フォーム入力・プリセット管理まで。PDF 生成連携・写真台帳は後続フェーズ
- **プロジェクト保存**: 将来的に表紙＋写真台帳すべてを保存する想定。Phase 1 では未実装だがデータモデルは拡張可能に設計
