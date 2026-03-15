"""raw report / render-ready report の構造検証を行う。"""

from __future__ import annotations

from typing import Any


def require_mapping(name: str, value: Any) -> dict[str, Any]:
    """値が JSON object 相当であることを検証する。"""

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a JSON object.")
    return value


def require_list(name: str, value: Any) -> list[Any]:
    """値が JSON array 相当であることを検証する。"""

    if not isinstance(value, list):
        raise TypeError(f"{name} must be a JSON array.")
    return value


def validate_report_data(report_data: dict[str, Any]) -> None:
    """render-ready report の最低限の構造を検証する。

    ここで保証するのはキーの存在と object/array の形だけであり、業務上の妥当性や文字数制限までは
    判定しない。そうした意味づけは adapter や template 側の責務とする。
    """

    required_top_level_keys = ["title", "cover", "overview", "photo_layout", "photo_pages"]
    missing_keys = [key for key in required_top_level_keys if key not in report_data]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise KeyError(f"report JSON is missing required top-level keys: {missing}")

    cover = require_mapping("report.cover", report_data["cover"])
    cover_company = require_mapping("report.cover.company", cover.get("company"))
    require_list("report.cover.detail_rows", cover.get("detail_rows"))
    require_list("report.cover.company.address_lines", cover_company.get("address_lines"))

    overview = require_mapping("report.overview", report_data["overview"])
    require_list("report.overview.company_lines", overview.get("company_lines"))
    info_rows = require_list("report.overview.info_rows", overview.get("info_rows"))
    work_groups = require_list("report.overview.work_groups", overview.get("work_groups"))
    require_list("report.overview.blank_lines", overview.get("blank_lines"))

    for index, row in enumerate(info_rows, start=1):
        mapping = require_mapping(f"report.overview.info_rows[{index}]", row)
        require_list(f"report.overview.info_rows[{index}].extra_values", mapping.get("extra_values"))

    for index, group in enumerate(work_groups, start=1):
        mapping = require_mapping(f"report.overview.work_groups[{index}]", group)
        require_list(f"report.overview.work_groups[{index}].lines", mapping.get("lines"))

    photo_layout = require_mapping("report.photo_layout", report_data["photo_layout"])
    labels = require_mapping("report.photo_layout.labels", photo_layout.get("labels"))
    require_list("report.photo_layout.labels.work_content_stacked", labels.get("work_content_stacked"))
    require_list("report.photo_layout.labels.remarks_stacked", labels.get("remarks_stacked"))

    photo_pages = require_list("report.photo_pages", report_data["photo_pages"])
    for page_index, page in enumerate(photo_pages, start=1):
        page_items = require_list(f"report.photo_pages[{page_index}]", page)
        for item_index, item in enumerate(page_items, start=1):
            mapping = require_mapping(f"report.photo_pages[{page_index}][{item_index}]", item)
            require_mapping(
                f"report.photo_pages[{page_index}][{item_index}].work_content",
                mapping.get("work_content"),
            )
            require_mapping(
                f"report.photo_pages[{page_index}][{item_index}].remarks",
                mapping.get("remarks"),
            )


def validate_raw_report_data(raw_report: dict[str, Any]) -> None:
    """raw report の最低限の構造を検証する。"""

    required_top_level_keys = ["title", "cover", "overview", "photos"]
    missing_keys = [key for key in required_top_level_keys if key not in raw_report]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise KeyError(f"raw report JSON is missing required top-level keys: {missing}")

    cover = require_mapping("raw_report.cover", raw_report["cover"])
    company = require_mapping("raw_report.cover.company", cover.get("company"))
    require_list("raw_report.cover.detail_rows", cover.get("detail_rows"))
    require_list("raw_report.cover.company.address_lines", company.get("address_lines"))

    overview = require_mapping("raw_report.overview", raw_report["overview"])
    require_list("raw_report.overview.company_lines", overview.get("company_lines"))

    info_rows = require_list("raw_report.overview.info_rows", overview.get("info_rows"))
    for index, row in enumerate(info_rows, start=1):
        mapping = require_mapping(f"raw_report.overview.info_rows[{index}]", row)
        require_list(f"raw_report.overview.info_rows[{index}].extra_values", mapping.get("extra_values", []))

    work_groups = require_list("raw_report.overview.work_groups", overview.get("work_groups"))
    for index, group in enumerate(work_groups, start=1):
        mapping = require_mapping(f"raw_report.overview.work_groups[{index}]", group)
        require_list(f"raw_report.overview.work_groups[{index}].lines", mapping.get("lines"))

    photos = require_list("raw_report.photos", raw_report["photos"])
    required_photo_keys = ["no", "site", "work_date", "location", "photo_path", "work_content", "remarks"]
    for index, photo in enumerate(photos, start=1):
        mapping = require_mapping(f"raw_report.photos[{index}]", photo)
        missing_photo_keys = [key for key in required_photo_keys if key not in mapping]
        if missing_photo_keys:
            missing = ", ".join(missing_photo_keys)
            raise KeyError(f"raw_report.photos[{index}] is missing required keys: {missing}")
