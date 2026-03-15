## Plan: GUI PDF Export Flow

Finish 押下時に GUI から実際の PDF 生成へ接続し、保存先は Step 1 で指定・永続化、最終ファイル名は保存ダイアログで `project_name.pdf` を初期値として提示する。PDF 本体は既存の `generate_full_report(...)` を GUI と CLI の共通バックエンドとして再利用し、その直後に pikepdf による構造最適化を挿入する。構造最適化は CLI からの PDF 生成にも適用可能とし、GUI と CLI で同じサービス層を通す。最適化では作成者・日時などのメタデータは保持し、保存先の既定値はユーザー単位 JSON として既存プリセット保存領域へ統合する。

**Steps**
1. Phase 1: 現状フローの受け口を整える
   `src/work_report_maker/gui/main_window.py` の `ReportWizard.accept()` で、現在の stderr 出力専用フローを「payload 構築 → 保存先/ファイル名確定 → PDF 生成呼び出し → 成否通知」へ置き換える設計にする。`_build_report_payload()` はそのまま再利用し、GUI 側で report_data を `services.pdf_generator.generate_full_report(...)` へ渡す。
2. Phase 2: 保存先既定値の永続化を追加する
   `src/work_report_maker/gui/preset_manager.py` に、既存の `~/.work_report_maker/` 配下 JSON 保存パターンを踏襲した PDF 出力設定の load/save API を追加する。保存項目は最低でも `default_output_dir` とし、未設定時は「デスクトップ、取得不能ならプロジェクトルート」を返す解決関数を用意する。Windows でも `Path.home() / "Desktop"` の存在確認を行い、無ければ `PROJECT_ROOT` へフォールバックする。これは Step 3 と *parallel 可能*。
3. Phase 3: Step 1 に保存先フォルダ UI を追加する
   `src/work_report_maker/gui/pages/project_name_page.py` に、現在のプロジェクト名入力欄に加えて「保存先フォルダ表示欄 + 参照ボタン + 既定値説明」を追加する。初期表示は Phase 2 の load API から取得し、ユーザーが参照ダイアログで変更したら、その場でウィザードのフィールドへ反映し、以後の別プロジェクトでも使えるよう保存する。プロジェクト名は引き続き必須、保存先フォルダは存在するディレクトリのみ受理する。これは Phase 2 に *depends on 2*。
4. Phase 4: Finish 時の保存ダイアログを設計する
   `src/work_report_maker/gui/main_window.py` で Finish 押下時に保存ダイアログを開き、初期ディレクトリは Step 1 の保存先、初期ファイル名は `project_name` を stem にした `.pdf` とする。ユーザーはここで stem を変更可能にし、キャンセル時は PDF 生成を開始しない。ファイル名として不正な文字が含まれる場合に備え、初期提案名だけ GUI 側で安全化する。これは Phase 1 と Phase 3 に *depends on 1,3*。
5. Phase 5: PDF 最適化サービスを追加する
   `src/work_report_maker/services/` に pikepdf を使う最適化処理を追加する。形としては `pdf_generator.py` 内の補助関数でも独立モジュールでもよいが、責務分離を優先するなら `pdf_optimizer.py` の新設が適切。既存の WeasyPrint 出力完了後に同一ファイルへ再保存する post-process とし、線形化または同等の構造最適化オプションを適用する。pikepdf 保存時に document info / XMP metadata を削除しない設定を明示し、GUI と CLI の両方から同じサービス層経由で呼び出せるようにして要件 (1) を満たす。これは Phase 1 に *depends on 1*。
6. Phase 6: PDF 生成サービス API を拡張する
   `src/work_report_maker/services/pdf_generator.py` の `generate_full_report(...)` に、最適化を有効化するフラグまたは内部固定動作を追加する。処理順は「render-ready 化 → WeasyPrint 出力 → pikepdf 最適化」とし、GUI と CLI の両方がこの共通バックエンドを使う前提を明記する。CLI でも同じ品質が必要なら共通で有効化し、GUI 側は保存先選択や例外表示だけを担当する。失敗時の例外境界もここで決め、GUI 側は例外を捕捉してメッセージ表示する。これは Phase 5 に *depends on 5*。
7. Phase 7: 依存関係とドキュメントを更新する
   `pyproject.toml` に `pikepdf` を追加し、必要なら `README.md` の GUI/PDF 出力説明を更新する。保存先の既定値、Finish 時の保存ダイアログ、PDF 最適化が新しい動作になるため、利用者向け説明を簡潔に追記する。これは Phase 3-6 と *parallel 可能*。
8. Phase 8: テストを追加する
   サービス層では `tests/services/test_pdf_generator.py` を拡張し、指定出力パスで PDF が生成されることに加えて、最適化後も PDF が開けること、メタデータが保持されることを確認する。GUI 層では `tests/gui/test_report_wizard_integration.py` または新規テストで、Step 1 初期保存先の読込、フォルダ変更時の保存、Finish 時に保存ダイアログへ `project_name.pdf` が初期提案されること、キャンセル時に生成しないこと、生成関数へ選択パスが渡ることを検証する。Phase 2-6 に *depends on 2-6*。

**Relevant files**
- `c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\main_window.py` — `ReportWizard.accept()` と `_build_report_payload()` を GUI 完了から実生成フローへ接続する中心点
- `c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\project_name_page.py` — プロジェクト名に加えて保存先フォルダ選択 UI を追加するページ
- `c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\preset_manager.py` — 既存の `~/.work_report_maker/` JSON 永続化パターンを再利用して既定保存先を保持
- `c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\services\pdf_generator.py` — WeasyPrint 出力後に最適化をつなぐ既存エントリポイント
- `c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\config.py` — プロジェクトルート fallback と既定出力パス定数の見直し候補
- `c:\Users\tohbo\python_programs\work_report_maker\tests\gui\test_report_wizard_integration.py` — Finish フローとウィザード連携の回帰テスト候補
- `c:\Users\tohbo\python_programs\work_report_maker\tests\services\test_pdf_generator.py` — 最適化込みの PDF 出力テスト候補
- `c:\Users\tohbo\python_programs\work_report_maker\pyproject.toml` — pikepdf 依存追加
- `c:\Users\tohbo\python_programs\work_report_maker\README.md` — 新しい GUI 保存動作の説明追記候補

**Verification**
1. GUI テストで Step 1 表示時に、未保存なら Desktop、Desktop 不可ならプロジェクトルートが表示されることを確認する。
2. GUI テストで保存先フォルダを変更したとき、次回新規ウィザード起動でもその値が初期表示されることを確認する。
3. GUI テストで Finish 押下時に保存ダイアログの初期値が `プロジェクト名.pdf` になり、ユーザー変更後の最終パスが `generate_full_report(...)` に渡ることを確認する。
4. GUI テストで保存ダイアログをキャンセルした場合、PDF 生成も設定更新も不要な副作用を起こさないことを確認する。
5. サービステストで GUI・CLI 共通の `generate_full_report(...)` から生成された PDF を pikepdf で再度開けること、ファイルサイズが 0 より大きいこと、既存メタデータが消えていないことを確認する。
6. 実機確認として Windows で `uv run python -m work_report_maker --gui` を起動し、Step 7 完了から PDF が Desktop または指定フォルダへ保存されることを確認する。

**Decisions**
- ファイル名変更 UI は Step 1 ではなく Finish 時の保存ダイアログで扱う。Step 1 は保存先フォルダの既定値管理に限定する。
- 保存先既定値はユーザー単位設定として `~/.work_report_maker/` 配下 JSON に保存する。プロジェクトごとの設定分離は今回のスコープ外。
- PDF 最適化は WeasyPrint の後段処理として services 層に追加し、GUI と CLI は同じバックエンドを共有する。GUI 側は保存先選択とエラー表示だけを担い、最適化の詳細は services 層へ閉じ込める。
- メタデータ保持は必須要件とし、最適化実装では「削除しない」ことをテストで固定する。

**Further Considerations**
1. `config.OUTPUT_PDF` は CLI の既定値として残してよいが、GUI の保存ダイアログ導入後は GUI 側で直接使わない設計に寄せるのが自然。
2. pikepdf の最適化内容は「linearize を主目的とする構造最適化」で十分か、さらに object stream / recompress を触るかを実装時に確認する。要件上は metadata 非破壊が最優先。
