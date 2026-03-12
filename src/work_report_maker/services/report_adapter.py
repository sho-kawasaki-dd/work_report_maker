from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Sequence, TypedDict

from work_report_maker.models.validator import require_list, require_mapping, validate_raw_report_data

PHOTO_PAGE_SIZE = 3
WORK_CONTENT_ROWS = 6
REMARKS_ROWS = 4
DEFAULT_BLANK_LINE_COUNT = 12
DEFAULT_NOTE_LINE = "※ 仕上り品質報告書 『別紙写真参照』"
DEFAULT_ENDING = "以上"
DEFAULT_WORK_SECTION_TITLE = "作業内容"
DEFAULT_PHOTO_LAYOUT = {
    "labels": {
        "status_photo": "状　況　写　真",
        "description": "写　真　説　明",
        "photo_no": "写 真 No",
        "site": "現　場",
        "work_date": "施 工 日",
        "location": "施工箇所",
        "work_content_stacked": ["施", "工", "内", "容"],
        "remarks_stacked": ["備", "考"],
    }
}


class WritingSpec(TypedDict):
    max_chars: int
    font_size_pt: float
    line_count: int
    chars_per_line: int
    mode: str


def _normalize_text(value: str | Iterable[str] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return "\n".join(str(item).strip() for item in value if str(item).strip()).strip()


def _wrap_text(text: str, chars_per_line: int, max_lines: int) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    wrapped_lines: list[str] = []
    for paragraph in normalized.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            wrapped_lines.append("")
            continue

        while len(paragraph) > chars_per_line:
            wrapped_lines.append(paragraph[:chars_per_line])
            paragraph = paragraph[chars_per_line:]
        wrapped_lines.append(paragraph)

    if len(wrapped_lines) <= max_lines:
        return wrapped_lines

    visible_lines = wrapped_lines[:max_lines]
    overflow = "".join(wrapped_lines[max_lines - 1:])
    visible_lines[-1] = overflow[:chars_per_line]
    return visible_lines


def _build_writing_block(
    text: str | Iterable[str] | None,
    *,
    max_rows: int,
    specs: Sequence[WritingSpec],
    override_font_size_pt: float | None = None,
) -> dict[str, object]:
    normalized = _normalize_text(text)
    compact_text = normalized.replace("\n", "").replace(" ", "")
    char_count = len(compact_text)

    chosen_spec: WritingSpec = specs[-1]
    for spec in specs:
        if char_count <= spec["max_chars"]:
            chosen_spec = spec
            break

    lines = _wrap_text(
        normalized,
        chars_per_line=chosen_spec["chars_per_line"],
        max_lines=chosen_spec["line_count"],
    )
    padded_lines = lines + [""] * max(0, max_rows - len(lines))

    return {
        "text": normalized,
        "font_size_pt": override_font_size_pt if override_font_size_pt is not None else chosen_spec["font_size_pt"],
        "line_count": len(lines),
        "lines": padded_lines[:max_rows],
        "layout_mode": chosen_spec["mode"],
    }


def _chunk_photos(items: Sequence[dict[str, object]]) -> list[list[dict[str, object]]]:
    pages: list[list[dict[str, object]]] = []
    current_page: list[dict[str, object]] = []

    for item in items:
        current_page.append(item)
        force_break = bool(item.pop("page_break_after", False))
        if len(current_page) >= PHOTO_PAGE_SIZE or force_break:
            pages.append(current_page)
            current_page = []

    if current_page:
        pages.append(current_page)

    return pages


def _normalize_photo_layout(value: Any) -> dict[str, Any]:
    layout = deepcopy(DEFAULT_PHOTO_LAYOUT)
    if value is None:
        return layout

    mapping = require_mapping("raw_report.photo_layout", value)
    labels = mapping.get("labels")
    if labels is None:
        return layout

    label_mapping = require_mapping("raw_report.photo_layout.labels", labels)
    layout["labels"].update(label_mapping)
    return layout


def _normalize_info_rows(value: Any) -> list[dict[str, Any]]:
    rows = require_list("raw_report.overview.info_rows", value)
    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        mapping = require_mapping(f"raw_report.overview.info_rows[{index}]", row)
        normalized_rows.append(
            {
                "number": mapping["number"],
                "label": mapping["label"],
                "value": mapping["value"],
                "extra_values": list(mapping.get("extra_values", [])),
            }
        )
    return normalized_rows


def _normalize_work_groups(value: Any) -> list[dict[str, Any]]:
    groups = require_list("raw_report.overview.work_groups", value)
    normalized_groups: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        mapping = require_mapping(f"raw_report.overview.work_groups[{index}]", group)
        normalized_groups.append(
            {
                "marker": mapping["marker"],
                "title": mapping["title"],
                "lines": list(require_list(f"raw_report.overview.work_groups[{index}].lines", mapping["lines"])),
            }
        )
    return normalized_groups


def _build_photo_entry(item: dict[str, Any]) -> dict[str, object]:
    work_content_specs: list[WritingSpec] = [
        {"max_chars": 12, "font_size_pt": 9.2, "line_count": 1, "chars_per_line": 12, "mode": "compact"},
        {"max_chars": 24, "font_size_pt": 8.6, "line_count": 2, "chars_per_line": 12, "mode": "standard"},
        {"max_chars": 36, "font_size_pt": 8.0, "line_count": 3, "chars_per_line": 12, "mode": "standard"},
        {"max_chars": 52, "font_size_pt": 7.5, "line_count": 4, "chars_per_line": 13, "mode": "dense"},
        {"max_chars": 70, "font_size_pt": 7.0, "line_count": 5, "chars_per_line": 14, "mode": "dense"},
        {"max_chars": 999, "font_size_pt": 6.6, "line_count": 6, "chars_per_line": 14, "mode": "dense"},
    ]
    remarks_specs: list[WritingSpec] = [
        {"max_chars": 10, "font_size_pt": 8.6, "line_count": 1, "chars_per_line": 10, "mode": "compact"},
        {"max_chars": 20, "font_size_pt": 7.9, "line_count": 2, "chars_per_line": 10, "mode": "standard"},
        {"max_chars": 30, "font_size_pt": 7.3, "line_count": 3, "chars_per_line": 10, "mode": "dense"},
        {"max_chars": 999, "font_size_pt": 6.8, "line_count": 4, "chars_per_line": 11, "mode": "dense"},
    ]

    override_font_size_pt = item.get("font_size_pt")
    font_size = float(override_font_size_pt) if isinstance(override_font_size_pt, int | float) else None

    photo_entry: dict[str, object] = {
        "no": item["no"],
        "site": item["site"],
        "work_date": item["work_date"],
        "location": item["location"],
        "photo_path": item["photo_path"],
        "work_content": _build_writing_block(
            item.get("work_content"),
            max_rows=WORK_CONTENT_ROWS,
            specs=work_content_specs,
            override_font_size_pt=font_size,
        ),
        "remarks": _build_writing_block(
            item.get("remarks"),
            max_rows=REMARKS_ROWS,
            specs=remarks_specs,
            override_font_size_pt=font_size,
        ),
    }
    if "page_break_after" in item:
        photo_entry["page_break_after"] = bool(item["page_break_after"])
    return photo_entry


def build_report_from_raw(raw_report: dict[str, Any]) -> dict[str, Any]:
    validate_raw_report_data(raw_report)

    cover = require_mapping("raw_report.cover", raw_report["cover"])
    overview_raw = require_mapping("raw_report.overview", raw_report["overview"])
    photos_raw = require_list("raw_report.photos", raw_report["photos"])

    blank_lines_value = overview_raw.get("blank_lines")
    if blank_lines_value is None:
        blank_line_count = overview_raw.get("blank_line_count", DEFAULT_BLANK_LINE_COUNT)
        blank_lines = ["　"] * int(blank_line_count)
    else:
        blank_lines = list(require_list("raw_report.overview.blank_lines", blank_lines_value))

    photos = [_build_photo_entry(require_mapping(f"raw_report.photos[{index}]", item)) for index, item in enumerate(photos_raw, start=1)]

    return {
        "title": raw_report["title"],
        "cover": {
            "recipient": cover["recipient"],
            "date": cover["date"],
            "title": cover["title"],
            "subtitle": cover["subtitle"],
            "detail_rows": list(require_list("raw_report.cover.detail_rows", cover["detail_rows"])),
            "company": {
                "name": cover["company"]["name"],
                "postal_code": cover["company"]["postal_code"],
                "address_lines": list(require_list("raw_report.cover.company.address_lines", cover["company"]["address_lines"])),
                "tel_label": cover["company"]["tel_label"],
                "tel": cover["company"]["tel"],
                "fax_label": cover["company"]["fax_label"],
                "fax": cover["company"]["fax"],
            },
        },
        "overview": {
            "recipient": overview_raw["recipient"],
            "title": overview_raw["title"],
            "company_lines": list(require_list("raw_report.overview.company_lines", overview_raw["company_lines"])),
            "info_rows": _normalize_info_rows(overview_raw["info_rows"]),
            "work_section_title": overview_raw.get("work_section_title", DEFAULT_WORK_SECTION_TITLE),
            "work_groups": _normalize_work_groups(overview_raw["work_groups"]),
            "blank_lines": blank_lines,
            "note_line": overview_raw.get("note_line", DEFAULT_NOTE_LINE),
            "ending": overview_raw.get("ending", DEFAULT_ENDING),
        },
        "photo_layout": _normalize_photo_layout(raw_report.get("photo_layout")),
        "photo_pages": _chunk_photos(photos),
    }
