from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QImage


@dataclass(frozen=True)
class PhotoDescriptionDefaults:
    """写真説明欄へ注入する既定値セット。"""

    site: str = ""
    work_date: str = ""
    location: str = ""


@dataclass
class PhotoItem:
    """圧縮済み画像データを保持するデータクラス。"""

    filename: str
    data: bytes
    format: str
    thumbnail: QImage | None = None
    site: str = ""
    work_date: str = ""
    location: str = ""
    work_content: str = ""
    remarks: str = ""
    _default_description_values: dict[str, str] = field(default_factory=dict, repr=False)
    _user_edited_description_fields: set[str] = field(default_factory=set, repr=False)

    def apply_initial_description_defaults(self, defaults: PhotoDescriptionDefaults) -> None:
        """取り込み直後の既定値を注入する。"""
        self.sync_description_defaults(defaults, force=True)

    def sync_description_defaults(
        self,
        defaults: PhotoDescriptionDefaults,
        *,
        force: bool = False,
    ) -> None:
        """未編集項目にだけ既定値を反映し、最新の既定値スナップショットを保持する。"""
        for field_name, value in {
            "site": defaults.site,
            "work_date": defaults.work_date,
            "location": defaults.location,
        }.items():
            current_value = getattr(self, field_name)
            previous_default = self._default_description_values.get(field_name, "")
            should_update = force or (
                field_name not in self._user_edited_description_fields
                and (current_value == "" or current_value == previous_default)
            )
            if should_update:
                setattr(self, field_name, value)
            self._default_description_values[field_name] = value

    def set_description_field(self, field_name: str, value: str) -> None:
        """説明項目を更新し、ユーザー編集済みとして扱う。"""
        if field_name not in {"site", "work_date", "location", "work_content", "remarks"}:
            raise ValueError(f"Unsupported description field: {field_name}")
        setattr(self, field_name, value)
        self._user_edited_description_fields.add(field_name)

    def is_description_field_user_edited(self, field_name: str) -> bool:
        """指定した説明項目がユーザー編集済みかどうかを返す。"""
        return field_name in self._user_edited_description_fields