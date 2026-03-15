# Prompt: Extract Report Build Helper

あなたの対象は、現時点で `plan-guiResponsibilityClarification.prompt.md` まで反映された GUI 実装です。目的は、`ReportWizard.accept()` 周辺に残っている report 出力組み立て責務を、既存動作と既存テストを維持したまま小さな helper / service へ寄せることです。

この prompt は `QWizard` ベース UI の再設計を求めるものではありません。`accept()` と `_build_photos()` を中心に、最終 payload 組み立ての責務だけを切り出してください。

## Goal

- `ReportWizard` から report build 専用責務を薄く切り出す
- cover / overview / photos の最終 payload 組み立てを helper に寄せる
- 一時写真ファイル書き出し責務を UI クラス本体から分離する
- 既存の `accept()` の外部挙動と GUI テストを壊さない

## Primary Concerns To Address

現時点で特に整理対象になりやすいのは、少なくとも次の 4 点です。

1. `ReportWizard.accept()` が UI 終了処理と report payload 組み立てを両方持っていること
2. `_build_photos()` が photo tmp dir 管理と出力 dict 生成をまとめて持っていること
3. cover / overview / photos の collect 呼び出しと payload schema 組み立てが近接していること
4. 将来 CLI や別 UI から再利用したい report build 境界がまだ曖昧なこと

## Constraints

- 外部仕様を変えない
- `accept()` の公開挙動を変えない
- 既存の report schema を変えない
- `QWizard` のページ遷移や UI 文言を変えない
- 一時ファイルの扱いは従来どおり `file://` URI を返す
- 1 回で services 層の大規模再編はしない

## Recommended Implementation Order

次の順番を推奨します。

1. report build に必要な入力を棚卸しする
2. photos 出力の helper を抽出する
3. cover / overview / photos をまとめる report build helper を導入する
4. `ReportWizard.accept()` を orchestration に寄せる

## Implementation Tasks

### Task 1: Report Build Input を明確にする

`accept()` が最終 payload を作るために必要な入力を棚卸ししてください。

最低限、次を明確にしてください。

- project name
- cover data
- overview data
- arranged photo items
- temporary photo output directory

必要なら、これらを受け取る小さな value object を導入して構いません。

### Task 2: Photos 出力 helper を切り出す

`_build_photos()` にある責務を、UI クラス本体から見えにくくしてください。

少なくとも以下を分けてください。

- 一時ディレクトリの作成
- ファイル名決定
- bytes の書き出し
- `photo_path` を含む dict への変換

優先構成:

- `ReportWizard` は helper を呼ぶだけにする
- helper が photos 配列と temp dir を返す
- schema 自体はそのまま維持する

### Task 3: Report payload 組み立て helper を導入する

cover / overview / photos をまとめる report build helper を導入してください。

候補:

- `gui/report_builder.py`
- `gui/report_build_helper.py`
- `gui/report_payloads.py`

ただし、ファイル数を増やしすぎないでください。最初は 1 ファイルの小さな helper で十分です。

### Task 4: ReportWizard.accept() を orchestration に寄せる

`accept()` には最低限、次の責務だけを残してください。

- field / page から必要値を取得する
- report build helper を呼ぶ
- stderr へ JSON を出力する
- `super().accept()` を呼ぶ

`ReportWizard` 本体に report schema 組み立ての詳細を残しすぎないでください。

### Task 5: 残す責務と見送る責務を明確にする

最後に、最低限次の 3 区分で整理してください。

- `ReportWizard` に残す責務
- report build helper に移した責務
- 今回見送った責務

## Suggested File Targets

- `src/work_report_maker/gui/main_window.py`
- 新規 helper 候補: `src/work_report_maker/gui/report_build_helper.py`
- 必要なら新規 helper 候補: `src/work_report_maker/gui/report_payloads.py`

## Required Verification

最低限、次を実行してください。

- `tests/gui/test_report_wizard_integration.py`
- `tests/gui/test_photo_description_page.py`

最低限確認すべき観点:

- `accept()` が従来どおり JSON を stderr へ出力すること
- arrange された写真列が完了時の payload へ反映されること
- photo description の編集値が photos 配列へ反映されること
- `photo_path` が従来どおり `file:///` URI になること

必要なら、抽出した pure helper に対する単体テストを追加してください。

## Non-Goals

この段階では、次のことはやらないでください。

- report schema の変更
- PDF 生成 services の設計変更
- `QWizard` 自体の置き換え
- GUI の見た目変更
- photo import / arrange / description page の大規模再設計

## Completion Criteria

次の状態になったら完了とみなしてください。

- `ReportWizard.accept()` の責務が今より明確に薄くなっている
- photos 出力責務が helper へ切り出されている
- 最終 payload 組み立てが再利用しやすい入口へ寄っている
- 必須テストが通る
- 今回見送った残タスクが短く整理されている

## Optional Stretch

余力があれば、次も検討してください。

- temp dir を保持するオブジェクト境界をさらに明確にする
- GUI から独立した report build 単体テストを増やす
- stderr 出力と payload build をさらに分離する