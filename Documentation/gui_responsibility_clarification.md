# GUI Responsibility Clarification

## 自己文書化の方針

- コメントは `what` の言い換えではなく、責務境界、前提条件、不変条件、副作用、なぜその実装にしているかを補うために使う。
- module/class/function docstring は役割と依存関係をまとめ、block comment は状態遷移やアルゴリズムの全体像を説明し、inline comment は分岐理由や Qt 固有の回避策だけに限定する。
- `PhotoItem identity`、`default sync`、`raw report` / `render-ready report`、`temporary photo directory` のような横断概念は語彙を統一して記述する。
- 単純な getter/setter や明白な UI 配線には冗長コメントを足さず、レビュー時に判断材料が不足する箇所へ密度を寄せる。

## ReportWizard に残す責務

- `QWizard` として各 page を生成し、画面遷移順を管理する。
- Windows 既定の `AeroStyle` ではなくフッター型の wizard style を選び、`Back` / `Next` / `Cancel` の配置を一貫させる。
- `Back` を 1 ページ目では非表示、2 ページ目以降では下部ボタン列へ表示する。
- 表紙入力から `CoverDisplayInfo` / `OverviewDefaults` / `WorkContentDefaults` を組み立てる。
- 完了時に cover / overview / photos を集約して最終 payload を構築する。
- `Cancel` 押下とウィンドウ close の両方で、プロジェクト破棄確認と終了可否判定を集約する。
- close 時に photo import / arrange の停止処理をまとめて呼び出す。
- PDF 生成成功後に終了するかどうかを Step 1 の永続設定に従って分岐する。

## 各 page に残す責務

- `PhotoImportPage`: import UI、圧縮設定の受け渡し、PhotoItem 集合の初期構築と default sync の入口。
- `PhotoArrangePage`: arrange UI、選択状態、モデル並び順、追加削除操作の画面反映。
- `PhotoDescriptionPage`: description UI、フォーカス制御、表示モード切替、現在写真の編集。
- `CoverFormPage`: 後続ページ既定値の source of truth になる表紙入力の採取と整形。
- `OverviewFormPage`: overview の表示ラベル更新と入力欄の採取。
- `WorkContentPage`: work group 編集 UI とフラットな group list の採取。

## helper / context / service へ移した責務

- `wizard_contexts.py` の `resolve_photo_wizard_context(...)` に、軽量 wizard fixture 互換の fallback 解決を集約した。
- `WizardPhotoContext` に、photo 系の読み取りと更新操作を集約した。
- `OverviewDefaults` に、overview 表示既定値と report 用 payload 組み立ての土台を集約した。
- `WorkContentDefaults` に、cover 由来の先頭 work group title を集約した。
- `load_company_lines()` に、overview 用の会社情報行生成を移した。
- `PhotoImportCompressionControls` に、import 設定 UI と worker へ渡す値の対応付けを集約した。
- `PhotoImportOperationController` に、worker/thread/progress dialog のライフサイクル管理を集約した。

## 今回見送ったもの

- 全 page を shared state object に統合する再設計。
- `accept()` 専用の report build service 抽出。
- close 時の停止処理を photo operation service へさらに寄せること。
- GUI テストで使う軽量 wizard stub の共通 helper 化。