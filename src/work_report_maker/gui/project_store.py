"""GUI プロジェクトの保存・読込・削除を扱う永続化モジュール。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from work_report_maker.gui.pages.photo_import_page import PhotoItem

_APP_DIR = Path.home() / ".work_report_maker"
_PROJECTS_DIR = _APP_DIR / "projects"
_PROJECT_FILE_NAME = "project.json"
_PHOTOS_DIR_NAME = "photos"
_PROJECT_VERSION = 1


class ProjectStoreError(Exception):
    """プロジェクト永続化に失敗したことを表す例外。"""


class ProjectNotFoundError(ProjectStoreError):
    """指定したプロジェクトが存在しない。"""


@dataclass(frozen=True)
class ProjectSummary:
    name: str
    saved_at: str


def list_projects() -> list[ProjectSummary]:
    """保存済みプロジェクト一覧を返す。"""

    if not _PROJECTS_DIR.exists():
        return []

    summaries: list[ProjectSummary] = []
    for project_dir in _PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        project_file = project_dir / _PROJECT_FILE_NAME
        if not project_file.exists():
            continue
        try:
            data = json.loads(project_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("project_name")
        saved_at = data.get("saved_at", "")
        if isinstance(name, str) and name.strip():
            summaries.append(ProjectSummary(name=name, saved_at=saved_at if isinstance(saved_at, str) else ""))

    summaries.sort(key=lambda summary: (summary.saved_at, summary.name.casefold()), reverse=True)
    return summaries


def list_project_names() -> list[str]:
    return [summary.name for summary in list_projects()]


def project_exists(project_name: str) -> bool:
    return (_project_dir(project_name) / _PROJECT_FILE_NAME).exists()


def save_project(
    *,
    project_name: str,
    cover_state: dict,
    overview_state: dict,
    work_content_state: dict,
    photo_import_settings: dict,
    photo_items: list[PhotoItem],
) -> Path:
    """現在のウィザード状態をプロジェクトとして保存する。"""

    normalized_name = _normalize_project_name(project_name)
    project_dir = _project_dir(normalized_name)
    photos_dir = project_dir / _PHOTOS_DIR_NAME
    project_dir.mkdir(parents=True, exist_ok=True)
    photos_dir.mkdir(parents=True, exist_ok=True)

    photo_entries, expected_files = _write_photo_files(photos_dir, photo_items)
    _remove_deleted_photo_files(photos_dir, expected_files)

    payload = {
        "project_version": _PROJECT_VERSION,
        "project_name": normalized_name,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "cover_state": cover_state,
        "overview_state": overview_state,
        "work_content_state": work_content_state,
        "photo_import_settings": photo_import_settings,
        "photos": photo_entries,
    }
    project_file = project_dir / _PROJECT_FILE_NAME
    project_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return project_dir


def load_project(project_name: str) -> dict:
    """保存済みプロジェクトを読み込み、GUI 復元用 state を返す。"""

    normalized_name = _normalize_project_name(project_name)
    project_dir = _project_dir(normalized_name)
    project_file = project_dir / _PROJECT_FILE_NAME
    if not project_file.exists():
        raise ProjectNotFoundError(f"Project not found: {normalized_name}")

    try:
        payload = json.loads(project_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectStoreError(f"プロジェクトを読み込めませんでした: {normalized_name}") from exc

    photos_dir = project_dir / _PHOTOS_DIR_NAME
    photo_items = [_deserialize_photo_item(photos_dir, photo_state) for photo_state in payload.get("photos", [])]
    return {
        "project_name": payload.get("project_name", normalized_name),
        "cover_state": payload.get("cover_state", {}),
        "overview_state": payload.get("overview_state", {}),
        "work_content_state": payload.get("work_content_state", {}),
        "photo_import_settings": payload.get("photo_import_settings", {}),
        "photo_items": photo_items,
    }


def delete_project(project_name: str) -> None:
    """保存済みプロジェクトを削除する。"""

    project_dir = _project_dir(project_name)
    if not project_dir.exists():
        raise ProjectNotFoundError(f"Project not found: {project_name}")

    for child in sorted(project_dir.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    project_dir.rmdir()


def _normalize_project_name(project_name: str) -> str:
    normalized = project_name.strip()
    if not normalized:
        raise ProjectStoreError("プロジェクト名が空です。")
    return normalized


def _project_dir(project_name: str) -> Path:
    normalized_name = _normalize_project_name(project_name)
    digest = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:10]
    safe_name = _sanitize_name_for_path(normalized_name)
    return _PROJECTS_DIR / f"{safe_name}-{digest}"


def _sanitize_name_for_path(project_name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    translated = "".join("_" if char in invalid_chars or ord(char) < 32 else char for char in project_name)
    translated = translated.strip().rstrip(". ")
    return translated or "project"


def _write_photo_files(photos_dir: Path, photo_items: list[PhotoItem]) -> tuple[list[dict], set[str]]:
    entries: list[dict] = []
    expected_files: set[str] = set()
    for photo in photo_items:
        extension = _photo_extension(photo)
        digest = hashlib.sha1(photo.data).hexdigest()
        stored_filename = f"{digest}.{extension}"
        photo_path = photos_dir / stored_filename
        photo_path.write_bytes(photo.data)
        expected_files.add(stored_filename)
        entries.append(
            {
                "filename": photo.filename,
                "stored_filename": stored_filename,
                "format": photo.format,
                "site": photo.site,
                "work_date": photo.work_date,
                "location": photo.location,
                "work_content": photo.work_content,
                "remarks": photo.remarks,
                "default_description_values": dict(photo._default_description_values),
                "user_edited_description_fields": sorted(photo._user_edited_description_fields),
            }
        )
    return entries, expected_files


def _remove_deleted_photo_files(photos_dir: Path, expected_files: set[str]) -> None:
    for child in photos_dir.iterdir():
        if not child.is_file():
            continue
        if child.name not in expected_files:
            child.unlink()


def _deserialize_photo_item(photos_dir: Path, photo_state: dict) -> PhotoItem:
    stored_filename = photo_state.get("stored_filename")
    if not isinstance(stored_filename, str) or not stored_filename:
        raise ProjectStoreError("保存済み写真の情報が不正です。")
    photo_path = photos_dir / stored_filename
    if not photo_path.exists():
        raise ProjectStoreError(f"保存済み写真が見つかりません: {stored_filename}")

    data = photo_path.read_bytes()
    image = QImage()
    image.loadFromData(data)
    thumbnail = None
    if not image.isNull():
        thumbnail = image.scaled(
            128,
            128,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    item = PhotoItem(
        filename=photo_state.get("filename", stored_filename),
        data=data,
        format=photo_state.get("format", photo_path.suffix.lstrip(".")),
        thumbnail=thumbnail,
        site=photo_state.get("site", ""),
        work_date=photo_state.get("work_date", ""),
        location=photo_state.get("location", ""),
        work_content=photo_state.get("work_content", ""),
        remarks=photo_state.get("remarks", ""),
    )
    default_values = photo_state.get("default_description_values", {})
    if isinstance(default_values, dict):
        item._default_description_values = {
            str(key): str(value) for key, value in default_values.items()
        }
    user_edited = photo_state.get("user_edited_description_fields", [])
    if isinstance(user_edited, list):
        item._user_edited_description_fields = {str(field_name) for field_name in user_edited}
    return item


def _photo_extension(photo: PhotoItem) -> str:
    normalized = photo.format.lower().strip().lstrip(".")
    if normalized in {"jpg", "jpeg"}:
        return "jpg"
    if normalized == "png":
        return "png"
    return normalized or "bin"