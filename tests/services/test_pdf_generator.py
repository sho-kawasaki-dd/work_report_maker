from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from work_report_maker.config import PROJECT_ROOT, TEMPLATES_DIR
from work_report_maker.models.loader import load_input_data
from work_report_maker.services.pdf_generator import generate_full_report, prepare_report_for_render


_DUMMY_PHOTO_PATH = PROJECT_ROOT / "tests" / "temp" / "IMG_20260218_215726354.jpg"


def _build_raw_report_with_photo_count(photo_count: int) -> dict:
    raw_report = deepcopy(load_input_data())
    base_photos = raw_report["photos"]
    assert base_photos
    assert _DUMMY_PHOTO_PATH.exists()

    raw_report["photos"] = [
        {
            **deepcopy(base_photos[index % len(base_photos)]),
            "no": index + 1,
            "photo_path": str(_DUMMY_PHOTO_PATH),
        }
        for index in range(photo_count)
    ]
    return raw_report


def _render_page_count(report_data: dict) -> int:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report_tmp.html")
    report_context = prepare_report_for_render(report_data)
    html_content = template.render(report=report_context)

    from work_report_maker.services.pdf_generator import _get_html_class

    html_class = _get_html_class()
    document = html_class(
        string=html_content,
        base_url=str(TEMPLATES_DIR.resolve()),
    ).render()
    return len(document.pages)


def test_generate_full_report_keeps_500_photos_at_three_per_page(tmp_path: Path) -> None:
    raw_report = _build_raw_report_with_photo_count(100)
    prepared_report = prepare_report_for_render(raw_report)

    assert len(prepared_report["photo_pages"]) == 34
    assert all(len(page) <= 3 for page in prepared_report["photo_pages"])
    assert sum(len(page) for page in prepared_report["photo_pages"]) == 100

    rendered_page_count = _render_page_count(raw_report)

    assert rendered_page_count == 36

    output_path = tmp_path / "full_report_500_photos.pdf"
    generate_full_report(report_data=raw_report, output_path=output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0