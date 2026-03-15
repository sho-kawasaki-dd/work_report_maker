## Plan: GUI Project Save Delete

プロジェクト保存を `~/.work_report_maker/` 配下の永続データとして追加し、保存は任意操作として扱う。保存ボタンは表紙内容入力ページに入った時点で利用可能にし、既存の `preset_manager` が担っているユーザー設定永続化パターンを踏襲しつつ、プロジェクト本体は別責務に分離して、GUI は保存操作・読込反映・削除確認だけを担当させる。写真は runtime の `PhotoItem` が圧縮済み bytes を保持しているため、プロジェクト保存時に専用フォルダへ書き出し、上書き時は現在 UI に残っていない写真を差分削除する。

**Steps**
1. 永続化仕様を定義する。`~/.work_report_maker/` 直下にプロジェクト用ディレクトリを切り、1 プロジェクト 1 フォルダの命名規約、メタデータ JSON のキー、写真保存サブフォルダ、バージョンフィールド、同名上書き時の確認フローを決める。
2. 新規の project 永続化モジュールを [src/work_report_maker/gui](src/work_report_maker/gui) 配下へ追加する。責務は `list/load/save/delete` とし、既存の [src/work_report_maker/gui/preset_manager.py](src/work_report_maker/gui/preset_manager.py) のように `Path.home() / ".work_report_maker"` を基点に扱うが、building/company 設定とは分離する。*Step 1 の後に着手*
3. 保存対象の wizard state を定義する。少なくとも project name、cover、overview、work groups、photo import settings、arranged photo order、各写真の説明欄、圧縮済み画像ファイル名対応を含める。`PhotoItem` は [src/work_report_maker/gui/pages/photo_models.py](src/work_report_maker/gui/pages/photo_models.py) の identity 前提を壊さないよう、復元時に新しい `PhotoItem` を再構築する。*Step 2 と並行で設計可、実装は Step 2 依存*
4. Step 1 画面の UI を拡張する。[src/work_report_maker/gui/pages/project_name_page.py](src/work_report_maker/gui/pages/project_name_page.py) には「読込」「削除」導線を追加し、これらは同ページ内で完結させる。一覧取得と選択 UI は簡潔なダイアログまたはリスト選択コンポーネントで実装する。*Step 2 依存*
5. 表紙内容入力ページの UI を拡張する。[src/work_report_maker/gui/pages/cover_form_page.py](src/work_report_maker/gui/pages/cover_form_page.py) に任意保存用のボタンを追加し、要件どおり左下へ配置する。Step 1 で project name を確定した状態で Step 2 に入った時点から保存可能とし、押下時に初回保存または確認付き上書き保存を行う。*Step 2, 3 依存*
6. ウィザード遷移時の状態連携を追加する。[src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) で Step 1 から Step 2 へ進む瞬間に project name を current project context として確定し、Cover page の保存操作が参照できるようにする。ここでは保存自体は行わず、保存可能状態への遷移とエラーハンドリングだけを担う。*Step 2, 4, 5 依存*
7. 読込処理をウィザードへ配線する。[src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) と各 page の公開 API を使って、Step 1 で選んだ保存済みプロジェクトから cover、overview、work content、photo import state、photo arrange 順序、photo description を全復元し、その後 Step 2 へ進める。必要なら各 page に「既存 state を注入する」ための最小限の setter を追加する。*Step 3, 4 依存*
8. 写真ファイルの差分保存と削除を実装する。保存時は現在 wizard 上に存在する圧縮済み `PhotoItem.data` をプロジェクト写真フォルダへ反映し、既存フォルダ内で今回の state に含まれない写真は削除する。配列順とファイル名の責務を明確に分け、順序は JSON、実ファイルは stable な保存名で管理する。*Step 2, 3 依存*
9. 削除機能を実装する。Step 1 の削除導線から対象プロジェクトフォルダを確認付きで削除し、成功後は一覧を即時更新する。削除対象が現在編集中プロジェクト名と一致する場合の UI 挙動も定義し、編集中 state は明示的に破棄するか、未読込扱いへ戻す。*Step 2, 4 依存*
10. 画面遷移と既存責務の整合を調整する。[src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) の `_confirm_project_discard()` は現在「GUI 上の未保存 state を捨てる」意味なので、保存済みプロジェクト削除とは文言と責務を分離する。あわせて「まだ保存していない編集中 state」を終了時にどう扱うか整理し、将来の未保存変更検知へ拡張しやすくする。*Step 6, 7, 9 依存*
11. テストを追加する。ProjectNamePage の読込/削除 UI、CoverFormPage の任意保存ボタン、Step 2 到達後に初めて保存可能になること、既存プロジェクト読込、上書き確認、写真差分削除、削除確認を GUI テストで押さえる。`~/.work_report_maker` 汚染を避けるため、既存メモの通り [tests/gui/test_report_wizard_integration.py](tests/gui/test_report_wizard_integration.py) では [src/work_report_maker/gui/pages/project_name_page.py](src/work_report_maker/gui/pages/project_name_page.py) の永続設定読み込み関数を monkeypatch し、プロジェクト保存先も一時ディレクトリへ差し替える。*全実装後*

**Relevant files**
- [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) — Step 1→2 の project context 確定、読込結果の wizard 全体反映、削除後の状態整理
- [src/work_report_maker/gui/pages/project_name_page.py](src/work_report_maker/gui/pages/project_name_page.py) — 読込/削除 UI、project 名入力と操作の調停
- [src/work_report_maker/gui/pages/cover_form_page.py](src/work_report_maker/gui/pages/cover_form_page.py) — 保存ボタン左下配置、保存 state の収集済み API 再利用、必要なら復元 setter 追加
- [src/work_report_maker/gui/pages/overview_form_page.py](src/work_report_maker/gui/pages/overview_form_page.py) — overview 入力値の復元 API 追加候補
- [src/work_report_maker/gui/pages/work_content_page.py](src/work_report_maker/gui/pages/work_content_page.py) — work group 復元 API 追加候補
- [src/work_report_maker/gui/pages/photo_import_page.py](src/work_report_maker/gui/pages/photo_import_page.py) — photo import settings と PhotoItem 群の注入 API 追加候補
- [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py) — arranged order の復元 API 追加候補
- [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py) — 説明欄 state 復元後の表示同期確認
- [src/work_report_maker/gui/pages/photo_models.py](src/work_report_maker/gui/pages/photo_models.py) — `PhotoItem` の serialize/deserialize 対象定義
- [src/work_report_maker/gui/preset_manager.py](src/work_report_maker/gui/preset_manager.py) — `~/.work_report_maker/` 配下利用と JSON 永続化パターンの参照元
- [tests/gui/test_report_wizard_integration.py](tests/gui/test_report_wizard_integration.py) — wizard 遷移と Step 1 UI の統合テスト追加先
- [tests/gui/wizard_stubs.py](tests/gui/wizard_stubs.py) — page 単体テスト用 stub 拡張候補

**Verification**
1. GUI テストで、project 名入力後に Step 1 から Step 2 へ進んだだけでは未保存のままで、Step 2 の保存ボタン押下で初めてプロジェクトフォルダと JSON が生成されることを確認する。
2. 同名プロジェクトが存在する状態で Step 2 から再保存し、確認ダイアログ経由で上書きできること、UI 上で削除した写真が保存フォルダから消えることを確認する。
3. Step 1 の読込操作で、cover 以降の全入力値と写真順序・説明欄が復元され、Step 2 へ進んだ後も既存の downstream 表示が破綻しないことを確認する。
4. Step 1 の削除操作で、対象プロジェクトフォルダが消え、一覧更新と確認ダイアログが正しく動くことを確認する。
5. 既存の [tests/gui/test_report_wizard_integration.py](tests/gui/test_report_wizard_integration.py) と photo 系 GUI テスト群を実行し、既存遷移や説明欄同期を壊していないことを確認する。

**Decisions**
- 保存先は `~/.work_report_maker/` 配下で固定し、1 プロジェクト 1 フォルダ構成とする。
- 保存は任意操作とし、保存が可能になるタイミングは「Step 1 で project 名入力後、表紙内容入力ページに入った時点」とする。
- 読込・削除は Step 1 内で実行する。
- 写真は元画像ではなく圧縮済みデータを保存し、上書き時には現 state に存在しない写真ファイルを削除する。
- 同名保存は確認ダイアログ付き上書きを採用する。
- 今回の範囲には PDF 出力仕様の変更、building/company preset の仕様変更、未保存変更検知の高度化は含めない。

**Further Considerations**
1. プロジェクトフォルダ名に project 名をそのまま使うと Windows 禁止文字の扱いが必要になるため、表示名と実ディレクトリ名を分離するか、既存 `_sanitize_pdf_stem()` 相当のサニタイズ規約を project 用にも明示しておく。
2. 読込 UI は件数が増えると選択性が落ちるため、初版は単純な一覧ダイアログで十分だが、将来は更新日時やサムネイルの表示余地を残せる構造にしておく。
3. 保存 JSON には `project_version` を必ず持たせ、後から state 項目を増やしても移行しやすくする.
