## Plan: Photo Description Page

写真並び替えの直後に Step 7 の写真説明ページを追加し、各写真の説明値を PhotoItem に保持したまま最終 JSON/PDF 出力へ流す。並び順の正本は引き続き PhotoArrangePage が持ち、新ページはその順序を読みつつ、1 件前後移動だけを許可する。移動対象は「現在位置」ではなく、Step 7 上で現在フォーカスされている写真とする。初期値は取り込み時に PhotoItem へ入れ、表紙・工事概要の変更後は未編集項目だけ再同期する。2 枚/4 枚同時編集は「現在位置から連続した写真」を対象にする。フォーカス中の写真は、編集枠を薄い青で強調するなど視覚的に判別できる状態にする。

**Phases**

### Phase 1: データモデルと既定値基盤

目的: 写真説明を UI より先にデータとして成立させ、後続フェーズが同じ状態モデルを使えるようにする。

1. データモデル整理: src/work_report_maker/gui/pages/photo_import_page.py の PhotoItem に `site` `work_date` `location` `work_content` `remarks` と、未編集初期値の再同期に必要なフラグまたは初期値スナップショットを追加する。PhotoItem 生成時にデフォルト値を与える入口を用意し、GUI 非依存で扱える更新 API を決める。
2. 既定値供給の整理: src/work_report_maker/gui/pages/cover_form_page.py と src/work_report_maker/gui/pages/overview_form_page.py の公開アクセサを再利用し、`現場=施工対象・名称` `施工日=開始日` `施工箇所=施工場所` をまとめて取得するヘルパーを src/work_report_maker/gui/main_window.py か新ページ側から参照できる形にする。`開始日` は format_work_date() ではなく開始日単独の表示を返す専用アクセサを追加する。

完了条件:

- PhotoItem が写真説明の状態を保持できる。
- 新規取り込み時に 3 つの既定値が注入される。
- 後続ページから既定値取得 API を呼べる。

### Phase 2: Step 7 の骨組み追加

目的: 写真並び替えの後ろに新ページを差し込み、現在順に追従する表示の土台を作る。

1. 新ページ追加: src/work_report_maker/gui/pages/photo_description_page.py を追加し、src/work_report_maker/gui/main_window.py の Step 7 として PhotoArrangePage の後ろへ差し込む。
2. initializePage() で PhotoArrangePage.collect_photo_items() の現在順を取り込み、ページ再訪時は既存編集状態を保持しつつ不足分だけ UI を再構成する。
3. まずは単票表示を成立させ、写真 No が現在順に基づいて表示されることを保証する。この段階ではファイル名称は表示せず、施工内容と備考の文章だけは編集できるようにする。

完了条件:

- ウィザードに Step 7 が追加される。
- PhotoArrangePage の順序が Step 7 に反映される。
- 写真 No が読み取り専用で表示される。
- 施工内容と備考の文章を Step 7 で編集でき、PhotoItem に保存される。

### Phase 3: 編集 UI と画面切替

目的: 実用的な写真説明入力を可能にし、1 枚、2 枚、4 枚の連続編集を成立させる。

1. 編集 UI 設計: 新ページに「現在位置」「表示モード 1/2/4」「前の写真」「次の写真」「PageUp/PageDown ショートカット」を持たせ、現在位置から連続した 1 件/2 件/4 件の編集フォームを表示する。
2. 各フォームは写真 No を読み取り専用表示し、現場・施工日・施工箇所を編集可能にする。施工内容と備考の文章編集は Phase 2 で導入済みとし、Phase 3 では複数枚同時編集へ拡張する。サムネイルも併記して対象誤認を防ぐ。
3. PageUp/PageDown と画面内ボタンの両方で編集対象を前後切替できるようにする。

完了条件:

- 1 枚、2 枚、4 枚モードを切り替えられる。
- 現在位置から連続した写真が表示される。
- 入力値が各 PhotoItem に保存される。

### Phase 4: 限定並び替えと未編集項目の再同期

目的: Step 7 内での軽微な順序調整と、前段ページの変更反映を安全に両立させる。

1. 限定並び替え: 新ページに「写真を一つ前に移動」「写真を一つ後ろに移動」を追加し、内部で PhotoArrangePage の単一移動ロジックを再利用できるよう公開メソッド化するか、共有ヘルパーへ抽出する。移動対象は Step 7 上でフォーカスされている `_PhotoDescriptionEditor` に紐づく PhotoItem とする。
2. フォーカス管理: 各編集フォームのフォーカスインを拾って「どの写真が操作対象か」を明示的に管理し、フォーカス中の編集枠は薄い青背景や枠線で強調表示する。クリックや Tab 移動でフォーカスが変わったら、操作対象も即座に切り替わるようにする。
3. 移動後は PhotoArrangePage と新ページの両方で同じ PhotoItem 順序を参照し、編集中の対象 PhotoItem が新しい index へ追従するよう current anchor を PhotoItem 参照ベースで持つ。写真 No は常に現在順から再計算する。
4. 未編集項目の再同期: 新ページ表示時または前ページ変更後の再入場時に、各 PhotoItem の `site` `work_date` `location` について「まだ既定値のまま」の項目だけ最新の表紙/工事概要値へ更新する。ユーザー変更済み判定は項目単位で持ち、手動編集後は再同期対象から外す。`work_content` と `remarks` は空欄既定のため自動再同期対象外とする。

完了条件:

- Step 7 で前後 1 件移動ができる。
- Step 7 の前後 1 件移動が、フォーカス中の写真に対して適用される。
- 移動後も同じ PhotoItem を編集し続けられる。
- フォーカス中の写真が視覚的に判別できる。
- 未編集の `site` `work_date` `location` だけが再同期される。

### Phase 5: 出力連携とテスト

目的: UI で保持した値を最終成果物へ確実に流し、回帰しない状態で締める。

1. 最終出力連携: src/work_report_maker/gui/main_window.py の \_build_photos() を更新し、PhotoItem 上の説明値を photos 配列へ反映する。src/work_report_maker/services/report_adapter.py は既存のまま利用しつつ、必要なら長文入力時の UI ガイドまたはバリデーションを追加する。work_content は 52 文字超で 5-6 行へ縮小、remarks は 30 文字超で 4 行へ縮小される既存仕様を前提にする。
2. テスト追加: tests/gui/test_photo_arrange_page.py の PhotoItem ヘルパーを新属性対応に更新し、限定移動 API の単体テストを追加する。
3. tests/gui に新ページ用テストを追加し、1/2/4 表示切替、PageUp/PageDown による対象切替、フォーカス移動に伴う操作対象の切替、単一前後移動後の No 再計算、編集値が PhotoItem へ保存されること、未編集項目のみ再同期されること、フォーカス中フォームの強調表示が切り替わることを検証する。必要なら tests/services/test_pdf_generator.py か新規 GUI 統合テストで \_build_photos() への反映も確認する。

完了条件:

- wizard.accept() 相当の経路で photos 配列へ説明値が出力される。
- 並び替えと説明編集の主要挙動がテストで担保される。
- 既存の PDF 生成フローに接続しても回帰しない。

### Phase 6: ドキュメント加筆修正

目的: 実装後の GUI フロー、PhotoItem の責務、写真説明画面の仕様を README と設計資料へ反映し、運用時の認識差分をなくす。

1. README 更新: GUI のページ構成へ Step 7 を追加し、写真説明画面の役割、1/2/4 分割編集、PageUp/PageDown による切替、Step 7 内での前後 1 件移動、既定値の由来、未編集項目だけ再同期される挙動を追記する。
2. 設計ドキュメント更新: Documentation/photo_import_arrange_design.md を、写真説明入力まで含む設計資料へ拡張する。必要に応じてタイトル、概要、モジュール構成、データフロー、PhotoItem 定義、UI 構成、accept() 時のデータ構造、スコープを更新する。
3. 変更内容の整合確認: README と設計ドキュメントの説明が実装済みの挙動と一致することを確認し、旧仕様の記述や「後続フェーズで実装」のような未更新文言を除去する。

完了条件:

- README に Step 7 の説明と操作方法が反映される。
- Documentation/photo_import_arrange_design.md が写真説明画面を含む現行仕様へ更新される。
- 実装と文書の用語、画面順、データ構造の説明が一致する。

**Relevant files**

- d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/main_window.py - Step 7 追加、写真収集の出口 `_build_photos()` 更新、必要なら既定値取得ヘルパーの配置
- d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/pages/photo_import_page.py - PhotoItem の属性拡張、取り込み時の既定値注入
- d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/pages/photo_arrange_page.py - 単一前後移動ロジックの再利用口追加、順序の正本として新ページと連携
- d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/pages/cover_form_page.py - 開始日単独の既定値アクセサ追加
- d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/pages/overview_form_page.py - `施工対象・名称` `施工場所` の既定値取得を再利用可能に整理
- d:/programming/py_apps/work_report_maker/src/work_report_maker/gui/pages/photo_description_page.py - 新規 Step 7、分割編集・移動・切替 UI 本体
- d:/programming/py_apps/work_report_maker/src/work_report_maker/services/report_adapter.py - 既存制約確認先。通常は修正不要だが UI バリデーション設計時の根拠として参照
- d:/programming/py_apps/work_report_maker/tests/gui/test_photo_arrange_page.py - 既存並び替えロジックの回帰防止とヘルパー更新
- d:/programming/py_apps/work_report_maker/tests/gui - 新ページの GUI テスト追加先
- d:/programming/py_apps/work_report_maker/README.md - Step 7 の利用方法と GUI 全体仕様の更新先
- d:/programming/py_apps/work_report_maker/Documentation/photo_import_arrange_design.md - 写真説明画面まで含めた設計資料の更新先

**Verification**

1. GUI テストで、PhotoArrangePage で並び替えた順序が新ページへ反映され、写真 No が読み取り専用で順序に追従することを確認する。
2. GUI テストで、Step 7 の「一つ前/後ろへ移動」がフォーカス中の写真へ適用され、移動後も編集対象が同じ PhotoItem を指し続け、表示 No のみ更新されることを確認する。
3. GUI テストで、1/2/4 分割切替時に現在位置から連続した写真が表示され、PageUp/PageDown で編集対象が前後に切り替わることを確認する。
4. GUI テストで、クリックや Tab 移動でフォーカスが移った写真の編集枠だけが強調表示されることを確認する。
5. GUI テストで、表紙または工事概要を変更して戻った場合、未編集の `site` `work_date` `location` だけ再同期され、手動編集済み項目は保持されることを確認する。
6. 受け入れ確認として、wizard.accept() 相当の経路で生成される photos 配列に PhotoItem の説明値が入ることを確認する。
7. README の GUI 手順、Step 7 の説明、既定値と再同期の説明が実装済みの挙動と一致することを確認する。
8. Documentation/photo_import_arrange_design.md のモジュール構成、データフロー、PhotoItem 定義、スコープが現行実装と矛盾しないことを確認する。

**Decisions**

- Step 7 は PhotoArrangePage の後ろに追加する。
- 2 枚/4 枚編集は「現在位置から連続した写真」を対象にする。
- 編集対象の切替ショートカットは PageUp/PageDown を中心にする。
- Step 7 の「一つ前/後ろへ移動」は、現在フォーカスされている写真に対して適用する。
- フォーカス中の写真は、薄い青の背景や枠線などで視覚的に強調する。
- `site` `work_date` `location` は未編集項目のみ最新値へ再同期する。
- 並び順の正本は引き続き PhotoArrangePage に置き、新ページはそれを参照・限定更新する。
- 今回のスコープにはテンプレート HTML/CSS のレイアウト変更は含めず、既存の photos 出力構造を活かす。

**Further Considerations**

1. `PhotoItem` の項目ごとの dirty 管理は、単純な bool 5 個でも実装できるが、`default_values` と `user_overrides` を持つ小さなヘルパーへまとめると再同期条件が明確になる。
2. 新ページでサムネイル再生成を避けるため、既存 `thumbnail` をそのまま使い、拡大表示が必要な場合だけ `data` から再描画するのがよい。
3. 将来 Step 7 で複数写真一括入力を広げる可能性を考えると、フォーム部品は `PhotoDescriptionEditor` のような小コンポーネントへ分けると保守しやすい。
