# 画像読み込み・並び替えウィザード 設計ドキュメント

## 概要

テンプレート 3 ページ目以降の写真ページ用に、画像の読み込み（フォルダ一括 / ファイル選択 / ZIP 対応）・圧縮・並び替え・追加・削除機能を提供する。

## 機能概要

| 機能         | 説明                                                     |
| ------------ | -------------------------------------------------------- |
| 画像読み込み | フォルダ一括、ファイル個別選択、ZIP 自動展開（再帰対応） |
| 圧縮         | DPI 指定リサイズ + JPEG/PNG 品質指定圧縮                 |
| 4:3 クロップ | テンプレート枠に合わせてアスペクト比 4:3 に中央クロップ  |
| 並び替え     | ドラッグ＆ドロップ、← → 矢印ボタン（複数選択対応）       |
| 追加         | 並び替え画面から直接ファイル追加（同じ圧縮設定を適用）   |
| 削除         | 選択中の写真を確認ダイアログ付きで削除                   |

## アーキテクチャ

### モジュール構成

```
services/image_processor.py    ← GUI 非依存のコアロジック
gui/pages/photo_import_page.py ← Step 5: インポート UI
gui/pages/photo_arrange_page.py← Step 6: 並び替え UI
gui/main_window.py             ← ウィザード統合
config.py                      ← 定数 (PHOTO_WIDTH_MM, PHOTO_HEIGHT_MM 等)
```

### データフロー

```
ファイル選択 / フォルダ / ZIP
        │
        ▼
collect_image_paths()  ← パス収集 (ZIP 展開含む)
        │
        ▼
process_image()        ← load → 4:3 クロップ → リサイズ → 圧縮
        │
        ▼
PhotoItem(filename, data, format, thumbnail)  ← メモリ上に保持
        │
        ▼
PhotoImportPage._photo_items  ← リスト管理
        │
        ▼
PhotoArrangePage (QStandardItemModel)  ← 並び替え・追加・削除
        │
        ▼
ReportWizard.accept() → _build_photos()
        │
        ▼
一時ファイル書き出し → photos 配列 (file:// URI)
        │
        ▼
JSON 出力 / PDF 生成
```

## 主要クラス・関数

### image_processor.py (サービス層)

| 関数                                                      | 説明                                                                                                    |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `load_image(path)`                                        | 対応拡張子 (.jpg/.jpeg/.png) の画像を読み込み                                                           |
| `resize_for_template(img, dpi)`                           | 4:3 クロップ後、テンプレートサイズ × DPI でリサイズ（元画像がターゲットより小さい場合はリサイズしない） |
| `compress_jpeg(img, quality)`                             | JPEG 圧縮 → bytes                                                                                       |
| `compress_png(img, quality_max)`                          | pngquant or Pillow quantize → bytes                                                                     |
| `is_pngquant_available()`                                 | pngquant の有無チェック                                                                                 |
| `process_image(path, dpi, jpeg_quality, png_quality_max)` | 統合パイプライン → (bytes, format)                                                                      |
| `extract_images_from_zip(zip_path, tmp_dir)`              | ZIP 再帰展開（深さ上限 5、パストラバーサル対策あり）                                                    |
| `collect_image_paths(source)`                             | フォルダ / ZIP / ファイルの統一パス収集                                                                 |

### PhotoItem (データクラス)

```python
@dataclass
class PhotoItem:
    filename: str                    # 元ファイル名
    data: bytes                      # 圧縮済みバイト列
    format: str                      # "jpeg" or "png"
    thumbnail: QImage | None = None  # サムネイル用 (最大辺 128px, KeepAspectRatio)
```

- bytes でメモリ保持（ファイル I/O を最小化）
- サムネイルは QImage で保持し、表示時に `QPixmap.fromImage()` で変換

### PhotoImportPage (Step 5)

- **読み込みボタン**: フォルダ読込 / ファイル選択
- **圧縮設定**: DPI (72–300), JPEG 品質 (10–100), PNG 品質 (10–100)
- **読み込み済みリスト**: QListWidget（アイコン付き）
- **バリデーション**: `isComplete()` → 1 枚以上
- **スレッド処理**: `_ImportWorker` (QObject) + QThread + モーダル QProgressDialog
  - バッチ処理: `_ITEM_BATCH_SIZE = 8` 件ごとに `items_ready` シグナルを送出し UI 更新回数を抑制
  - エラー処理: 個別の画像失敗は記録し、完了後に `_format_failure_message()` で先頭 3 件 + 残数を要約表示
- **ページ間同期**: `add_photo_items()` / `remove_photo_items()` で PhotoArrangePage との双方向同期
- **クリーンアップ**: `cancel_active_import()` でスレッド停止。`ReportWizard.closeEvent()` から呼び出される

### PhotoArrangePage (Step 6)

- **サムネイルグリッド**: `_PhotoArrangeListView` (QListView サブクラス, IconMode) + QStandardItemModel
- **D&D 並び替え**: `_PhotoArrangeListView` でカスタム MIME タイプ (`application/x-work-report-maker-photo-arrange`) による手動 DnD 制御。ドロップ位置はアイコン中心基準で前後判定
- **矢印ボタン**: 複数選択の相対順序維持移動
- **キーバインド**: 1 枚選択時のみ `Ctrl + ←` / `Ctrl + →` で前後に 1 件移動。未選択・複数選択・先頭 / 末尾では no-op
- **番号表示**: サムネイル下のキャプションはファイル名ではなく、現在の並び順に対応した 1 始まりの通し番号を表示
- **写真追加**: ファイル選択 → `_ImportWorker` → 選択中の先頭アイテムの直後（未選択なら末尾）に挿入。追加分は PhotoImportPage にも同期
- **削除**: 確認ダイアログ付き（Delete キー対応）。削除分は PhotoImportPage からも除去
- **ズーム**: スライダー 50%–200%（25%刻み、100% = 128px）。表示中の倍率 1 つ分だけ軽量なアイコンキャッシュを持ち、同倍率内の再描画で再デコードを避ける
- **ページ区切り**: `_PageBorderDelegate` で 3 枚ごとに破線描画
- **内部管理**: `_photo_items_by_key` (`dict[int, PhotoItem]`) で `id()` ベースのルックアップ。モデル上は `UserRole` にキーを格納
- **データ収集**: `collect_photo_items()` で並び順の PhotoItem リストを返す（`ReportWizard._build_photos()` から使用）
- **クリーンアップ**: `cancel_active_import()` でスレッド停止。`ReportWizard.closeEvent()` から呼び出される

#### Step 6 の追加テスト観点

- 単一選択時の `Ctrl + ←` / `Ctrl + →` が 1 件だけ移動すること
- 複数選択時、未選択時、先頭 / 末尾選択時のキーバインドが no-op であること
- 並び替え後もサムネイル番号が `1, 2, 3, ...` の通し番号として再計算されること
- ズームスライダーが 25% 刻みにスナップし、50% / 200% で `iconSize` と `gridSize` が期待どおり更新されること

## UI 構成

### Step 5: 写真インポート

```
┌─────────────────────────────────────────┐
│ [フォルダ読込] [ファイル選択]            │
├─────────────────────────────────────────┤
│ ┌─ 圧縮設定 ─────────────────────────┐  │
│ │ DPI:       [====●========] [150]   │  │
│ │ JPEG品質:  [=======●=====] [ 75]   │  │
│ │ PNG品質:   [=======●=====] [ 75]   │  │
│ └────────────────────────────────────┘  │
│ ※ アスペクト比が 4:3 でない画像は...    │
├─────────────────────────────────────────┤
│ 📷 IMG_0001.jpg                         │
│ 📷 IMG_0002.jpg                         │
│ 📷 IMG_0003.png                         │
│ ...                                     │
├─────────────────────────────────────────┤
│ 3 枚の画像を読み込みました  [すべてクリア] │
└─────────────────────────────────────────┘
```

### Step 6: 写真並び替え

```
┌─────────────────────────────────────────┐
│ [←] [→]              [写真追加] [削除]  │
├─────────────────────────────────────────┤
│ ┌──────┐ ┌──────┐ ┌──────┐ ┊ ┌──────┐  │
│ │ 📷   │ │ 📷   │ │ 📷   │ ┊ │ 📷   │  │
│ │ 1    │ │ 2    │ │ 3    │ ┊ │ 4    │  │
│ └──────┘ └──────┘ └──────┘ ┊ └──────┘  │
│ ┌──────┐ ┌──────┐                       │
│ │ 📷   │ │ 📷   │         ┊ = ページ区切 │
│ │ 5    │ │ 6    │                       │
│ └──────┘ └──────┘                       │
├─────────────────────────────────────────┤
│ サムネイルサイズ: 100% [====●========]   │
│ 写真 6 枚 / 2 ページ（1ページあたり 3 枚） │
└─────────────────────────────────────────┘
```

## セキュリティ考慮

- **ZIP パストラバーサル**: `extract_images_from_zip()` で展開先パスが `tmp_dir` 内であることを `resolve().relative_to()` で検証
- **ZIP 再帰爆弾**: 再帰深さ上限 `_MAX_ZIP_RECURSION = 5`
- **pngquant subprocess**: `subprocess.run()` で `capture_output=True`、入力は stdin 経由（シェルインジェクション回避）

## 定数 (config.py)

| 定数                         | 値                          | 用途                      |
| ---------------------------- | --------------------------- | ------------------------- |
| `PHOTO_WIDTH_MM`             | 100.0                       | テンプレート画像幅 (mm)   |
| `PHOTO_HEIGHT_MM`            | 75.0                        | テンプレート画像高さ (mm) |
| `SUPPORTED_IMAGE_EXTENSIONS` | `{".jpg", ".jpeg", ".png"}` | 対応画像拡張子            |

## accept() 時のデータ構造

ウィザード完了時に `_build_photos()` が生成する photos 配列:

```json
{
  "photos": [
    {
      "no": 1,
      "photo_path": "file:///C:/Users/.../wrm_photos_.../0001.jpg",
      "site": "",
      "work_date": "",
      "location": "",
      "work_content": "",
      "remarks": ""
    }
  ]
}
```

- `photo_path`: 一時ディレクトリ内のファイルを `file://` URI で参照
- メタデータ (`site`, `work_date` 等) は空文字列プレースホルダ（後続フェーズで入力 UI を追加予定）

## スコープ

- **IN**: 画像読み込み、圧縮、4:3 クロップ、並び替え、追加、削除
- **OUT**: 写真メタデータ入力（site, work_date, location, work_content, remarks）— 後続フェーズで実装
