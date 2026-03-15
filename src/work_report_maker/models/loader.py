"""report 入力 JSON の読込とフォーマット判定を担当する。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from work_report_maker.config import DEFAULT_REPORT_JSON, LEGACY_REPORT_JSON, PROJECT_ROOT


def detect_report_format(report_data: dict[str, Any]) -> str:
    """入力が raw 形式か render-ready 形式かを判定する。

    現行実装では `photos` と `photo_pages` のどちらか一方だけが存在することを前提にしている。
    両方ある場合は、どちらを正とすべきか決められないため明示的にエラーにする。
    """

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
    """既定の入力 JSON パスを解決する。

    互換性のため、既定パスが存在せず legacy report が存在する場合だけ legacy 側へフォールバックする。
    呼び出し側が明示的に `json_path` を渡した場合は、この自動切り替えを行わない。
    """

    source_path = json_path or DEFAULT_REPORT_JSON
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path

    if json_path is None and not source_path.exists() and LEGACY_REPORT_JSON.exists():
        return LEGACY_REPORT_JSON

    return source_path


def load_json_file(json_path: Path | None = None) -> dict[str, Any]:
    """JSON ファイルを辞書として読み込む。"""

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
