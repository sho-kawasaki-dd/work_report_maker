## Phase 1 Prompt: Refactor PhotoArrangePage

あなたの対象は [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py) のみです。目的は、巨大なページクラスを安全に分割し、責務を減らしつつ既存の振る舞いを維持することです。

この段階では、見た目や仕様を変えないでください。最優先は、公開 API と既存テストを壊さずに内部構造を整理することです。

## Goal

- [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py#L240) の責務を分割する。
- 既存の公開 API を維持する。
- Qt 依存が強い処理と、純粋な並び替えロジックを切り離す。
- 追加インポート、ズーム、アイコン更新、削除、並び替えの回帰を防ぐ。

公開 API として維持するもの:

- `collect_photo_items()`
- `move_photo_item_left()`
- `move_photo_item_right()`
- `cancel_active_import()`

この Phase では、[src/work_report_maker/gui/pages/photo_import_page.py](src/work_report_maker/gui/pages/photo_import_page.py) や [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py) の仕様変更は行わないでください。必要があっても、呼び出し側のコードを壊さない範囲に留めてください。

## Constraints

- 外部仕様を変えない。
- 既存の GUI テストを回帰防止の基準にする。
- 1 回の変更で大きく作り替えず、小さく分離する。
- `self._wizard()._photo_import_page` との連携は当面維持してよい。
- 公開 API を追加する場合は、既存 API を置き換えず補助的なものだけにする。

## Implementation Tasks

1. まず [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py) の責務を 4 つに棚卸ししてください。
   責務は少なくとも、並び替えロジック、表示ウィジェット、アイコンとズーム、追加インポート制御に分けてください。

2. 並び替えロジックの抽出方針を決めてください。
   対象は `_move_rows_to()` を中心に、`_move_selection_to()`, `_move_left()`, `_move_right()`, `_move_single_selection_left()`, `_move_single_selection_right()`, `move_photo_item_left()`, `move_photo_item_right()` です。
   このロジックは、可能な限り Qt の view や selection model から独立した形へ寄せてください。

3. 並び替えロジック用の新しい helper か module を追加してください。
   ここでは、行番号の移動計算、複数選択のブロック移動、端での no-op 判定、挿入位置補正を担当させてください。
   UI 更新や selection の復元はページ側に残して構いません。

4. [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py#L83) の `_PageBorderDelegate` と [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py#L120) の `_PhotoArrangeListView` の扱いを整理してください。
   この段階では、無理に完全分離しなくて構いません。先に「ページ本体に置くべきか」「widgets 側へ移すべきか」を決め、切り出せるなら小さく分離してください。

5. アイコン生成とズーム更新をページ本体から薄くしてください。
   対象は `_clear_icon_cache()`, `_make_icon_for_photo()`, `_refresh_item_icons()`, `_update_zoom_label()`, `_snap_zoom_percent()`, `_thumb_size_for_percent()`, `_on_zoom_changed()` です。
   アイコンキャッシュとズーム計算は helper に寄せ、QListView への反映はページ側に残す構成を優先してください。

6. 追加インポート処理を整理してください。
   対象は `_add_photos()` から、進捗ダイアログ、worker/thread の保持、insert 位置計算、import page の設定参照、items の受け取りまでです。
   この段階では import page との再利用を完全統合しなくてよいですが、ページ本体から処理の塊を切り出してください。

7. ページ本体を orchestration に寄せてください。
   `PhotoArrangePage` には、UI 配線、外部ページ連携、モデル更新の最終反映だけを残す方向で整理してください。

8. 既存テストが依存している振る舞いを維持してください。
   特に [tests/gui/test_photo_arrange_page.py](tests/gui/test_photo_arrange_page.py) で検証されている以下を壊さないでください。
   並び替え順序、複数選択のブロック移動、削除、Ctrl+左右、ズーム、公開 API 経由の単一写真移動、追加写真の挿入位置。

9. 必要なら Arrange 専用の小さな単体テストを追加してください。
   追加対象は、Qt を立ち上げなくても検証できる純粋ロジックだけにしてください。

10. 最後に、どこまで分離したかを要約してください。
    最低限、ページ本体に残した責務、helper/module に移した責務、今回見送った責務を分けて説明してください。

## Suggested File Targets

必要なら、次のような小さな分割を検討してください。

- [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py)
- 新規 helper: `src/work_report_maker/gui/pages/photo_arrange_logic.py`
- 新規 helper: `src/work_report_maker/gui/pages/photo_arrange_icons.py`
- 新規 helper: `src/work_report_maker/gui/widgets/photo_arrange_view.py`

ただし、ファイル数を増やしすぎないでください。最初の一歩では、2 つか 3 つの小さな抽出で十分です。

## Required Verification

必ず [tests/gui/test_photo_arrange_page.py](tests/gui/test_photo_arrange_page.py) を実行してください。

最低限確認すべき観点:

- 並び順が `initializePage()` の再実行後も維持されること
- 複数選択の移動がブロックとして扱われること
- 削除が import page 側にも反映されること
- `move_photo_item_left()` と `move_photo_item_right()` が期待通り動くこと
- ズーム変更で icon size と grid size が同期すること
- 追加写真が選択位置または末尾へ正しく挿入されること

必要なら、今回の抽出に対応する純粋ロジックのテストを追加してください。

## Non-Goals

この Phase では、次のことはやらないでください。

- [src/work_report_maker/gui/pages/photo_import_page.py](src/work_report_maker/gui/pages/photo_import_page.py) の大規模分割
- [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py) の大規模分割
- [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) の直参照解消
- UI 文言や見た目の変更
- PDF 生成や services 層の機能変更

## Completion Criteria

次の状態になったら Phase 1 完了とみなしてください。

- [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py) の責務が以前より明確に減っている
- 並び替えロジックまたはズーム・アイコン処理の少なくとも 1 つがページ外へ抽出されている
- 公開 API が維持されている
- [tests/gui/test_photo_arrange_page.py](tests/gui/test_photo_arrange_page.py) が通る
- 今回見送った残タスクが短く整理されている

## Phase 2 Prompt: Refactor PhotoImportPage

あなたの対象は [src/work_report_maker/gui/pages/photo_import_page.py](src/work_report_maker/gui/pages/photo_import_page.py) です。目的は、画像インポートページの責務を分割し、UI、インポート実行制御、一覧管理、共有データモデルの境界を明確にすることです。

この段階では、見た目や既存フローを変えないでください。最優先は、既存ページとの連携を壊さずに内部構造を整理することです。

## Goal

- [src/work_report_maker/gui/pages/photo_import_page.py](src/work_report_maker/gui/pages/photo_import_page.py#L207) の責務を分割する。
- import 実行制御、圧縮設定 UI、一覧更新、既定値同期の責務を切り分ける。
- Arrange と Description から使われている呼び出し面を維持する。
- 将来の shared model 化に備えて、`PhotoItem` と `PhotoDescriptionDefaults` の位置づけを整理する。

公開面として維持するもの:

- `photo_items`
- `dpi()`
- `jpeg_quality()`
- `png_quality_max()`
- `current_photo_description_defaults()`
- `sync_photo_item_defaults()`
- `add_photo_items()`
- `remove_photo_items()`
- `cancel_active_import()`

## Constraints

- 外部仕様を変えない。
- Arrange と Description の呼び出しコードを壊さない。
- 既存の GUI テストが前提にしている振る舞いを維持する。
- 1 回で全面再設計せず、小さく分離する。
- `PhotoItem` を移動する場合も、import 側からの import パス破壊を避ける。

## Implementation Tasks

1. まず [src/work_report_maker/gui/pages/photo_import_page.py](src/work_report_maker/gui/pages/photo_import_page.py) の責務を、少なくとも次の 4 つに分けて整理してください。圧縮設定 UI、インポート実行制御、読み込み済み一覧表示、PhotoItem 既定値同期。

2. 圧縮設定 UI をページ本体から薄くしてください。対象は DPI、JPEG 品質、PNG 品質の slider/spinbox 同期と、`is_pngquant_available()` による表示切替です。

3. import 実行制御を切り出してください。対象は `_run_import()`, `_cancel_import()`, `_on_import_worker_finished()`, `_on_import_thread_finished()`, `_cleanup_import_state()` と、その周辺の progress dialog と worker/thread 管理です。

4. 読み込み済み一覧の更新責務を切り出してください。対象は `_add_photo_items()`, `_append_list_items()`, `_rebuild_photo_list()`, `_clear_all()`, `_update_count_label()` です。ページ本体には orchestration だけを残してください。

5. `PhotoItem` と `PhotoDescriptionDefaults` の位置づけを見直してください。必要なら shared module へ寄せても構いませんが、この Phase では import 側・arrange 側・description 側の import を壊さないことを優先してください。

6. `current_photo_description_defaults()` と `sync_photo_item_defaults()` の責務を維持してください。Overview と Cover の入力値が写真へ既定値として反映される現在の挙動を壊さないでください。

7. 追加・削除・既定値同期の Arrange 連携を維持してください。特に [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py) から見える振る舞いを変えないでください。

8. 可能なら、Qt を立ち上げずに検証できる最小の単体テストを追加してください。対象は defaults 同期や一覧状態更新のような純粋ロジックに限定してください。

9. 最後に、どこまで切り出したかを要約してください。ページ本体に残した責務、helper/module に移した責務、見送った責務を分けて説明してください。

## Suggested File Targets

- [src/work_report_maker/gui/pages/photo_import_page.py](src/work_report_maker/gui/pages/photo_import_page.py)
- 新規 helper 候補: `src/work_report_maker/gui/pages/photo_import_controls.py`
- 新規 helper 候補: `src/work_report_maker/gui/pages/photo_import_operation.py`
- 新規 shared model 候補: `src/work_report_maker/gui/pages/photo_models.py`

## Required Verification

必ず import 周辺の既存 GUI テストと、Arrange 連携が壊れていないことを確認してください。最低限、次を確認してください。

- `add_photo_items()` で一覧と内部状態が同期すること
- `remove_photo_items()` が Arrange 連携を壊さないこと
- `sync_photo_item_defaults()` が未編集フィールドだけを更新すること
- import キャンセル後に thread と progress state が正しく片付くこと
- `current_photo_description_defaults()` が wizard の現在値を反映すること

## Non-Goals

- [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py) の大規模分割
- [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) の直参照解消
- UI 文言や見た目の変更
- 画像処理サービス自体のアルゴリズム変更

## Completion Criteria

- [src/work_report_maker/gui/pages/photo_import_page.py](src/work_report_maker/gui/pages/photo_import_page.py) の責務が明確に減っている
- import 実行制御または設定 UI の少なくとも 1 つがページ外へ抽出されている
- Arrange/Description 連携が維持されている
- 既定値同期の挙動が維持されている
- 対象テストが通る

## Phase 3 Prompt: Refactor PhotoDescriptionPage

あなたの対象は [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py) です。目的は、写真説明ページの責務を分割し、editor 自体は維持しつつ、ナビゲーション、表示モード、focus 管理、page sync をページ本体から外へ出すことです。

この段階では、UI の見た目や編集体験を変えないでください。最優先は、Arrange との並び替え連携と、現在写真の維持ロジックを壊さないことです。

## Goal

- [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py#L273) の責務を分割する。
- `_PhotoDescriptionEditor` は UI と `PhotoItem` binding の中心として残す。
- page state、focus、view mode、navigation を helper/controller に寄せる。
- Arrange との連携を公開 API 経由に保つ。

## Constraints

- `_PhotoDescriptionEditor` の責務は無理に分割しない。
- Arrange 側の内部構造に依存しすぎない。
- 既存の表示モード 1/2/4、focus 移動、再初期化時の current photo 維持を壊さない。
- `PhotoItem` への直接反映という現在のデータ更新方式は維持する。

## Implementation Tasks

1. まず [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py) の責務を、少なくとも次の 5 つに分けて整理してください。editor binding、page sync、navigation、focus 管理、view mode/layout。

2. 日付処理を utility へ抽出してください。対象は `_parse_work_date()` と `_format_work_date()` です。editor/page から再利用する形にしてください。

3. page state を整理してください。対象は `initializePage()`, `current_photo()`, `current_photo_no()`, `visible_photo_items()`, `_refresh_display()`, `_update_navigation_buttons()` です。

4. focus 管理を切り出してください。対象は `_focused_photo_key`, `_sync_focused_photo()`, `_on_editor_focus_received()` と、active editor の見た目同期です。

5. view mode と再レイアウトを切り出してください。対象は `set_view_mode()` と `_relayout_visible_editors()` です。

6. Arrange 連携をページ本体から見えやすく整理してください。対象は `_move_current_photo_left()` と `_move_current_photo_right()` です。Arrange の公開 API だけを使う形に寄せてください。

7. `_PhotoDescriptionEditor` は残しつつ、フォーム生成や binding の補助が切り出せるなら小さく分けてください。ただし、過剰分割は避けてください。

8. 既存テストで検証されている振る舞いを維持してください。特に current photo の維持、view mode、focus、編集反映、Arrange との順序同期を壊さないでください。

9. 必要なら、Qt 依存の薄い状態遷移や日付 utility の単体テストを追加してください。

10. 最後に、ページ本体に残した責務、helper に移した責務、見送った責務を要約してください。

## Suggested File Targets

- [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py)
- 新規 helper 候補: `src/work_report_maker/gui/pages/photo_description_navigation.py`
- 新規 helper 候補: `src/work_report_maker/gui/pages/photo_description_focus.py`
- 新規 helper 候補: `src/work_report_maker/gui/pages/photo_description_dates.py`

## Required Verification

必ず [tests/gui/test_photo_description_page.py](tests/gui/test_photo_description_page.py) を実行してください。最低限、次を確認してください。

- 表示モード 1/2/4 が維持されること
- Arrange 順が page 初期化時に反映されること
- current photo が再初期化後も適切に保持されること
- 編集内容が `PhotoItem` に反映されること
- focus が visible editor と同期すること
- Arrange 側の並び替え API 連携が維持されること

## Non-Goals

- [src/work_report_maker/gui/pages/photo_import_page.py](src/work_report_maker/gui/pages/photo_import_page.py) の再整理
- [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) の直参照解消
- editor UI レイアウトの見た目変更
- PhotoItem のデータ構造変更

## Completion Criteria

- [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py) の責務が明確に減っている
- navigation、focus、view mode、date utility のいずれかがページ外へ抽出されている
- Arrange 連携が維持されている
- [tests/gui/test_photo_description_page.py](tests/gui/test_photo_description_page.py) が通る
- 残タスクが短く整理されている

## Phase 4 Prompt: Reduce ReportWizard Coupling

あなたの対象は [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) と、wizard 直参照を持つ各ページです。目的は、`self._wizard()._cover_page` のような直接参照を減らし、共有状態や accessor/service を通じた依存に薄くすることです。

この段階では、wizard のページ構成やユーザーの操作フローは変えないでください。最優先は、現在のページ間データ連携を壊さずに、依存方向を整理することです。

## Goal

- [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) と各ページの強い直参照を減らす。
- 読み取り専用データと更新系操作を切り分ける。
- 大きな shared state object をいきなり導入せず、最小の accessor/service から始める。
- `accept()` と `closeEvent()` の依存を明確にする。

## Constraints

- wizard のページ順、操作フロー、完了時の出力形式を変えない。
- 既存ページの公開 API を壊さない。
- まずは accessor/service に寄せる。全面的な state 管理再設計は避ける。
- 1 回で全ページを完全抽象化しようとしない。

## Implementation Tasks

1. まず wizard 直参照の一覧を作ってください。対象は少なくとも [src/work_report_maker/gui/pages/overview_form_page.py](src/work_report_maker/gui/pages/overview_form_page.py)、[src/work_report_maker/gui/pages/work_content_page.py](src/work_report_maker/gui/pages/work_content_page.py)、[src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py)、[src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py) です。

2. 直参照を、読み取り専用データと更新操作に分類してください。たとえば cover の参照値、overview の既定値、arrange の写真列、work content の収集結果を分けて扱ってください。

3. [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) に最小の accessor/service を導入してください。最初は、photo description defaults、cover 情報の参照、overview の既定値、arrange された写真列の取得あたりから始めてください。

4. 各ページが `self._wizard()._page_name` に直接触れる箇所を、可能な範囲で accessor/service 経由へ置き換えてください。

5. `accept()` でのデータ収集を整理してください。ページ内部へ直接潜らず、公開 API または集約 service を経由する形へ寄せてください。

6. `closeEvent()` の import 停止処理を整理してください。停止対象の取得や停止順序がページの内部構造に依存しすぎないようにしてください。

7. 既存の GUI テストや workflow を壊さない範囲で、最小の公開面を整えてください。大きなアーキテクチャ変更は避けてください。

8. 最後に、どの直参照を解消したか、まだ残っている直参照は何かを整理してください。

## Suggested File Targets

- [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py)
- [src/work_report_maker/gui/pages/overview_form_page.py](src/work_report_maker/gui/pages/overview_form_page.py)
- [src/work_report_maker/gui/pages/work_content_page.py](src/work_report_maker/gui/pages/work_content_page.py)
- [src/work_report_maker/gui/pages/photo_arrange_page.py](src/work_report_maker/gui/pages/photo_arrange_page.py)
- [src/work_report_maker/gui/pages/photo_description_page.py](src/work_report_maker/gui/pages/photo_description_page.py)

## Required Verification

最低限、次を確認してください。

- wizard の前後移動が維持されること
- cover と overview の値が各ページへ正しく伝播すること
- photo description defaults が current form values を反映すること
- arrange された写真列が完了時の出力へ反映されること
- 画像処理中の close で cancel 動作が維持されること

## Non-Goals

- 全ページを shared state object へ一気に載せ替えること
- UI 見た目の変更
- PDF 生成処理そのものの変更
- PhotoItem や report data schema の再設計

## Completion Criteria

- 主要な `self._wizard()._...` 直参照が減っている
- `main_window.py` の集約責務が整理されている
- 完了時出力と cancel 動作が維持されている
- 既存ワークフローが壊れていない
- 残りの直参照と次段階の整理候補が短くまとめられている
