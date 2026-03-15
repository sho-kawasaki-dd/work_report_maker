"""work_report_maker パッケージのエントリーポイント。

起動モード:
    python -m work_report_maker          → 従来の CLI モード（PDF 生成）
    python -m work_report_maker --gui    → PySide6 GUI ウィザードを起動
"""

import sys


def main() -> None:
    """CLI と GUI の 2 つの起動経路を切り替える。

    GUI でも最終的には同じ report 生成パイプラインへ合流するが、ここでは entry point を分け、
    Qt 依存 import を `--gui` 指定時だけに遅延させている。
    """

    if "--gui" in sys.argv:
        # GUI モード: PySide6 の QApplication とウィザードを起動
        from PySide6.QtWidgets import QApplication

        from work_report_maker.gui.main_window import ReportWizard

        app = QApplication(sys.argv)
        wizard = ReportWizard()
        wizard.show()
        sys.exit(app.exec())
    else:
        # CLI モード: raw_report.json から PDF を生成（従来の動作）
        from work_report_maker.services.pdf_generator import generate_full_report

        generate_full_report()


main()
