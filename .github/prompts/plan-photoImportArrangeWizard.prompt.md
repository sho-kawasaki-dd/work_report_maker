# Plan: 画像読み込み・並び替えウィザード

## TL;DR
テンプレート3枚目以降の写真ページ用に、画像の読み込み（フォルダ一括/ファイル選択/ZIP対応）・圧縮・並び替え・追加・削除機能を実装する。4フェーズに分け、バックエンドのサービス層 → インポートUI → サムネイル並び替えUI → ウィザード統合 の順に段階構築する。

---

## Phase A: 画像処理サービス層 (image_processor.py)

**目的**: 画像の読み込み・リサイズ・圧縮のコアロジックをGUIから独立したサービスとして実装。

### Steps

1. `src/work_report_maker/services/image_processor.py` を新規作成
   - `load_image(path: Path) -> PIL.Image` — 単一画像読み込み（.jpg/.jpeg/.png のみ）
   - `resize_for_template(img: Image, dpi: int = 150) -> Image` — テンプレート上の画像サイズ（100mm × 75mm）と指定DPIからターゲットピクセル数を算出してリサイズ。計算式: `px_w = 100 * dpi / 25.4`, `px_h = 75 * dpi / 25.4`。元画像が小さければリサイズしない。`Image.LANCZOS` で縮小。この時点で、画像のアスペクト比が4:3でない場合は、中央をクロップして4:3に整形してからリサイズする
   - `compress_jpeg(img: Image, quality: int = 75) -> bytes` — Pillow でJPEG圧縮、bytesで返す
   - `compress_png(img: Image, quality_max: int = 75) -> bytes` — pngquant が利用可能なら subprocess で圧縮（quality_min = quality_max - 20）、なければ Pillow の `quantize()` でフォールバック
   - `is_pngquant_available() -> bool` — `shutil.which("pngquant")` でチェック
   - `process_image(path: Path, dpi: int, jpeg_quality: int, png_quality_max: int) -> tuple[bytes, str]` — load → resize → compress の統合パイプライン。圧縮後バイト列とフォーマット("jpeg"/"png")を返す
   
2. ZIP展開ユーティリティを同モジュールに追加
   - `extract_images_from_zip(zip_path: Path, tmp_dir: Path) -> list[Path]` — ZIP内の対象拡張子ファイルのみを tmp_dir に展開し、パスリストを返す。ZIP内部を再帰捜査し、ZIP内部にZIPがあれば再帰展開。無限ループに陥らないように、ループ数は有限とする。zipfile モジュール使用。パストラバーサル対策として展開先が tmp_dir 内であることを検証
   - `collect_image_paths(source: Path) -> list[Path]` — フォルダなら再帰走査、ZIPならtemp展開、ファイルならそのまま返す。拡張子フィルタ(.jpg/.jpeg/.png/.zip)付き
   
3. `src/work_report_maker/config.py` に定数追加
   - `PHOTO_WIDTH_MM = 105.0`
   - `PHOTO_HEIGHT_MM = 75.0`
   - `SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}`

### 対象ファイル
- `src/work_report_maker/services/image_processor.py` — 新規作成
- `src/work_report_maker/config.py` — 定数追加

---

## Phase B: 画像インポートページ (PhotoImportPage)

**目的**: フォルダ一括読み込み / ファイル選択 / ZIP対応の読み込みウィザードページと、圧縮設定UIを実装。

### Steps

4. `src/work_report_maker/gui/pages/photo_import_page.py` を新規作成
   - `PhotoImportPage(QWizardPage)` クラス
   
5. UI構成:
   - **読み込みボタン群** (QHBoxLayout):
     - 「フォルダ読込」ボタン → `QFileDialog.getExistingDirectory()` → フォルダ内の画像+ZIP一括読み込み
     - 「ファイル選択」ボタン → `QFileDialog.getOpenFileNames()` フィルタ: "画像/ZIP (*.jpg *.jpeg *.png *.zip)"
   - **圧縮設定グループ** (QGroupBox "圧縮設定"):
     - DPIスライダー (QSlider + QSpinBox): 範囲 72–300, デフォルト 150, ステップ 1
     - JPEG品質スライダー: 範囲 10–100, デフォルト 75
     - PNG品質スライダー: 範囲 10–100, デフォルト 75 (pngquant無効時はスライダーを無効化し「Pillow減色」と表示)
   - **読み込み済みリスト** (QListWidget):
     - 読み込んだファイル名一覧表示（アイコン付き）
     - 件数ラベル ("N 枚の画像を読み込みました")
   - **クリアボタン**: 読み込み済み画像をすべてクリア
   - 見やすい場所に、画像のアスペクト比が4:3でない場合はクロップされる旨の注意書きを表示（端が途切れる可能性を指摘）

6. 読み込みロジック:
   - 読み込み&圧縮は `QThread` ワーカーで実行し、**モーダルな `QProgressDialog`** で進捗表示（ダイアログ表示中はメインウィンドウ操作不可、ユーザーに待機を促す）。キャンセル可能
   - ZIP展開は `tempfile.TemporaryDirectory()` 上で行い、圧縮済みバイト列取得後に一時ファイルは自動削除
   - 各画像は `image_processor.process_image()` で圧縮し、結果を `PhotoItem` データクラスに格納:
     ```
     @dataclass
     class PhotoItem:
         filename: str
         data: bytes          # 圧縮済みバイト列
         format: str          # "jpeg" or "png"
         thumbnail: QPixmap   # サムネイル用（128x128程度）
     ```
   - `PhotoItem` リストを `PhotoImportPage` のインスタンス変数に保持
   - 追加読み込み（既存リストに追記）と全クリアの両方をサポート

7. ページバリデーション:
   - `isComplete()` → 1枚以上の画像が読み込まれていること

### 対象ファイル
- `src/work_report_maker/gui/pages/photo_import_page.py` — 新規作成

---

## Phase C: 画像並び替え・追加・削除ページ (PhotoArrangePage)

**目的**: サムネイル一覧での並び替え（D&D + 矢印）・複数選択・追加・削除機能を実装。

### Steps

8. `src/work_report_maker/gui/pages/photo_arrange_page.py` を新規作成
   - `PhotoArrangePage(QWizardPage)` クラス

9. サムネイルグリッド:
   - `QListView` を `ViewMode.IconMode` で使用
   - `QStandardItemModel` で画像データを管理
   - 各アイテムに `Qt.DecorationRole`（QIcon from thumbnail）と `Qt.UserRole`（PhotoItem参照）を格納
   - `setDragDropMode(QAbstractItemView.InternalMove)` でドラッグ＆ドロップ並び替え
   - `setSelectionMode(QAbstractItemView.ExtendedSelection)` で複数選択（Ctrl+Click, Shift+Click）
   - `setResizeMode(QListView.Adjust)` でウィンドウリサイズ時に自動再配置

10. サムネイルサイズ制御:
    - 下部にズームスライダー (QSlider): 範囲 64–256px, デフォルト 128
    - スライダー変更で `setIconSize(QSize(v, v))` をリアルタイム更新
    - `setGridSize()` もアイコンサイズに連動して余白調整

11. 並び替え操作:
    - 「←」「→」ボタン (QToolButton): 選択中のアイテム群を左/右に移動
    - 複数選択時は選択アイテム群をまとめて移動（相対順序を維持）
    - D&D時も複数選択アイテムをまとめて移動
    - ページ区切り表示: 3枚ごとに `QStyledItemDelegate` で視覚的にページ境界を描画

12. 追加操作:
    - 「写真追加」ボタン → PhotoImportPage と同じファイル選択ダイアログを開く（フォルダ/ファイル/ZIP対応）
    - 追加時も同じ圧縮設定（Phase B のスライダー値）を適用。圧縮設定は `self.wizard()._photo_import_page` 経由で参照
    - 読み込み&圧縮中は Phase B と同様に**モーダルな `QProgressDialog`** で進捗表示（メインウィンドウ操作不可）
    - 挿入位置: 選択中のアイテムの最も番号が若いものの直後。未選択なら末尾

13. 削除操作:
    - 「削除」ボタン or Delete キー → 選択中のアイテムを削除
    - 確認ダイアログ: "N 枚の画像を削除しますか？" (QMessageBox)

14. `initializePage()`:
    - PhotoImportPage の PhotoItem リストからモデルを構築
    - 前のページに戻って再度進んだ場合は、既存の並び順を維持

### 対象ファイル
- `src/work_report_maker/gui/pages/photo_arrange_page.py` — 新規作成

---

## Phase D: ウィザード統合・データフロー接続

**目的**: 新ページをウィザードに組み込み、画像データをレポート出力に接続。

### Steps

15. `main_window.py` に2ページ追加:
    - `ReportWizard.__init__()` に `_photo_import_page` と `_photo_arrange_page` を追加
    - `addPage()` で Step 5, Step 6 として追加
    - ウィザード docstring 更新

16. データ収集の接続:
    - `PhotoArrangePage.collect_photo_items() -> list[PhotoItem]` — 並び順に PhotoItem リストを返す
    - `ReportWizard.accept()` で写真データも収集し、report の `photos` 配列に組み込む
    - 各 PhotoItem から `{no, photo_path, site, work_date, location, work_content, remarks}` 構造を生成
    - 写真メタデータ（site, work_date 等）は Phase D 時点では空文字列のプレースホルダとし、後続フェーズで入力UIを追加（スコープ外）

17. 画像ファイル出力:
    - PDF生成時に PhotoItem の bytes データを一時ファイルに書き出し、`photo_path` として file:// URI を設定
    - `tempfile.TemporaryDirectory()` 内に書き出し、PDF生成完了後に自動クリーンアップ

---

## Phase E: ドキュメント作成
18. 開発ドキュメント:
    - `README.md` に 新機能の説明と使用方法を追加
    - 上記の内容をわかりやすくまとめる（目的、機能概要、UI構成、データフロー、検証手順など）
    - `Documentation/` に設計ドキュメントを追加

---

## 対象ファイル一覧

| ファイル | 操作 | 内容 |
|---------|------|------|
| `src/work_report_maker/services/image_processor.py` | 新規 | 画像読み込み・圧縮・ZIP展開サービス |
| `src/work_report_maker/gui/pages/photo_import_page.py` | 新規 | 画像インポートウィザードページ |
| `src/work_report_maker/gui/pages/photo_arrange_page.py` | 新規 | 画像並び替え・追加・削除ページ |
| `src/work_report_maker/config.py` | 修正 | テンプレート画像寸法の定数追加 |
| `src/work_report_maker/gui/main_window.py` | 修正 | 新ページ登録・accept()更新 |

---

## 検証手順

1. **Phase A 検証**: `image_processor.py` の各関数をスクリプトから直接呼び出し、(a) JPG/PNG読み込み → リサイズ → 圧縮バイト列取得、(b) ZIP展開 → 画像パスリスト取得、(c) pngquant有無でのPNG圧縮分岐 を確認
2. **Phase B 検証**: `--gui` 起動 → Step 5 到達 → フォルダ読み込み/ファイル選択/ZIP読み込みの各経路で画像がリストに追加されること、スライダー値が圧縮に反映されること、0枚で「次へ」が無効なことを確認
3. **Phase C 検証**: Step 6 でサムネイル一覧表示 → D&D並び替え/矢印ボタン並び替え/複数選択移動/追加/削除が正しく動作すること、ズームスライダーでサムネイルサイズが変わることを確認
4. **Phase D 検証**: ウィザード完了 → accept() の JSON 出力に photos 配列が含まれること、生成PDFに写真ページが正しく表示されることを確認

---

## 決定事項・スコープ

- **スコープIN**: 画像読み込み、圧縮、並び替え、追加、削除
- **スコープOUT**: 写真メタデータ入力（site, work_date, location, work_content, remarks）— 後続フェーズで実装
- **PhotoItem データクラス**: bytes でメモリ保持（ファイルI/Oを最小化）。サムネイルの QPixmap は表示用に別途保持
- **ZIP展開**: tempfile.TemporaryDirectory() で処理、圧縮バイト取得後に自動削除
- **pngquant**: subprocess 呼び出し。未インストール時は Pillow quantize() フォールバック。ユーザーへの通知はスライダーラベルで表示
- **スレッド処理**: 画像読み込み/圧縮は QThread ワーカー + モーダル QProgressDialog で実行。ダイアログ表示中はメインウィンドウ操作不可（Phase B のインポート時、Phase C の追加時いずれも同様）
- **ページ区切り表示**: QStyledItemDelegate でカスタム描画（セパレータアイテム挿入方式ではなく、描画方式を採用）
- **写真メタデータ入力**: 別ステップ（Step 7）として後続フェーズで実装予定
- **既存パターン踏襲**: QWizardPage 継承、initializePage() での前ページデータ取得、self.wizard() 経由のクロスページアクセス
