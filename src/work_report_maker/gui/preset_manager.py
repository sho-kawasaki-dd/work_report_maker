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

from work_report_maker.config import PROJECT_ROOT

# プリセット保存ディレクトリ（ユーザーホーム直下）
_PRESET_DIR = Path.home() / ".work_report_maker"
# 建物プリセットファイルパス
_BUILDING_FILE = _PRESET_DIR / "building_presets.json"
# 会社情報ファイルパス
_COMPANY_FILE = _PRESET_DIR / "company_info.json"
# PDF 出力設定ファイルパス
_PDF_OUTPUT_FILE = _PRESET_DIR / "pdf_output_settings.json"


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
    # GUI での利便性を優先し、破損ファイルは例外で止めず「プリセット無し」として扱う。
    if not _BUILDING_FILE.exists():
        return {}
    data = json.loads(_BUILDING_FILE.read_text("utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def save_building_presets(presets: dict[str, dict[str, str]]) -> None:
    """建物プリセット全体を JSON ファイルに上書き保存する。

    差分更新ではなく全体書き戻しにしているのは、件数が少なく schema も単純であり、部分更新より
    実装の見通しを優先できるためである。
    """
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
    # building_name を辞書キーにすることで、一覧表示と上書き判定を単純化している。
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
    # 表紙出力では company 情報が必須キー前提で組み立てられるため、未保存時でも
    # 空値入りの完全な dict を返して caller 側の分岐を減らす。
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


# ── PDF 出力設定 ─────────────────────────────────────────────


def _resolve_desktop_dir() -> Path:
    """既定保存先として使う Desktop を返し、なければプロジェクトルートへ落とす。"""

    # GUI 初回起動時でも確実に保存先を返したいため、OS 依存 API ではなく存在確認だけで決める。
    desktop_dir = Path.home() / "Desktop"
    if desktop_dir.exists() and desktop_dir.is_dir():
        return desktop_dir
    return PROJECT_ROOT


def load_default_output_dir() -> Path:
    """既定の PDF 保存先ディレクトリを返す。

    保存済み JSON が壊れている場合や、以前の保存先が削除済みだった場合でも、呼び出し側へ
    例外を漏らさず fallback を返して GUI の起動を優先する。
    """

    fallback_dir = _resolve_desktop_dir()
    if not _PDF_OUTPUT_FILE.exists():
        return fallback_dir

    data = json.loads(_PDF_OUTPUT_FILE.read_text("utf-8"))
    if not isinstance(data, dict):
        return fallback_dir

    saved_dir = data.get("default_output_dir", "")
    if not isinstance(saved_dir, str) or not saved_dir.strip():
        return fallback_dir

    candidate = Path(saved_dir).expanduser()
    if candidate.exists() and candidate.is_dir():
        return candidate.resolve()
    return fallback_dir


def save_default_output_dir(directory: str | Path) -> Path:
    """既定の PDF 保存先ディレクトリを保存する。

    保存前に実在ディレクトリへ正規化しておくことで、以後の GUI 初期表示や保存ダイアログが
    常に絶対パスを前提に動けるようにする。
    """

    resolved_dir = Path(directory).expanduser().resolve()
    if not resolved_dir.exists() or not resolved_dir.is_dir():
        raise ValueError(f"Output directory does not exist: {resolved_dir}")

    _ensure_dir()
    _PDF_OUTPUT_FILE.write_text(
        json.dumps({"default_output_dir": str(resolved_dir)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return resolved_dir
