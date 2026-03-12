# work-report-maker

このプロジェクトは、Jinja2 で組み立てた HTML を WeasyPrint で PDF に変換して、現場写真付きの業務報告書を生成します。
標準入力は GUI と相性のよい raw JSON で、[main.py](main.py) がそれを Jinja 用の完成形 `report` に変換して PDF を生成します。

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

[main.py](main.py) は WeasyPrint を import する前にこれらのパスを環境変数へ設定し、同梱済みの DLL と設定ファイルを参照するようにしています。具体的には次の初期化を行います。

- `PATH` と `os.add_dll_directory()` に [dependencies/bin](dependencies/bin) を追加
- `GDK_PIXBUF_MODULEDIR` を画像 loader ディレクトリへ設定
- `FONTCONFIG_PATH` と `FONTCONFIG_FILE` を [dependencies/etc/fonts](dependencies/etc/fonts) 配下へ設定
- `XDG_DATA_DIRS` に [dependencies/share](dependencies/share) を追加

これにより、利用者が別途 GTK や Cairo をシステムへインストールしなくても、このリポジトリ内のファイルだけで WeasyPrint を起動できる構成になっています。

## 実行方法

仮想環境に Python パッケージを入れた状態で、プロジェクトルートから [main.py](main.py) を実行します。

```powershell
uv run .\main.py
```

正常に実行されると、プロジェクトルートに `full_report.pdf` が出力されます。

## 入力データ

- 標準のサンプル入力は [data/raw_report.json](data/raw_report.json) にあります。
- raw JSON では、写真は `photos` の一次元配列で管理します。ページ分割、行分割、`font_size_pt`、`layout_mode` は Python 側で補完します。
- HTML テンプレートは [templates/report_tmp.html](templates/report_tmp.html) で、Jinja には完成形の `report` が渡されます。
- 写真の `photo_path` には、プロジェクトルート基準の相対パス、絶対パス、`file://` URI のいずれも使えます。存在しない場合はテンプレート側でプレースホルダ表示になります。

GUI を追加する場合は、フォーム入力を raw JSON と同じ構造の辞書にまとめて [main.py](main.py) の `generate_full_report(...)` に渡せます。`photo_pages` や `lines` を GUI 側で組み立てる必要はありません。

```python
from pathlib import Path

from main import generate_full_report, load_input_data

raw_report = load_input_data(Path("data/raw_report.json"))
generate_full_report(report_data=raw_report)
```

raw JSON を差し替えるだけでレポート内容を変更したい場合は、[data/raw_report.json](data/raw_report.json) を編集してから再度 `uv run .\main.py` を実行してください。

移行期間中は、従来の完成形 JSON である [data/report.json](data/report.json) も引き続き読み込めます。こちらはデバッグ用、比較用、変換結果の確認用と考えてください。

## 補足

- 現在の同梱構成は Windows での実行を前提にしています。
- 画像 loader cache を追加で同梱していないため、画像読み込みで問題が出る場合は `gdk-pixbuf` の cache 生成を追加検討してください。
- [main.py](main.py) には `load_input_data(...)`, `load_report_data(...)`, `prepare_report_for_render(...)`, `generate_full_report(...)` を用意してあり、GUI 実装時はこの入口を再利用できます。
- raw JSON から完成形への変換ロジックは [backend/report_adapter.py](backend/report_adapter.py) に分離してあります。
