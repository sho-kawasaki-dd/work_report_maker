"""プリセット永続化モジュール。

建物プリセットと会社情報を ~/.work_report_maker/ 以下の JSON ファイルに
保存・読込する機能を提供する。

保存先:
    ~/.work_report_maker/building_presets.json  — 建物プリセット (複数保存可)
    ~/.work_report_maker/company_info.json      — 会社情報 (1件のみ)

建物プリセットのデータ構造:
    {
        "建物名A": { "recipient": "提出先名", "address": "住所" },
        "建物名B": { ... },
        ...
    }
    - building_name (辞書キー) が一意識別子
    - recipient は「御中」を含まない純粋な提出先名

会社情報のデータ構造:
    {
        "name": "社名",
        "postal_code": "〒000-0000",
        "address_lines": ["住所行1", "住所行2"],
        "tel": "000-000-0000",
        "fax": "000-000-0000"
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# プリセット保存ディレクトリ（ユーザーホーム直下）
_PRESET_DIR = Path.home() / ".work_report_maker"
# 建物プリセットファイルパス
_BUILDING_FILE = _PRESET_DIR / "building_presets.json"
# 会社情報ファイルパス
_COMPANY_FILE = _PRESET_DIR / "company_info.json"


def _ensure_dir() -> None:
    """保存ディレクトリが存在しなければ作成する。"""
    _PRESET_DIR.mkdir(parents=True, exist_ok=True)


# ── 建物プリセット ────────────────────────────────────────────


def load_building_presets() -> dict[str, dict[str, str]]:
    """建物プリセットを JSON ファイルから読み込んで返す。

    Returns:
        {建物名: {"recipient": 提出先名, "address": 住所}, ...}
        ファイルが未作成、または不正な形式の場合は空の dict を返す。
    """
    if not _BUILDING_FILE.exists():
        return {}
    data = json.loads(_BUILDING_FILE.read_text("utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def save_building_presets(presets: dict[str, dict[str, str]]) -> None:
    """建物プリセット全体を JSON ファイルに上書き保存する。"""
    _ensure_dir()
    _BUILDING_FILE.write_text(
        json.dumps(presets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_building_preset(
    building_name: str, recipient: str, address: str
) -> None:
    """建物プリセットを1件追加（または同名を上書き）する。

    Args:
        building_name: 建物名（一意キー）
        recipient: 提出先名（「御中」を含まない）
        address: 住所
    """
    presets = load_building_presets()
    presets[building_name] = {"recipient": recipient, "address": address}
    save_building_presets(presets)


def delete_building_preset(building_name: str) -> None:
    """指定した建物名のプリセットを削除する。存在しなければ何もしない。"""
    presets = load_building_presets()
    presets.pop(building_name, None)
    save_building_presets(presets)


# ── 会社情報 ──────────────────────────────────────────────────

# 未保存時に返すデフォルト値
_DEFAULT_COMPANY: dict[str, Any] = {
    "name": "",
    "postal_code": "",
    "address_lines": [""],
    "tel": "",
    "fax": "",
}


def load_company_info() -> dict[str, Any]:
    """会社情報を JSON ファイルから読み込んで返す。

    ファイルが未作成、または不正な形式の場合はデフォルト（空）の会社情報を返す。
    """
    if not _COMPANY_FILE.exists():
        return dict(_DEFAULT_COMPANY)
    data = json.loads(_COMPANY_FILE.read_text("utf-8"))
    if not isinstance(data, dict):
        return dict(_DEFAULT_COMPANY)
    return data


def save_company_info(info: dict[str, Any]) -> None:
    """会社情報を JSON ファイルに上書き保存する。"""
    _ensure_dir()
    _COMPANY_FILE.write_text(
        json.dumps(info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
