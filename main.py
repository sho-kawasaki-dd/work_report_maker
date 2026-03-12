from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from backend.report_adapter import build_report_from_raw

PROJECT_ROOT = Path(__file__).resolve().parent
DEPENDENCIES_DIR = PROJECT_ROOT / "dependencies"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
DEFAULT_REPORT_JSON = PROJECT_ROOT / "data" / "raw_report.json"
LEGACY_REPORT_JSON = PROJECT_ROOT / "data" / "report.json"
OUTPUT_PDF = PROJECT_ROOT / "full_report.pdf"
_DLL_DIRECTORIES: list[object] = []


def _prepend_env_path(name: str, value: Path) -> None:
    current = os.environ.get(name, "")
    entries = [entry for entry in current.split(os.pathsep) if entry]
    value_str = str(value)
    if value_str not in entries:
        os.environ[name] = os.pathsep.join([value_str, *entries]) if entries else value_str


def configure_weasyprint_runtime() -> None:
    if os.name != "nt":
        return

    bin_dir = DEPENDENCIES_DIR / "bin"
    loaders_dir = DEPENDENCIES_DIR / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders"
    loaders_cache = DEPENDENCIES_DIR / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders.cache"
    fonts_dir = DEPENDENCIES_DIR / "etc" / "fonts"
    fonts_conf = fonts_dir / "fonts.conf"
    share_dir = DEPENDENCIES_DIR / "share"

    required_paths = [bin_dir, loaders_dir, fonts_dir, fonts_conf, share_dir]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        missing = "\n".join(f"- {path}" for path in missing_paths)
        raise FileNotFoundError(
            "WeasyPrint dependencies are incomplete. Missing paths:\n"
            f"{missing}"
        )

    _prepend_env_path("PATH", bin_dir)
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is not None:
        _DLL_DIRECTORIES.append(add_dll_directory(str(bin_dir)))

    os.environ["GDK_PIXBUF_MODULEDIR"] = str(loaders_dir)
    if loaders_cache.exists():
        os.environ["GDK_PIXBUF_MODULE_FILE"] = str(loaders_cache)

    os.environ["FONTCONFIG_PATH"] = str(fonts_dir)
    os.environ["FONTCONFIG_FILE"] = str(fonts_conf)
    _prepend_env_path("XDG_DATA_DIRS", share_dir)


configure_weasyprint_runtime()

try:
    from weasyprint import HTML
except OSError as exc:
    raise RuntimeError(
        "Failed to load WeasyPrint runtime libraries from the bundled dependencies directory: "
        f"{DEPENDENCIES_DIR}"
    ) from exc


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


def _require_mapping(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a JSON object.")
    return value


def _require_list(name: str, value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a JSON array.")
    return value


def _detect_report_format(report_data: dict[str, Any]) -> str:
    has_photo_pages = "photo_pages" in report_data
    has_photos = "photos" in report_data

    if has_photo_pages and has_photos:
        raise ValueError("Report input must contain either photo_pages or photos, not both.")
    if has_photo_pages:
        return "render-ready"
    if has_photos:
        return "raw"

    raise ValueError("Report input must contain either photo_pages or photos.")


def _validate_report_data(report_data: dict[str, Any]) -> None:
    required_top_level_keys = ["title", "cover", "overview", "photo_layout", "photo_pages"]
    missing_keys = [key for key in required_top_level_keys if key not in report_data]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise KeyError(f"report JSON is missing required top-level keys: {missing}")

    cover = _require_mapping("report.cover", report_data["cover"])
    cover_company = _require_mapping("report.cover.company", cover.get("company"))
    _require_list("report.cover.detail_rows", cover.get("detail_rows"))
    _require_list("report.cover.company.address_lines", cover_company.get("address_lines"))

    overview = _require_mapping("report.overview", report_data["overview"])
    _require_list("report.overview.company_lines", overview.get("company_lines"))
    info_rows = _require_list("report.overview.info_rows", overview.get("info_rows"))
    work_groups = _require_list("report.overview.work_groups", overview.get("work_groups"))
    _require_list("report.overview.blank_lines", overview.get("blank_lines"))

    for index, row in enumerate(info_rows, start=1):
        mapping = _require_mapping(f"report.overview.info_rows[{index}]", row)
        _require_list(f"report.overview.info_rows[{index}].extra_values", mapping.get("extra_values"))

    for index, group in enumerate(work_groups, start=1):
        mapping = _require_mapping(f"report.overview.work_groups[{index}]", group)
        _require_list(f"report.overview.work_groups[{index}].lines", mapping.get("lines"))

    photo_layout = _require_mapping("report.photo_layout", report_data["photo_layout"])
    labels = _require_mapping("report.photo_layout.labels", photo_layout.get("labels"))
    _require_list("report.photo_layout.labels.work_content_stacked", labels.get("work_content_stacked"))
    _require_list("report.photo_layout.labels.remarks_stacked", labels.get("remarks_stacked"))

    photo_pages = _require_list("report.photo_pages", report_data["photo_pages"])
    for page_index, page in enumerate(photo_pages, start=1):
        page_items = _require_list(f"report.photo_pages[{page_index}]", page)
        for item_index, item in enumerate(page_items, start=1):
            mapping = _require_mapping(f"report.photo_pages[{page_index}][{item_index}]", item)
            _require_mapping(
                f"report.photo_pages[{page_index}][{item_index}].work_content",
                mapping.get("work_content"),
            )
            _require_mapping(
                f"report.photo_pages[{page_index}][{item_index}].remarks",
                mapping.get("remarks"),
            )


def _resolve_input_path(json_path: Path | None = None) -> Path:
    source_path = json_path or DEFAULT_REPORT_JSON
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path

    if json_path is None and not source_path.exists() and LEGACY_REPORT_JSON.exists():
        return LEGACY_REPORT_JSON

    return source_path


def _load_json_file(json_path: Path | None = None) -> dict[str, Any]:
    source_path = _resolve_input_path(json_path)

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


def _normalize_report_data(report_data: dict[str, Any]) -> dict[str, Any]:
    report_format = _detect_report_format(report_data)
    normalized_report = build_report_from_raw(report_data) if report_format == "raw" else deepcopy(report_data)

    _validate_report_data(normalized_report)
    return normalized_report


def load_input_data(json_path: Path | None = None) -> dict[str, Any]:
    return _load_json_file(json_path)


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

    HTML(string=html_content, base_url=str(TEMPLATES_DIR.resolve())).write_pdf(output_path)


if __name__ == "__main__":
    generate_full_report()