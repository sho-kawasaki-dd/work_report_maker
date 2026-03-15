from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from work_report_maker import __main__


def test_main_cli_optimizes_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _generate_full_report(*, optimize_pdf=True, **kwargs) -> None:
        captured["optimize_pdf"] = optimize_pdf
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "work_report_maker.services.pdf_generator.generate_full_report",
        _generate_full_report,
    )

    __main__.main([])

    assert captured["optimize_pdf"] is True


def test_main_cli_can_disable_optimization(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _generate_full_report(*, optimize_pdf=True, **kwargs) -> None:
        captured["optimize_pdf"] = optimize_pdf
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "work_report_maker.services.pdf_generator.generate_full_report",
        _generate_full_report,
    )

    __main__.main(["--no-optimize-pdf"])

    assert captured["optimize_pdf"] is False