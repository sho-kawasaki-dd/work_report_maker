from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from work_report_maker.config import DEFAULT_REPORT_JSON, LEGACY_REPORT_JSON, PROJECT_ROOT


def detect_report_format(report_data: dict[str, Any]) -> str:
    has_photo_pages = "photo_pages" in report_data
    has_photos = "photos" in report_data

    if has_photo_pages and has_photos:
        raise ValueError("Report input must contain either photo_pages or photos, not both.")
    if has_photo_pages:
        return "render-ready"
    if has_photos:
        return "raw"

    raise ValueError("Report input must contain either photo_pages or photos.")


def resolve_input_path(json_path: Path | None = None) -> Path:
    source_path = json_path or DEFAULT_REPORT_JSON
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path

    if json_path is None and not source_path.exists() and LEGACY_REPORT_JSON.exists():
        return LEGACY_REPORT_JSON

    return source_path


def load_json_file(json_path: Path | None = None) -> dict[str, Any]:
    source_path = resolve_input_path(json_path)

    try:
        with source_path.open("r", encoding="utf-8") as file:
            report_data = json.load(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Report JSON file was not found: {source_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Report JSON could not be parsed: {source_path}") from exc

    if not isinstance(report_data, dict):
        raise TypeError("Report JSON root must be a JSON object.")

    return report_data


def load_input_data(json_path: Path | None = None) -> dict[str, Any]:
    return load_json_file(json_path)
