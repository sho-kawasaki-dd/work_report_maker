## Plan: GUI Source Self-Documentation

既存実装の責務分割は概ね明確だが、レビュー時に読み解きコストが高い箇所が GUI の写真ワークフロー、ページ間の暗黙依存、raw JSON から PDF までの変換境界、Windows 向け WeasyPrint 初期化に集中している。日本語ベースで必要語のみ英語を残し、モジュール／クラス／関数の docstring、複雑処理前のブロックコメント、分岐や副作用の意図を示す短い行内コメントを併用して、why・前提条件・不変条件・副作用を補う方針で自己文書化する。

**Steps**
1. Phase 1: コメント方針と優先度を固定する。コメントを 3 種別に分ける: module/class/function docstring は責務・入出力・依存先・ライフサイクルを説明し、block comment は状態遷移やアルゴリズム全体を説明し、inline comment は副作用・分岐理由・ Qt 上の回避策だけに限定する。 trivial な getter/setter や見ればわかる UI 配線にはコメントを増やさない。これは後続全工程の基準になる。
2. Phase 2: 起動経路とウィザード統合層を自己文書化する。対象は c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\__main__.py、gui\main_window.py、gui\wizard_contexts.py、gui\report_build_helper.py、必要に応じて config.py。ここでは CLI/GUI 二系統の起動、ReportWizard が各ページを束ねる責務、Cover 情報が Overview/WorkContent/Photo defaults へ伝播する契約、写真一時ディレクトリの所有者と寿命、WizardPhotoContext によるページ疎結合の意図を明示する。 Step 1 に依存。
3. Phase 3A: 写真モデルとインポート系を自己文書化する。対象は gui\pages\photo_models.py、photo_import_page.py、photo_import_operation.py、photo_import_controls.py。PhotoItem が id ベースの同一性で扱われる前提、初期既定値注入とユーザー編集済み項目の区別、force=True の意味、バッチ import と失敗収集の設計、UI 操作値と実際の圧縮パラメータの関係を説明する。 Step 2 と並行可能だが、WizardPhotoContext 側の説明と語彙を揃えること。
4. Phase 3B: 写真並び替え系を自己文書化する。対象は gui\pages\photo_arrange_page.py、photo_arrange_logic.py、photo_arrange_icons.py、gui\widgets\photo_arrange_view.py。 initializePage() の 3-way state reconciliation、_photo_items_by_key と UserRole キーの分離、drag and drop と矢印移動が最終的に同じ移動計画へ収束する構造、ズーム変更時の signal recursion 回避、単一倍率キャッシュの意図、3 枚ごとのページ境界描画の役割をブロックコメント中心で補強する。 Step 3A と並行可能。
5. Phase 3C: 写真説明系を自己文書化する。対象は gui\pages\photo_description_page.py、photo_description_navigation.py、photo_description_focus.py、photo_description_dates.py。 current photo と focused photo の違い、表示モード 1/2/4 に応じた visible range の決定、PageUp/PageDown と移動ボタンとフォーカスイベントの統合、編集ブロックが focus_received を発火する理由、日付文字列の許容形式を説明する。 Step 3A と並行可能だが、Arrange 側の同一性キー設計と用語を一致させるため Step 3B の方針を参照する。
6. Phase 4: フォーム・プリセット・ダイアログ層を補う。対象は gui\pages\project_name_page.py、cover_form_page.py、overview_form_page.py、work_content_page.py、gui\preset_manager.py、gui\dialogs\building_preset_dialog.py、gui\dialogs\company_editor_dialog.py。 Cover ページが他ページの既定値源である点、 building preset と company info の保存責務、WorkContent のグループ/サブグループ構造と collect 系メソッドの返却契約、各ダイアログがどの永続化 API を前提にしているかをまとめる。 Step 2 の後が望ましい。
7. Phase 5: データ読込・検証・変換・ PDF 生成層を自己文書化する。対象は models\loader.py、models\validator.py、services\report_adapter.py、services\pdf_generator.py、services\image_processor.py。 raw と render-ready の 2 フォーマット境界、 detect_report_format() の排他条件、 validator の責務が型検査であり業務妥当性までは保証しない点、 _wrap_text() の切り詰め仕様、 _build_writing_block() の文字数閾値とフォントサイズ選定、 _chunk_photos() の page_break_after を pop する副作用、 _resolve_photo_uri() の存在しないファイル時の None 返却、 _get_html_class() の Windows 依存な遅延初期化を明文化する。 Step 2 と並行可能。
8. Phase 6: コメントの一貫性レビューを行う。対象全体を横断して、同じ概念を同じ語彙で説明できているか、主語が曖昧でないか、仕様コメントと実装がずれていないか、コメントが what の言い換えに落ちていないかを確認する。特に PhotoItem の identity、default synchronization、raw/report-ready 変換、temp directory ownership の 4 概念は重複説明を揃える。 Step 3A-5 完了後に実施。
9. Phase 7: 検証を行う。 pytest で tests\gui\test_photo_arrange_page.py、tests\gui\test_photo_import_page.py、tests\gui\test_photo_description_page.py、tests\gui\test_report_wizard_integration.py、tests\services\test_pdf_generator.py を実行し、コメント追記でコード動作に影響がないことを確認する。加えてレビュー観点で、人手で主要 docstring が次の問いに答えているかを確認する: この関数は何を所有するか、何を前提にするか、どの副作用があるか、なぜその実装にしているか。

**Relevant files**
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\__main__.py — CLI/GUI 二系統の起動方針
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\config.py — WeasyPrint 実行環境の前提説明
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\main_window.py — ReportWizard のページ統合、closeEvent、accept、payload 生成
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\wizard_contexts.py — ページ間共有状態と Protocol ベースの疎結合
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\report_build_helper.py — raw payload と一時ファイルの生成契約
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\preset_manager.py — JSON 永続化の責務分離
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\project_name_page.py — 最小入力ページの登録契約
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\cover_form_page.py — 他ページ既定値の source of truth
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\overview_form_page.py — Cover 由来既定値の取り込み契約
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\work_content_page.py — collect_work_groups() の返却構造
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_models.py — PhotoItem の identity と default sync
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_import_page.py — 写真取込全体フロー
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_import_operation.py — worker thread と batch emission
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_import_controls.py — UI パラメータの意味
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_arrange_page.py — Arrange 状態同期とキー管理
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_arrange_logic.py — 行移動アルゴリズム
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_arrange_icons.py — アイコン生成キャッシュ
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_description_page.py — current/focused/visible の状態遷移
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_description_navigation.py — 表示窓と移動判定の純粋関数
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_description_focus.py — focused photo 解決規則
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_description_dates.py — 日付解析／整形ルール
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\widgets\photo_arrange_view.py — view 専用イベント処理と custom signal
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\models\loader.py — 入力 JSON 判定と path 解決
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\models\validator.py — スキーマ検証境界
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\services\report_adapter.py — raw から render-ready への変換ロジック
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\services\pdf_generator.py — render 前処理と WeasyPrint 実行
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\services\image_processor.py — 画像変換・圧縮・外部ツール fallback

**Verification**
1. pytest で GUI と services の既存テストを実行し、コメント追加だけで構文や import 順序が崩れていないことを確認する。
2. 主要箇所のレビューを実施する。最低でも ReportWizard、PhotoArrangePage.initializePage()、PhotoDescriptionPage._sync_focused_photo()、PhotoItem.sync_description_defaults()、report_adapter._build_writing_block()、pdf_generator._get_html_class() について、コメントが why・前提条件・副作用・失敗時挙動を説明しているかを確認する。
3. コメント密度を確認する。 1-3 行で済む単純処理に冗長コメントを足していないか、逆に複雑な状態同期や mutation を無説明で残していないかを横断確認する。
4. 用語統一を確認する。 PhotoItem identity、focused/current photo、raw report、render-ready report、temporary photo directory、default sync の表現を全ファイルで揃える。

**Decisions**
- コメント言語は日本語を基本にし、 API 名・ Qt 用語・ MIME type など必要最小限だけ英語を残す。
- 自己文書化の対象は src\work_report_maker 全体とし、 dependencies、templates、tests、__pycache__ は変更対象外とする。ただし tests は意図確認の参照元として使う。
- コメントは短さより正確さを優先するが、実装の逐語説明は避け、レビュー時に読者が判断材料を得られる情報に限定する。
- 既存 docstring が十分な箇所は全面書き換えではなく補強に留め、過剰な churn を避ける。

**Further Considerations**
1. 実作業時はまず gui\main_window.py と gui\wizard_contexts.py で共有語彙を定義してから写真系ページへ入ると、後続コメントの重複と語彙ぶれを抑えやすい。
2. report_adapter.py は magic number の由来がコードからは読めないため、仕様根拠が不明なら根拠不明の断定は避け、現行動作の選択規則とトレードオフを事実ベースで記述する.
