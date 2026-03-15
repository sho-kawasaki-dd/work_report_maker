from __future__ import annotations

import re

from PySide6.QtCore import QDate


_WORK_DATE_PATTERN = re.compile(r"^(?P<year>\d{4})年\s*(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日(?:\([^)]*\))?$")
_WEEKDAY_MAP: dict[int, str] = {
    1: "月",
    2: "火",
    3: "水",
    4: "木",
    5: "金",
    6: "土",
    7: "日",
}


def parse_work_date(value: str) -> QDate | None:
    match = _WORK_DATE_PATTERN.match(value.strip())
    if match is None:
        return None
    date = QDate(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
    )
    return date if date.isValid() else None


def format_work_date(date: QDate) -> str:
    weekday = _WEEKDAY_MAP.get(date.dayOfWeek(), "")
    return f"{date.year()}年 {date.month()}月 {date.day():02d}日({weekday})"