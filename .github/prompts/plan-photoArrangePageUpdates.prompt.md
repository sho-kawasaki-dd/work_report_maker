## Plan: Photo Arrange Page Updates

画像並び替えページに対して、単一選択時の Ctrl+左右キー移動、ファイル名ではなく並び順ベースの番号表示、50%〜200% のサムネイル拡大縮小、関連ドキュメント更新を追加する。既存の並び替え中核ロジック `_move_rows_to()` と選択復元 `_select_rows()` を再利用し、表示番号はモデル行番号から再計算する方式にして、並び替え・追加・削除後も自然に追従させるのが最小変更で堅い方針。

**Steps**

1. [src/work_report_maker/gui/pages/photo_arrange_page.py](d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/pages/photo_arrange_page.py) の現状ロジックを維持しつつ、単一選択だけを判定するヘルパーを追加する。`selectionModel()` から現在の選択行を確認し、選択数が 1 件のときだけ Ctrl+Left / Ctrl+Right に反応させる。複数選択、未選択、先頭での左移動、末尾での右移動は no-op にする。
2. _depends on 1_ 同ファイルの `keyPressEvent()` を拡張し、Delete の既存挙動を壊さずに `Qt.KeyboardModifier.ControlModifier` と左右キーをハンドリングする。移動自体は `_move_rows_to()` を単一行で呼び、移動後は `_select_rows()` で選択状態と current index を維持する。
3. _parallel with 1-2 conceptually, but implemented in same file_ [src/work_report_maker/gui/pages/photo_arrange_page.py](d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/pages/photo_arrange_page.py) のモデル項目生成を見直し、キャプションをファイル名ではなく 1 始まりの通し番号に変更する。`_make_model_item()` は初期番号を設定し、並び替え・追加・削除・再初期化後に一括再計算する `_refresh_item_labels()` のようなヘルパーを導入して、モデルの row 順を正として常に `1, 2, 3, ...` を振り直す。
4. _depends on 3_ 番号更新ヘルパーを、`initializePage()`、`_move_rows_to()`、`_on_add_items_ready()`、`_delete_selected()` の各モデル更新経路から呼ぶ。これにより、ページ再訪時、新規追加時、削除時、D&D / ボタン / キー移動時の全経路で表示番号を同期させる。
5. [src/work_report_maker/gui/pages/photo_arrange_page.py](d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/pages/photo_arrange_page.py) のズーム UI を百分率ベースに変更する。スライダー範囲を 50〜200、初期値を 100 にし、`_on_zoom_changed()` では `_DEFAULT_THUMB_SIZE` を基準に実ピクセル値へ変換して `setIconSize()` と `setGridSize()` を更新する。ラベル文言も「サムネイルサイズ」から、必要なら百分率が伝わる表現へ調整する。
6. [tests/gui/test_photo_arrange_page.py](d:/programming/py_apps/work_report_maker/tests/gui/test_photo_arrange_page.py) に回帰テストを追加する。既存の `_create_page()` と `_photo_names()` パターンを再利用し、少なくとも以下を検証する: 単一選択の Ctrl+Left / Ctrl+Right、複数選択時 no-op、境界 no-op、番号表示の初期値と並び替え後更新、ズームスライダー変更後の `iconSize` / `gridSize`。
7. _parallel with 6 after仕様確定_ [README.md](d:/programming/py_apps/work_report_maker/README.md) の Step 6 説明を更新し、Ctrl+左右キー、番号表示、50%〜200%ズームを追記する。
8. _parallel with 6 after仕様確定_ [Documentation/photo_import_arrange_design.md](d:/programming/py_apps/work_report_maker/Documentation/photo_import_arrange_design.md) の PhotoArrangePage 設計説明と UI 説明を更新し、キーバインド、番号表示、百分率ズーム、対応テスト観点を明記する。

**Relevant files**

- `d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/pages/photo_arrange_page.py` — `keyPressEvent()`, `_make_model_item()`, `_on_zoom_changed()`, `_move_rows_to()`, `initializePage()`, `_on_add_items_ready()`, `_delete_selected()` が主変更点。既存の `_select_rows()` と `_selected_rows_sorted()` を再利用する。
- `d:/programming/py_apps/work_report_maker/tests/gui/test_photo_arrange_page.py` — Arrange ページの既存回帰テスト。新しいキー操作・番号表示・ズームをここに追加するのが自然。
- `d:/programming/py_apps/work_report_maker/README.md` — Step 6 のユーザー向け仕様説明を更新する。
- `d:/programming/py_apps/work_report_maker/Documentation/photo_import_arrange_design.md` — 実装設計メモを実装仕様に合わせて更新する。

**Verification**

1. `uv run pytest tests/gui/test_photo_arrange_page.py` を実行し、既存テストと新規テストが通ることを確認する。
2. GUI の手動確認として、単一選択で Ctrl+Left / Ctrl+Right が 1 枚単位で移動し、複数選択では何も起きないことを確認する。
3. 並び替え、追加、削除、ページ再訪の各操作後に、サムネイル番号が見た目の並び順どおりに 1 始まりで連番更新されることを確認する。
4. ズームスライダーを 50%、100%、200% に動かし、サムネイルが期待どおりの大きさに変わり、レイアウト崩れや極端な重なりがないことを確認する。

**Decisions**

- ズームの 50%〜200% は既存のデフォルト 128px を 100% と解釈し、内部的には 64〜256px に写像する。
- 番号表示は「その時点の全体順」を表す単純な通し番号とし、ファイル名はキャプションから外す。
- 既存の複数選択移動ボタンと D&D の挙動は維持し、Ctrl+左右キーは単一選択専用の補助操作として追加する。
- スコープ外: 写真メタデータ入力、表示番号の永続化、ズーム値の設定保存。
