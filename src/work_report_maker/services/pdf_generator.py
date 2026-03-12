from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from work_report_maker.config import (
    DEPENDENCIES_DIR,
    OUTPUT_PDF,
    PROJECT_ROOT,
    TEMPLATES_DIR,
    configure_weasyprint_runtime,
)
from work_report_maker.models.loader import detect_report_format, load_input_data
from work_report_maker.models.validator import validate_report_data
from work_report_maker.services.report_adapter import build_report_from_raw

_weasyprint_html_class: type | None = None


def _get_html_class() -> type:
    global _weasyprint_html_class
    if _weasyprint_html_class is None:
        configure_weasyprint_runtime()
        try:
            from weasyprint import HTML
        except OSError as exc:
            raise RuntimeError(
                "Failed to load WeasyPrint runtime libraries from the bundled dependencies directory: "
                f"{DEPENDENCIES_DIR}"
            ) from exc
        _weasyprint_html_class = HTML
    return _weasyprint_html_class


def _resolve_photo_uri(photo_path: str | None) -> str | None:
    if not photo_path:
        return None
    if photo_path.startswith("file://"):
        return photo_path

    resolved_path = Path(photo_path)
    if not resolved_path.is_absolute():
        resolved_path = PROJECT_ROOT / resolved_path
    if not resolved_path.exists():
        return None
    return resolved_path.resolve().as_uri()


def _normalize_report_data(report_data: dict[str, Any]) -> dict[str, Any]:
    report_format = detect_report_format(report_data)
    normalized_report = build_report_from_raw(report_data) if report_format == "raw" else deepcopy(report_data)

    validate_report_data(normalized_report)
    return normalized_report


def load_report_data(json_path: Path | None = None) -> dict[str, Any]:
    return _normalize_report_data(load_input_data(json_path))


def prepare_report_for_render(report_data: dict[str, Any]) -> dict[str, Any]:
    prepared_report = _normalize_report_data(report_data)

    for page in prepared_report["photo_pages"]:
        for item in page:
            photo_path = item.get("photo_path")
            item["photo_path"] = _resolve_photo_uri(photo_path if isinstance(photo_path, str) else None)

    return prepared_report


def build_report_context(json_path: Path | None = None) -> dict[str, Any]:
    return prepare_report_for_render(load_input_data(json_path))


def generate_full_report(
    report_data: dict[str, Any] | None = None,
    *,
    json_path: Path | None = None,
    output_path: Path = OUTPUT_PDF,
) -> None:
    if report_data is not None and json_path is not None:
        raise ValueError("Pass either report_data or json_path, not both.")

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("report_tmp.html")

    report_context = prepare_report_for_render(report_data) if report_data is not None else build_report_context(json_path)
    html_content = template.render(report=report_context)

    HTML = _get_html_class()
    HTML(string=html_content, base_url=str(TEMPLATES_DIR.resolve())).write_pdf(output_path)
