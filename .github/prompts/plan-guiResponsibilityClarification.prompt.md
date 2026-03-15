# Prompt: Next GUI Responsibility Clarification

あなたの対象は、現時点で`.github/prompts/guiPhotoRefactor.prompt.md`の Phase 1〜4 を完了した GUI 実装です。目的は、既存動作と既存テストを維持したまま、責務の境界をもう一段明確にすることです。

この prompt は「大きな再設計」を求めるものではありません。今ある構造を壊さず、責務の曖昧さが残っている箇所を、薄い interface / service / helper に整理することを優先してください。

## Goal

- `ReportWizard` が新しい神オブジェクトへ膨らみ始めるのを防ぐ
- ページ側に残っている fallback 互換コードを、本番責務と分離する
- photo 系の「読み取り」と「更新」を分ける
- overview / work content の GUI 表示責務と、出力データ組み立て責務を分けやすい形へ寄せる
- 既存の workflow と GUI テストを壊さない

## Primary Concerns To Address

現時点で特に責務が曖昧になりやすいのは、少なくとも次の 4 点です。

1. `ReportWizard` の accessor 群が増え始めていること
2. `PhotoArrangePage` / `PhotoDescriptionPage` に、テスト互換の fallback ロジックが残っていること
3. photo 系アクセスに、読み取りと更新が混在していること
4. overview / work content で、GUI 表示用の値取得と report 出力用データ組み立てが近接していること

## Constraints

- 外部仕様を変えない
- 既存の公開 API は壊さない
- `QWizard` ベースの現在の画面遷移を変えない
- UI 文言や見た目を変更しない
- 1 回で shared state object へ全面移行しない
- まずは、小さな protocol / value object / service に寄せる
- 既存テストが依存している `wizard._photo_arrange_page` などの private 属性は、今回ただちに消さなくてよい

## Recommended Implementation Order

次の順番を推奨します。

1. wizard とページの間にある photo 系 interface を定義する
2. Arrange / Description の fallback 互換コードを、その interface を使う薄い adapter へ寄せる
3. `ReportWizard` の photo 系 accessor を、小さな service / context オブジェクトへまとめる
4. cover / overview / work content の既定値や表示値を、値オブジェクトとして整理する

## Implementation Tasks

### Task 1: Wizard Photo Interface を導入する

`PhotoArrangePage` と `PhotoDescriptionPage` が本当に必要としている依存を棚卸ししてください。

少なくとも以下を分類してください。

- 読み取り専用:
  - import 済み写真集合
  - arrange 済み写真集合
  - import 設定値
- 更新操作:
  - import 写真追加
  - import 写真削除
  - import defaults 同期
  - arrange 左移動
  - arrange 右移動

その上で、ページが依存する最小限の protocol / interface を導入してください。

例:

- `PhotoWizardReadContext`
- `PhotoWizardCommandContext`
- または `PhotoWizardContext` 1 つでもよい

ただし、interface の粒度は過剰に細かくしすぎないでください。

### Task 2: Fallback 互換コードをページ本体から薄くする

`PhotoArrangePage` と `PhotoDescriptionPage` には、現在 `getattr(wizard, "...")` と `wizard._photo_import_page` / `wizard._photo_arrange_page` fallback が入っています。

この責務をページ本体から見えにくくしてください。

優先構成:

- ページ本体は `self._photo_context()` のような単一入口だけを見る
- 実体解決は helper / adapter へ寄せる
- テスト互換ロジックは adapter 側へ閉じ込める

ページ本体に「本番ロジック」と「テスト用 fallback」の両方が混ざらない形を優先してください。

### Task 3: ReportWizard の photo 系 accessor を整理する

`main_window.py` に増えた photo 系 accessor 群を整理してください。

候補:

- `WizardPhotoContext`
- `WizardPhotoService`
- `WizardCoverContext`

最低限、次のどちらかは実施してください。

1. photo 系 accessor を private helper 群へ分ける
2. photo 系 accessor を小さな context/service オブジェクトへまとめる

`ReportWizard` 自体が単なる転送メソッドの集積になるのを避けてください。

### Task 4: Cover / Overview / Work Content の値境界を明確にする

`OverviewFormPage` と `WorkContentPage` について、GUI 表示用の既定値と、最終出力用の構造組み立て責務を整理してください。

少なくとも、以下のいずれかを導入してください。

- `OverviewDefaults`
- `CoverDisplayInfo`
- `WorkContentDefaults`

目的は、GUI ラベル反映と、`collect_overview_data()` / `collect_work_groups()` の出力構築が、今後さらに分けやすくなる土台を作ることです。

この段階では、出力 schema 自体を変えないでください。

### Task 5: 残す責務と見送る責務を明確にする

最後に、最低限次の 3 区分で整理してください。

- `ReportWizard` に残す責務
- 各 page に残す責務
- helper / context / service へ移した責務

また、今回あえて見送ったものも短く整理してください。

## Suggested File Targets

必要なら、次のようなファイルを検討してください。

- `src/work_report_maker/gui/main_window.py`
- `src/work_report_maker/gui/pages/photo_arrange_page.py`
- `src/work_report_maker/gui/pages/photo_description_page.py`
- `src/work_report_maker/gui/pages/overview_form_page.py`
- `src/work_report_maker/gui/pages/work_content_page.py`
- 新規 helper 候補: `src/work_report_maker/gui/wizard_contexts.py`
- 新規 helper 候補: `src/work_report_maker/gui/photo_wizard_context.py`
- 新規 helper 候補: `src/work_report_maker/gui/overview_defaults.py`

ただし、ファイル数を増やしすぎないでください。最初は 1〜3 個の小さな抽出で十分です。

## Required Verification

最低限、次を実行してください。

- `tests/gui/test_report_wizard_integration.py`
- `tests/gui/test_photo_import_page.py`
- `tests/gui/test_photo_arrange_page.py`
- `tests/gui/test_photo_description_helpers.py`
- `tests/gui/test_photo_description_page.py`

最低限確認すべき観点:

- wizard の前後移動が維持されること
- cover と overview の値が各ページへ正しく伝播すること
- photo description defaults が current form values を反映すること
- arrange された写真列が完了時の出力へ反映されること
- 画像処理中の close で cancel 動作が維持されること
- Arrange / Description が、テスト用の軽量 wizard fixture でも動くこと

必要なら、今回抽出した pure helper に対する単体テストを追加してください。

## Non-Goals

この段階では、次のことはやらないでください。

- 全ページを shared state object に全面移行すること
- `QWizard` 自体をやめること
- GUI の見た目変更
- report schema の変更
- `PhotoItem` の再設計
- 既存の GUI テストを大規模に書き換えること

## Completion Criteria

次の状態になったら完了とみなしてください。

- `ReportWizard` の責務が今より明確に整理されている
- `PhotoArrangePage` / `PhotoDescriptionPage` の fallback 互換コードがページ本体から薄くなっている
- photo 系アクセスで、読み取りと更新の境界が以前より明確になっている
- overview / work content が、GUI 表示責務と出力組み立て責務を分けやすい形へ前進している
- 必須テストが通る
- 今回見送った残タスクが短く整理されている

## Optional Stretch

余力があれば、次も検討してください。

- `accept()` 用の report build 専用 helper を導入する
- `closeEvent()` の停止処理を、photo operation service 側へさらに寄せる
- テスト側で使う軽量 wizard stub を共通 helper 化する