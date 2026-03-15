"""work_report_maker パッケージのエントリーポイント。

起動モード:
    python -m work_report_maker          → 従来の CLI モード（最適化込み PDF 生成）
    python -m work_report_maker --gui    → PySide6 GUI ウィザードを起動
    python -m work_report_maker --no-optimize-pdf → PDF 最適化を無効にして CLI 生成
"""

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    """CLI 入口の引数仕様を 1 か所にまとめて返す。"""

    parser = argparse.ArgumentParser(description="Generate work report PDFs from CLI or launch the GUI.")
    parser.add_argument("--gui", action="store_true", help="Launch the PySide6 GUI wizard.")

    optimize_group = parser.add_mutually_exclusive_group()
    optimize_group.add_argument(
        "--optimize-pdf",
        dest="optimize_pdf",
        action="store_true",
        help="Run pikepdf structure optimization after CLI PDF generation.",
    )
    optimize_group.add_argument(
        "--no-optimize-pdf",
        dest="optimize_pdf",
        action="store_false",
        help="Skip pikepdf structure optimization for CLI PDF generation.",
    )
    parser.set_defaults(optimize_pdf=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI と GUI の 2 つの起動経路を切り替える。

    GUI でも最終的には同じ report 生成パイプラインへ合流するが、ここでは entry point を分け、
    Qt 依存 import を `--gui` 指定時だけに遅延させている。
    """

    args = _build_parser().parse_args(argv)

    if args.gui:
        # GUI モードでは Qt 側が未使用環境でも import 失敗しないよう、ここで遅延 import する。
        from PySide6.QtWidgets import QApplication

        from work_report_maker.gui.main_window import ReportWizard

        app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
        wizard = ReportWizard()
        wizard.show()
        sys.exit(app.exec())
    else:
        # CLI と GUI は同じ generate_full_report() を通すが、CLI 側だけ最適化フラグを受け取る。
        from work_report_maker.services.pdf_generator import generate_full_report

        generate_full_report(optimize_pdf=args.optimize_pdf)


if __name__ == "__main__":
    main()
