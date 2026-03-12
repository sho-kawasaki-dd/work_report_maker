from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence, TypedDict

from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path(__file__).resolve().parent
DEPENDENCIES_DIR = PROJECT_ROOT / "dependencies"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OUTPUT_PDF = PROJECT_ROOT / "full_report.pdf"
_DLL_DIRECTORIES: list[object] = []
PHOTO_PAGE_SIZE = 3
WORK_CONTENT_ROWS = 6
REMARKS_ROWS = 4


class WritingSpec(TypedDict):
    max_chars: int
    font_size_pt: float
    line_count: int
    chars_per_line: int
    mode: str


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


def _chunked(items: Sequence[dict[str, object]], size: int) -> list[list[dict[str, object]]]:
    return [list(items[index:index + size]) for index in range(0, len(items), size)]


def _resolve_photo_uri(photo_path: str | None) -> str | None:
    if not photo_path:
        return None

    resolved_path = Path(photo_path)
    if not resolved_path.is_absolute():
        resolved_path = PROJECT_ROOT / resolved_path
    if not resolved_path.exists():
        return None
    return resolved_path.resolve().as_uri()


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
        "font_size_pt": chosen_spec["font_size_pt"],
        "line_count": len(lines),
        "lines": padded_lines[:max_rows],
        "layout_mode": chosen_spec["mode"],
    }


def _build_photo_entry(item: dict[str, object]) -> dict[str, object]:
    photo_path = item.get("photo_path")
    work_content = item.get("work_content")
    remarks = item.get("remarks")

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

    return {
        "no": item["no"],
        "site": item["site"],
        "work_date": item["work_date"],
        "location": item["location"],
        "photo_path": _resolve_photo_uri(photo_path if isinstance(photo_path, str) else None),
        "work_content": _build_writing_block(
            work_content if isinstance(work_content, str | list | tuple) else None,
            max_rows=WORK_CONTENT_ROWS,
            specs=work_content_specs,
        ),
        "remarks": _build_writing_block(
            remarks if isinstance(remarks, str | list | tuple) else None,
            max_rows=REMARKS_ROWS,
            specs=remarks_specs,
        ),
    }


def build_report_context() -> dict[str, object]:
    company = {
        "name": "株式会社京都ダイケンビルサービス",
        "postal_code": "〒600-8413",
        "address_lines": [
            "京都市下京区烏丸通仏光寺下ル大政所町680-1（第八長谷ビル）",
        ],
        "tel_label": "TEL：",
        "tel": "075-342-2611",
        "fax_label": "FAX：",
        "fax": "075-342-2660",
    }

    overview_company_lines = [
        "京都市下京区烏丸通仏光寺下ル大政所町680-1",
        "株式会社京都ダイケンビルサービス",
        "TEL  (075)  342－2611",
        "FAX  (075)  342－2660",
    ]

    sample_images = [
        "IMG_20260218_215726354.jpg",
        "IMG_20260218_215726354.jpg",
        "IMG_20260218_215726354.jpg",
    ]
    raw_photos = [
        {
            "no": 1,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "清掃箇所遠景",
            "remarks": "作業前",
            "photo_path": sample_images[0],
        },
        {
            "no": 2,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "グリストラップ本槽の内部状況確認",
            "remarks": "作業前",
            "photo_path": sample_images[1],
        },
        {
            "no": 3,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "堆積油脂・汚泥回収後の高圧洗浄状況",
            "remarks": "洗浄中の状況を記録",
            "photo_path": sample_images[2],
        },
        {
            "no": 4,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "バスケット、仕切板、トラップ蓋の取り外し清掃",
            "remarks": "部材を個別洗浄",
            "photo_path": sample_images[0],
        },
        {
            "no": 5,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "槽内壁面と配管入口周辺の油脂分を除去し、異臭発生源を重点洗浄",
            "remarks": "薬剤使用なし",
            "photo_path": sample_images[1],
        },
        {
            "no": 6,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "清掃完了後の水張り確認および復旧後の全景",
            "remarks": "作業後",
            "photo_path": sample_images[2],
        },
        {
            "no": 7,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "グリストラップ周辺床面の洗浄と飛散汚れの拭き上げ完了確認",
            "remarks": "周辺養生撤去後",
            "photo_path": sample_images[0],
        },
        {
            "no": 8,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "取り外し部材を復旧し、排水の流下状況と異常音の有無を確認",
            "remarks": "排水確認済",
            "photo_path": sample_images[1],
        },
        {
            "no": 9,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "槽内最終確認",
            "remarks": "清掃後",
            "photo_path": sample_images[2],
        },
        {
            "no": 10,
            "site": "LH京都三条",
            "work_date": "2025年3月27日",
            "location": "1階厨房",
            "work_content": "作業完了報告用の引き渡し時点写真。設備外観、周辺床面、付帯部材の復旧状態が判別できるよう広めの構図で撮影",
            "remarks": "最終引渡し前確認",
            "photo_path": sample_images[0],
        },
    ]
    photos = [_build_photo_entry(item) for item in raw_photos]

    return {
        "title": "厨房グリストラップ清掃完了報告書",
        "cover": {
            "recipient": "ロワジールホテルクラシックガーデン 京都三条　御中",
            "date": "2025年 3月 29日",
            "title": "厨房グリストラップ清掃完了報告書",
            "subtitle": "ホテル1階厨房",
            "detail_rows": [
                {"label": "建物名", "value": "ロワジールホテル クラシックガーデン 京都三条"},
                {"label": "住　所", "value": "京都市中京区三条烏丸西入る御倉町80番地"},
                {"label": "日　時", "value": "2025年 3月 27日(木)"},
            ],
            "company": company,
        },
        "overview": {
            "recipient": "ロワジールホテル クラシックガーデン 京都三条　御中",
            "title": "工 事 完 了 報 告 書",
            "company_lines": overview_company_lines,
            "info_rows": [
                {"number": "1", "label": "施工対象・名称", "value": "ロワジールホテル クラシックガーデン 京都三条", "extra_values": []},
                {"number": "2", "label": "施工場所", "value": "ホテル1階厨房", "extra_values": []},
                {"number": "3", "label": "施工内容", "value": "厨房グリストラップ清掃", "extra_values": []},
                {"number": "4", "label": "施工日時", "value": "2025年 3月 27日(木)", "extra_values": []},
                {
                    "number": "5",
                    "label": "施工担当",
                    "value": "現場責任者　川崎　潤",
                    "extra_values": ["現場作業者　他 2 名"],
                },
            ],
            "work_section_title": "作業内容",
            "work_groups": [
                {
                    "marker": "◎",
                    "title": "厨房グリストラップ清掃",
                    "lines": [
                        "1）作業内容",
                        "① 厨房グリストラップ清掃",
                        "グリストラップ内部の高圧洗浄及び汚泥・バキューム処理。",
                    ],
                }
            ],
            "blank_lines": ["　"] * 12,
            "note_line": "※ 仕上り品質報告書 『別紙写真参照』",
            "ending": "以上",
        },
        "photo_layout": {
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
        },
        "photo_pages": _chunked(photos, PHOTO_PAGE_SIZE),
    }


def generate_full_report() -> None:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("report_tmp.html")

    html_content = template.render(report=build_report_context())

    HTML(string=html_content, base_url=str(TEMPLATES_DIR.resolve())).write_pdf(OUTPUT_PDF)


if __name__ == "__main__":
    generate_full_report()