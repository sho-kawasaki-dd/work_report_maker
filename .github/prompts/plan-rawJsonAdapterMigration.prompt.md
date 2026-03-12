## Plan: Raw JSON adapter migration

GUI 入力しやすい raw JSON を今後の標準入力にし、Python 側で Jinja 完成形 `report` へ変換する adapter 層を追加する。短期は raw/完成形の両入力を扱えるようにして移行リスクを抑え、その後に既定サンプルと README を raw JSON 基準へ寄せる。テンプレートは変更せず、`main.py` はオーケストレーション、adapter は入力整形、テンプレートは表示に責務を分離する。

**Steps**
1. Phase 1: 入力契約の分離
2. 現在の [main.py](c:/Users/tohbo/python_programs/work_report_maker/main.py) で扱っている完成形 `report` を「レンダリング契約」と定義し直し、GUI や手編集用には別の raw JSON 契約を定義する。raw JSON では `photo_pages` を廃止し、一次元の `photos` 配列を採用する。
3. raw JSON に含めるのは GUI の自然入力だけに絞る。推奨は `title`, `cover`, `overview`, `photos`。`photos[]` には `no`, `site`, `work_date`, `location`, `photo_path`, `work_content`, `remarks` を必須とし、必要なら `page_break_after` や手動調整用 `font_size_pt` を任意項目にする。
4. `photo_layout.labels` や `overview.work_section_title`、`blank_lines` のような表示寄りの値は raw JSON の標準入力から外し、Python 側の既定値または adapter 設定に寄せる。テンプレートで固定に近い値を GUI 入力へ露出しない。
5. Phase 2: Adapter 層の導入
6. 新しい adapter モジュールを `backend` 配下に追加し、責務を `raw -> render-ready report` 変換へ限定する。推奨 API は `build_report_from_raw(raw_report: dict[str, object]) -> dict[str, object]`。
7. adapter 内に raw JSON 用バリデーションを追加し、必須フィールド欠落や型不整合を GUI 入力エラーとして返せるようにする。完成形用の既存検証は最終出力の確認として再利用する。*depends on 6*
8. adapter 内に、以前 `main.py` で持っていた表示派生ロジックを戻す。具体的には、テキスト正規化、行分割、文字量に応じた `font_size_pt` 推定、`layout_mode` 推定、`line_count` 算出、写真のページ分割をここへ集約する。*depends on 6*
9. ページ分割は `PHOTO_PAGE_SIZE=3` の固定 chunk を初期案としつつ、将来の明示改ページに備えて `page_break_after` を尊重できる構造で実装計画を立てる。最初から複雑な高さ計算には踏み込まない。
10. Phase 3: main.py の受け口整理
11. [main.py](c:/Users/tohbo/python_programs/work_report_maker/main.py) の `load_report_data(...)` は「ファイルを読む」責務に寄せ、入力が raw か完成形かを判定して適切な検証または変換へ回す流れに整理する。推奨は `load_input_data(...)`, `build_report_context(...)`, `prepare_report_for_render(...)`, `generate_full_report(...)` の 4 段構成。
12. 形式判定はトップレベルキーで行う。`photo_pages` があれば完成形、`photos` があれば raw とみなす。両方ある、またはいずれも無い場合は入力エラーとして扱う。*depends on 7*
13. `prepare_report_for_render(...)` は引き続き写真 URI 解決だけを担い、表示用派生値の生成は adapter に寄せる。これにより GUI 直接呼び出しでもファイル入力でも同じ変換ルートを通せる。
14. Phase 4: サンプルデータと移行導線
15. 現在の [data/report.json](c:/Users/tohbo/python_programs/work_report_maker/data/report.json) は移行期間だけ残し、新しい raw JSON サンプルを追加する。推奨は `data/raw_report.json` を既定サンプルにし、完成形 JSON は比較用または変換結果例に下げる。
16. raw JSON から完成形へ自動変換できるなら、CLI の既定入力を段階的に raw JSON へ移す計画にする。初期段階では両対応、次段で README と既定パスを raw 優先へ変更する。*depends on 11*
17. [README.md](c:/Users/tohbo/python_programs/work_report_maker/README.md) は「GUI は raw JSON を作る」「Python が完成形へ変換する」「テンプレートは完成形しか知らない」という責務分離を明示する。完成形 JSON はデバッグ用・移行用の位置づけへ下げる。
18. Phase 5: GUI アダプタ観点の設計詳細
19. GUI からはフォーム値をそのまま raw 辞書へ詰め、adapter の戻り値だけを PDF 生成へ渡す前提にする。GUI は `lines`, `layout_mode`, `photo_pages`, `blank_lines` を知らない構成にする。
20. 画面入力で編集しやすいよう、写真は一次元リストで管理し、並び順がそのまま出力順になる前提を明文化する。ページ分割責務は常に Python 側へ置く。
21. GUI で必要になりそうな調整項目は raw JSON の任意項目として先に設計余地を確保する。候補は `page_break_after`, `font_size_pt`, 将来的な `layout_mode` 手動上書き。初回実装では最小限に留める。
22. Phase 6: 検証計画
23. raw JSON サンプルから PDF を生成し、現行完成形 JSON 版と見た目が大きく崩れないことを確認する。
24. 同じ内容を raw JSON と完成形 JSON の両方で通し、テンプレート出力の差分が許容範囲かを目視確認する。特に `work_content.lines`, `remarks.lines`, `layout_mode` を重点確認する。
25. 写真パスの相対・絶対・存在しないケース、長文テキスト、空の `remarks`、4 ページ以上の写真件数で adapter の分岐を確認する。
26. raw JSON の必須フィールド欠落時に、GUI 側で扱いやすいエラーメッセージになることを確認する。

**Relevant files**
- `c:\Users\tohbo\python_programs\work_report_maker\main.py` — 入力形式判定、adapter 呼び出し、既存の PDF 生成入口の整理対象
- `c:\Users\tohbo\python_programs\work_report_maker\README.md` — raw JSON 標準化後の使い方と移行方針を記載する
- `c:\Users\tohbo\python_programs\work_report_maker\data\report.json` — 移行期間中の完成形サンプル。raw 版との比較対象
- `c:\Users\tohbo\python_programs\work_report_maker\templates\report_tmp.html` — 完成形 `report` 契約の参照元。テンプレート変更なしで adapter の正しさを確認する

**Verification**
1. raw JSON を入力として PDF が生成できることを確認する
2. 完成形 JSON も移行期間中は引き続き読み込めることを確認する
3. raw から変換した `report` が既存のテンプレート参照先を満たしていることを確認する
4. 長文の `work_content` と `remarks` で `font_size_pt`, `lines`, `layout_mode` が期待どおり縮退することを確認する
5. `page_break_after` を入れたケースと未指定ケースでページ分割が想定どおりかを確認する
6. README の手順だけで raw JSON 差し替えから PDF 生成まで再現できることを確認する

**Decisions**
- 今後の標準入力は raw JSON にする
- 既存の完成形 JSON は移行期間を設けたうえで最終的に廃止前提にする
- テンプレート HTML/CSS は変更せず、adapter の出力を完成形 `report` 契約へ合わせる
- GUI は表示派生値を持たず、自然入力のみを扱う
- ページ分割は Python 側責務に戻し、写真は一次元配列で管理する

**Further Considerations**
1. 初回 adapter は既存の文字数ベース heuristic を復元するのが安全。実測ベースのレイアウト計算は後段へ回す
2. `photo_layout.labels` を完全固定にするか raw JSON で上書き可能にするかは、GUI の自由度と設定画面の複雑さのトレードオフになる。初期案は Python 側既定値で十分
3. 完成形 JSON の廃止タイミングは、raw JSON サンプルと GUI 実装の両方が揃った段階で決めるのが安全
