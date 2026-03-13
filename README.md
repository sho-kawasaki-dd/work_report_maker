# work-report-maker

このプロジェクトは、Jinja2 で組み立てた HTML を WeasyPrint で PDF に変換して、現場写真付きの業務報告書を生成します。
標準入力は GUI と相性のよい raw JSON で、`services/pdf_generator.py` がそれを Jinja 用の完成形 `report` に変換して PDF を生成します。

## プロジェクト構成

レイヤードアーキテクチャを採用し、依存方向を一方向に保っています。

```
work_report_maker/
├── pyproject.toml                    # プロジェクト定義 (hatchling, src layout)
├── src/
│   └── work_report_maker/           # メインパッケージ
│       ├── __init__.py
│       ├── __main__.py              # python -m work_report_maker エントリポイント
│       ├── config.py                # 定数・パス定義・WeasyPrint ランタイム設定
│       ├── models/
│       │   ├── __init__.py
│       │   ├── loader.py            # JSON I/O, パス解決, フォーマット判定
│       │   └── validator.py         # バリデーション (raw & render-ready)
│       ├── services/
│       │   ├── __init__.py
│       │   ├── report_adapter.py    # raw → render-ready 変換
│       │   ├── pdf_generator.py     # Jinja2 テンプレート描画 + WeasyPrint PDF出力
│       │   └── image_processor.py   # 画像読み込み・リサイズ・圧縮・ZIP展開
│       └── gui/                     # QWizard ベースの GUI
│           ├── __init__.py
│           ├── main_window.py       # ReportWizard (メインウィンドウ)
│           ├── preset_manager.py    # 建物プリセット・会社情報の永続化
│           ├── dialogs/
│           │   ├── building_preset_dialog.py  # 建物プリセット読込ダイアログ
│           │   └── company_editor_dialog.py   # 会社情報編集ダイアログ
│           └── pages/
│               ├── project_name_page.py   # Step 1: プロジェクト名
│               ├── cover_form_page.py     # Step 2: 表紙情報
│               ├── overview_form_page.py  # Step 3: 工事概要
│               ├── work_content_page.py   # Step 4: 作業内容
│               ├── photo_import_page.py   # Step 5: 写真インポート
│               ├── photo_arrange_page.py  # Step 6: 写真並び替え
│               └── photo_description_page.py # Step 7: 写真説明
├── templates/                        # Jinja2 テンプレート (HTML/CSS)
├── data/                             # 入力 JSON サンプル
├── fonts/                            # カスタムフォント置き場
├── dependencies/                     # WeasyPrint 用ネイティブライブラリ (Windows)
└── Documentation/                    # 設計メモ等
```

### レイヤー間の依存方向

```
config.py             ← 依存なし (最下層)
    ↑
models/validator.py   ← 依存なし
    ↑
models/loader.py      ← config
    ↑
services/report_adapter.py  ← models.validator
    ↑
services/pdf_generator.py   ← config, models.loader, models.validator, services.report_adapter
    ↑
gui/                        ← services, models, config (最上層)
```

| レイヤー                   | 責務                                                               |
| -------------------------- | ------------------------------------------------------------------ |
| `config`                   | パス定数、WeasyPrint ランタイム環境変数の設定                      |
| `models/validator`         | JSON 構造の型検証 (raw 形式・render-ready 形式)                    |
| `models/loader`            | JSON ファイルの読み込み、入力パス解決、フォーマット判定            |
| `services/report_adapter`  | raw JSON → render-ready JSON 変換 (テキスト行分割・写真ページ分割) |
| `services/pdf_generator`   | Jinja2 テンプレート描画、WeasyPrint による PDF 出力                |
| `services/image_processor` | 画像読み込み・4:3 クロップ・リサイズ・JPEG/PNG 圧縮・ZIP 展開      |
| `gui`                      | QWizard ベースのウィザード UI、プリセット永続化                    |

## WeasyPrint の依存関係

WeasyPrint は Python パッケージを入れるだけでは動かず、実行時にネイティブライブラリも必要です。Windows では主に次の系統のライブラリに依存します。

- Cairo: PDF 描画に使用
- Pango / HarfBuzz / FriBidi: 文字組みと日本語を含むテキスト描画に使用
- GObject / GLib: WeasyPrint が参照する GTK 系ライブラリの基盤
- GDK-Pixbuf: PNG や JPEG などの画像読み込みに使用
- Fontconfig / FreeType: フォント検出とフォント読み込みに使用

これらは `pip install weasyprint` だけでは Windows 上で自動的に揃わないため、DLL や設定ファイルが見つからないと import 時点で失敗します。

## このプロジェクトでの依存関係の解決方法

このプロジェクトでは、WeasyPrint の実行に必要なネイティブ依存を [dependencies](dependencies) に同梱しています。主な内容は次のとおりです。

- [dependencies/bin](dependencies/bin): Cairo、Pango、GLib、Fontconfig などの DLL 群
- [dependencies/lib/gdk-pixbuf-2.0/2.10.0/loaders](dependencies/lib/gdk-pixbuf-2.0/2.10.0/loaders): 画像 loader
- [dependencies/etc/fonts](dependencies/etc/fonts): Fontconfig 設定
- [dependencies/share](dependencies/share): GLib / GTK 系の共有データ

`config.py` の `configure_weasyprint_runtime()` が WeasyPrint を import する前にこれらのパスを環境変数へ設定し、同梱済みの DLL と設定ファイルを参照するようにしています。具体的には次の初期化を行います。

- `PATH` と `os.add_dll_directory()` に [dependencies/bin](dependencies/bin) を追加
- `GDK_PIXBUF_MODULEDIR` を画像 loader ディレクトリへ設定
- `FONTCONFIG_PATH` と `FONTCONFIG_FILE` を [dependencies/etc/fonts](dependencies/etc/fonts) 配下へ設定
- `XDG_DATA_DIRS` に [dependencies/share](dependencies/share) を追加

これにより、利用者が別途 GTK や Cairo をシステムへインストールしなくても、このリポジトリ内のファイルだけで WeasyPrint を起動できる構成になっています。

## 実行方法

### PDF 直接生成（CLI）

仮想環境に Python パッケージを入れた状態で、プロジェクトルートから実行します。

```powershell
uv run python -m work_report_maker
```

正常に実行されると、プロジェクトルートに `full_report.pdf` が出力されます。

### GUI モード

```powershell
uv run python -m work_report_maker --gui
```

QWizard ベースのウィザード形式 UI が起動します。ページ構成は以下のとおりです。

| Step | ページ               | 内容                                                                             |
| ---- | -------------------- | -------------------------------------------------------------------------------- |
| 1    | ProjectNamePage      | プロジェクト名（必須）                                                           |
| 2    | CoverFormPage        | 表紙情報（報告書作成年月日・提出先・工事作業名・作業場所名・建物名・住所・日時） |
| 3    | OverviewFormPage     | 工事概要（施工担当：現場責任者 / 現場作業者）                                    |
| 4    | WorkContentPage      | 作業内容（先頭固定グループ ＋ 動的追加グループ ＋ サブグループ）                 |
| 5    | PhotoImportPage      | 写真インポート（フォルダ一括 / ファイル選択 / ZIP 対応、圧縮設定）               |
| 6    | PhotoArrangePage     | 写真並び替え・追加・削除（D&D / 矢印ボタン / ズーム）                            |
| 7    | PhotoDescriptionPage | 写真説明入力（1/2/4 枚表示、PageUp/PageDown、前後 1 件移動、説明編集）           |

#### 表紙から工事概要への自動流用

Step 2（表紙）で入力した以下の項目は、Step 3（工事概要）の `info_rows` に自動反映されます。Step 2 に戻って値を変更した場合も、Step 3 再表示時に追従します。

| 表紙のフィールド | 工事概要の info_rows |
| ---------------- | -------------------- |
| 建物名           | 施工対象・名称       |
| 作業場所名       | 施工場所             |
| 工事・作業名     | 施工内容             |
| 日時             | 施工日時             |

#### 施工担当

「現場責任者」と「現場作業者」をそれぞれ QLineEdit で入力します。collect 時に先頭へ `現場責任者　` / `現場作業者　` のプレフィックスが自動付与されます。

#### 作業内容グループ（Step 4）

- **先頭固定グループ**: marker `◎`、title は表紙の工事・作業名を自動設定。lines は QTextEdit で自由入力（改行区切り）。
- **追加グループ**: 「グループ追加」ボタンで動的に追加。marker は `1)`, `2)`, ... で自動採番（QLineEdit なので手動変更可）。
- **サブグループ（1 階層）**: 各追加グループ内の「サブグループ追加」ボタンで動的追加。marker は `1-a)`, `1-b)`, ... で自動採番。
- collect 時には GUI 上の親子構造がフラットな `work_groups` リストに展開されます（テンプレート HTML 側の変更は不要）。

#### 固定値・自動導出

以下の値は GUI 入力なしで固定またはプリセットから自動生成されます。

| フィールド                    | 値                                                                    |
| ----------------------------- | --------------------------------------------------------------------- |
| `overview.title`              | `"工 事 完 了 報 告 書"`                                              |
| `overview.work_section_title` | `"作業内容"`                                                          |
| `overview.note_line`          | `"※ 仕上り品質報告書 『別紙写真参照』"`                               |
| `overview.ending`             | `"以上"`                                                              |
| `overview.blank_line_count`   | `12`                                                                  |
| `overview.company_lines`      | 会社情報 JSON（`~/.work_report_maker/company_info.json`）から自動導出 |

#### 写真インポート（Step 5）

報告書 3 ページ目以降の写真ページに使用する画像を読み込みます。

- **フォルダ読込**: フォルダを選択すると、フォルダ内の `.jpg` / `.jpeg` / `.png` ファイルと `.zip` を一括読み込みします。
- **ファイル選択**: 個別のファイルを選択して読み込みます。ZIP ファイルも選択可能で、ZIP 内の画像を自動展開します（ネスト ZIP も再帰展開、深さ上限 5）。
- **圧縮設定**: DPI（72–300、デフォルト 150）、JPEG 品質（10–100、デフォルト 75）、PNG 品質（10–100、デフォルト 75）をスライダーで調整できます。pngquant がインストールされていない場合は Pillow の減色処理にフォールバックします。
- **アスペクト比**: 4:3 でない画像は中央を基準に自動クロップされます。画像の端が途切れる可能性があります。
- 読み込み処理はバックグラウンドスレッドで実行され、モーダルなプログレスダイアログで進捗を表示します。キャンセル可能です。
- 1 枚以上の画像が読み込まれていないと「次へ」に進めません。

#### 写真並び替え（Step 6）

読み込んだ写真のサムネイルをグリッド表示し、順序の変更・追加・削除を行います。

- **ドラッグ＆ドロップ**: サムネイルをドラッグして並び替えできます。
- **矢印ボタン / キーバインド**: ← → ボタンで選択中の写真を移動します。複数選択時は相対順序を維持したまま一括移動します。1 枚だけ選択しているときは `Ctrl + ←` で 1 つ前、`Ctrl + →` で 1 つ後ろへ移動できます。
- **番号表示**: 各サムネイルのキャプションにはファイル名ではなく、現在の並び順に対応した通し番号を表示します。並び替え、追加、削除のたびに自動更新されます。
- **写真追加**: Step 5 と同じファイル選択ダイアログで追加読み込みできます。圧縮設定は Step 5 のスライダー値が適用されます。挿入位置は選択中の先頭アイテムの直後（未選択なら末尾）です。
- **削除**: 選択中の写真を削除します（Delete キーまたは削除ボタン）。確認ダイアログが表示されます。
- **ズーム**: 下部のスライダー（50%–200%、25%刻み、既定 100%）でサムネイルサイズをリアルタイムに変更できます。100% は 128px 相当です。
- **ページ区切り**: 3 枚ごとにページ境界が破線で表示されます。

#### 写真説明（Step 7）

Step 6 の並び順を引き継いで、各写真の説明値を編集します。最終的にここで編集した値が `photos` 配列へ反映され、PDF 生成にも渡されます。

- **表示モード**: 1 枚 / 2 枚 / 4 枚表示を切り替えできます。2 枚 / 4 枚モードでは「現在位置から連続した写真」を同時表示します。
- **写真 No 表示**: 各フォームの写真 No は読み取り専用で、現在の並び順に応じて自動再計算されます。
- **編集項目**: `現場` `施工日` `施工箇所` `施工内容` `備考` を写真ごとに編集できます。サムネイルも各フォームに併記されます。
- **対象切替**: `前の写真` / `次の写真` ボタンと `PageUp` / `PageDown` で現在位置を切り替えられます。
- **前後 1 件移動**: `写真を一つ前に移動` / `写真を一つ後ろに移動` は、現在位置ではなくフォーカス中の写真に対して適用されます。移動後も同じ PhotoItem が編集対象のまま維持されます。
- **フォーカス表示**: フォーカス中の編集フォームは薄い青の背景と枠線で強調表示されます。クリックや Tab 移動で操作対象が切り替わります。
- **既定値の由来**: 新規写真の `現場` は Step 3 の「施工対象・名称」、`施工日` は Step 2 の開始日、`施工箇所` は Step 3 の「施工場所」から初期注入されます。
- **未編集項目のみ再同期**: Step 2 / Step 3 に戻って値を変更した場合、Step 7 再入場時に `現場` `施工日` `施工箇所` のうち未編集項目だけが最新値へ更新されます。手動編集済みの項目は保持されます。

#### プリセット機能

- **建物プリセット**: 提出先・建物名・住所を保存 / 読込できます。保存先は `~/.work_report_maker/building_presets.json`。
- **会社情報**: 社名・郵便番号・住所・TEL・FAX を保存 / 読込できます。保存先は `~/.work_report_maker/company_info.json`。表紙の会社情報と工事概要の `company_lines` の両方で使用されます。

## 入力データ

- 標準のサンプル入力は [data/raw_report.json](data/raw_report.json) にあります。
- raw JSON では、写真は `photos` の一次元配列で管理します。ページ分割、行分割、`font_size_pt`、`layout_mode` は Python 側で補完します。
- GUI の Step 7 で編集した `site` `work_date` `location` `work_content` `remarks` も raw JSON の `photos` 配列へそのまま流れます。文字数に応じた行分割と文字サイズ調整は `services/report_adapter.py` 側で補完します。
- HTML テンプレートは [templates/report_tmp.html](templates/report_tmp.html) で、Jinja には完成形の `report` が渡されます。
- 写真の `photo_path` には、プロジェクトルート基準の相対パス、絶対パス、`file://` URI のいずれも使えます。存在しない場合はテンプレート側でプレースホルダ表示になります。

GUI を追加する場合は、フォーム入力を raw JSON と同じ構造の辞書にまとめて `services/pdf_generator.py` の `generate_full_report(...)` に渡せます。`photo_pages` や `lines` を GUI 側で組み立てる必要はありません。

```python
from pathlib import Path

from work_report_maker.models.loader import load_input_data
from work_report_maker.services.pdf_generator import generate_full_report

raw_report = load_input_data(Path("data/raw_report.json"))
generate_full_report(report_data=raw_report)
```

raw JSON を差し替えるだけでレポート内容を変更したい場合は、[data/raw_report.json](data/raw_report.json) を編集してから再度 `uv run python -m work_report_maker` を実行してください。

移行期間中は、従来の完成形 JSON である [data/report.json](data/report.json) も引き続き読み込めます。こちらはデバッグ用、比較用、変換結果の確認用と考えてください。

## 補足

- 現在の同梱構成は Windows での実行を前提にしています。
- 画像 loader cache を追加で同梱していないため、画像読み込みで問題が出る場合は `gdk-pixbuf` の cache 生成を追加検討してください。
- GUI 実装時の再利用入口:
  - `work_report_maker.models.loader.load_input_data(...)` — JSON 読み込み
  - `work_report_maker.services.pdf_generator.prepare_report_for_render(...)` — render-ready 変換 + 写真 URI 解決
  - `work_report_maker.services.pdf_generator.generate_full_report(...)` — PDF 生成
- raw JSON から完成形への変換ロジックは `services/report_adapter.py` に分離してあります。
- WeasyPrint は PDF 生成時にのみ遅延 import されるため、GUI 起動時の読み込み速度には影響しません。
