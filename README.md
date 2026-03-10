# work-report-maker

このプロジェクトは、Jinja2 で組み立てた HTML を WeasyPrint で PDF に変換して、現場写真付きの業務報告書を生成します。

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

## 補足

- 現在の同梱構成は Windows での実行を前提にしています。
- 画像 loader cache を追加で同梱していないため、画像読み込みで問題が出る場合は `gdk-pixbuf` の cache 生成を追加検討してください。
