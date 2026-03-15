"""photo 系 GUI が共有する軽量データモデル。

`PhotoItem` は arrange/description/import の各 page をまたいで同一インスタンスのまま
受け回される。したがってこの層では、値の内容だけでなく「どのインスタンスを編集しているか」
という identity が重要になる。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QImage


@dataclass(frozen=True)
class PhotoDescriptionDefaults:
    """写真説明欄へ注入する既定値セット。

    Cover page の現在値から都度組み立てられ、PhotoItem の未編集フィールドへだけ反映される。
    """

    site: str = ""
    work_date: str = ""
    location: str = ""


@dataclass
class PhotoItem:
    """圧縮済み画像データと説明欄編集状態を保持するデータクラス。

    arrange/description 間ではこのインスタンス自体を共有し、表示順や選択状態だけを別途管理する。
    `_default_description_values` と `_user_edited_description_fields` は、cover 由来の既定値更新が
    ユーザー編集内容を上書きしないようにするための内部状態である。
    """

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
        """取り込み直後の既定値を注入する。

        import 直後は user edit がまだ存在しないため、force=True で全対象フィールドを同期する。
        """
        self.sync_description_defaults(defaults, force=True)

    def sync_description_defaults(
        self,
        defaults: PhotoDescriptionDefaults,
        *,
        force: bool = False,
    ) -> None:
        """未編集項目にだけ既定値を反映し、最新の既定値スナップショットを保持する。

        `force=False` では、次のどちらかを満たす場合だけ値を書き換える。

        - まだユーザー編集済みとして印が付いていない
        - 現在値が空、または前回適用した既定値そのもの

        これにより、Cover page に戻って既定値が変わっても、利用者が説明欄で明示的に編集した値は
        保持される。
        """
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
            # 既定値の履歴は、次回同期時に「これは自動反映された値か」を判定する材料になる。
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