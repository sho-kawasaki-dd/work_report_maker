# Prompt: Consolidate Lightweight Wizard Stubs

あなたの対象は、現時点で `plan-guiResponsibilityClarification.prompt.md` まで反映された GUI テスト群です。目的は、photo arrange / description まわりの GUI テストで散在し始めている lightweight wizard stub を、既存テストの意図と coverage を維持したまま小さな helper へまとめることです。

この prompt はテストの大規模書き換えを求めるものではありません。重複している最小限の wizard fixture 構築だけを共通化し、fallback 互換確認を保ちやすくすることを優先してください。

## Goal

- photo 系 GUI テストで使う lightweight wizard stub を共通 helper 化する
- Arrange / Description が fallback 互換で動くことを検証しやすくする
- テスト意図を崩さず、重複した stub 構築コードを減らす
- 既存の GUI テストを壊さない

## Primary Concerns To Address

現時点で特に責務が曖昧になりやすいのは、少なくとも次の 4 点です。

1. test ごとに `QWizard` と private page 属性のセットアップが重複しやすいこと
2. fallback 互換のための軽量 stub 生成方法が各テストで散らばること
3. Arrange / Description の依存境界をテスト側で説明しづらいこと
4. 今後 context 導入が進むと、stub と本番 wizard の境界確認が曖昧になりやすいこと

## Constraints

- 既存テストの assertion 意図を変えない
- coverage を落とさない
- `QWizard` ベースの lightweight fixture は維持してよい
- private 属性依存テストを今回ただちに排除しない
- helper 化は最小限にとどめる

## Recommended Implementation Order

次の順番を推奨します。

1. 重複している wizard stub 構築パターンを棚卸しする
2. photo import / arrange / description 用の最小 helper を導入する
3. 重複の大きいテストだけ helper へ寄せる
4. fallback 互換を検証する観点を維持できているか確認する

## Implementation Tasks

### Task 1: Stub 構築パターンを棚卸しする

少なくとも以下を分類してください。

- `QWizard` だけを使う軽量 fixture
- `_photo_import_page` を直接差し込む fixture
- `_photo_arrange_page` を直接差し込む fixture
- 本物の `ReportWizard` を使う統合寄り fixture

その上で、共通化してよい部分と test ごとに残す部分を分けてください。

### Task 2: 最小 helper を導入する

重複の大きい wizard stub 構築を helper へ寄せてください。

候補:

- `tests/gui/helpers.py`
- `tests/gui/photo_wizard_fixtures.py`
- `tests/gui/wizard_stubs.py`

ただし、helper は過剰に抽象化しないでください。テストが何を組み立てているか読みやすいことを優先してください。

### Task 3: Arrange / Description の fallback 互換テストを保つ

今回の helper 化で、以下の観点が見えなくならないようにしてください。

- accessor が無くても private page fallback で動くこと
- lightweight wizard fixture でも initialize / move / sync が機能すること
- `ReportWizard` を使う統合テストとは別の責務であること

必要なら、helper の命名でその意図が読み取れるようにしてください。

### Task 4: 重複だけを削る

すべてのテストを helper に寄せる必要はありません。以下を優先してください。

- 同じ `QWizard` + page 差し込みを繰り返している箇所
- 同じ photo item 準備を繰り返している箇所
- fallback 用の private 属性セットアップを繰り返している箇所

一方で、test の文脈が読みにくくなるなら無理に共通化しないでください。

### Task 5: 残す責務と見送る責務を明確にする

最後に、最低限次の 3 区分で整理してください。

- 各テストファイルに残した責務
- helper に移した責務
- 今回見送った責務

## Suggested File Targets

- `tests/gui/test_photo_arrange_page.py`
- `tests/gui/test_photo_description_page.py`
- `tests/gui/test_photo_import_page.py`
- 新規 helper 候補: `tests/gui/wizard_stubs.py`

## Required Verification

最低限、次を実行してください。

- `tests/gui/test_photo_arrange_page.py`
- `tests/gui/test_photo_description_page.py`
- `tests/gui/test_photo_import_page.py`

最低限確認すべき観点:

- Arrange が lightweight wizard stub でも動くこと
- Description が lightweight wizard stub または `ReportWizard` で従来どおり動くこと
- fallback 互換の確認が helper 化で失われていないこと
- テストの可読性が極端に悪化していないこと

必要なら、新しい helper 自体に対する薄いテストを追加してください。

## Non-Goals

この段階では、次のことはやらないでください。

- GUI テスト全体の全面的な fixture 再設計
- pytest plugin や conftest の大規模整理
- 本番コード側の設計変更
- private 属性依存テストの全面廃止

## Completion Criteria

次の状態になったら完了とみなしてください。

- lightweight wizard stub 構築の重複が今より減っている
- fallback 互換を確認するテスト意図が保たれている
- Arrange / Description / Import の主要 GUI テストが通る
- helper に寄せた責務と見送った責務が短く整理されている

## Optional Stretch

余力があれば、次も検討してください。

- photo item 生成 helper の共通化
- `ReportWizard` 統合テストと lightweight stub テストの役割分離を README かテストコメントで補強する
- fallback 互換専用の小さなテストファイルを追加して意図を固定する