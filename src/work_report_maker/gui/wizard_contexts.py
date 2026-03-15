"""GUI ウィザード内で共有する値オブジェクトと context 解決ヘルパー。

このモジュールの役割は 2 つある。

1. Cover/Overview/WorkContent 間で受け渡す「表示既定値」や「出力補助値」を、
    page 実装から独立した value object として表現すること。
2. photo 系 page が wizard 本体に直接依存しすぎないよう、読み取りと更新の入口を
    PhotoWizardContext 系 protocol に集約すること。

`resolve_photo_wizard_context()` は本番の ReportWizard だけでなく、GUI テストで使う
軽量な QWizard stub も受け付ける。したがってこの層では、ページ本体に fallback 分岐を
散らさずに済むことを優先し、やや防御的に属性を解決している。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from work_report_maker.gui.pages.photo_import_page import PhotoItem

_OVERVIEW_TITLE = "工 事 完 了 報 告 書"
_WORK_SECTION_TITLE = "作業内容"
_NOTE_LINE = "※ 仕上り品質報告書 『別紙写真参照』"
_ENDING = "以上"
_BLANK_LINE_COUNT = 12


@dataclass(frozen=True)
class PhotoImportSettings:
    """PhotoImportPage から読み出す圧縮設定のスナップショット。"""

    dpi: int
    jpeg_quality: int
    png_quality_max: int


@dataclass(frozen=True)
class CoverDisplayInfo:
    """Cover page を他ページへ反映するための表示用 DTO。

    Cover page 側では個別 field を保持しているが、Overview/WorkContent/Photo defaults
    側が必要とするのは「表示済みの意味づけを持つ値」の集合であるため、ここで一段
    抽象化して渡す。
    """

    building_name: str
    subtitle: str
    title_text: str
    work_date_text: str
    recipient_text: str

    @property
    def photo_site(self) -> str:
        """写真説明欄でいう「現場」に相当する値を返す。"""
        return self.building_name

    @property
    def photo_location(self) -> str:
        """写真説明欄でいう「施工箇所」に相当する値を返す。"""
        return self.subtitle


@dataclass(frozen=True)
class OverviewDefaults:
    """Overview page の表示既定値と raw payload 組み立て規約をまとめた値オブジェクト。

    GUI 表示更新と最終 payload 組み立てで同じ値群を共有するため、ページ側が cover 情報を
    再解釈し直さなくて済むようにしている。
    """

    recipient: str
    target: str
    location: str
    content: str
    work_date_text: str
    company_lines: list[str]
    title: str = _OVERVIEW_TITLE
    work_section_title: str = _WORK_SECTION_TITLE
    blank_line_count: int = _BLANK_LINE_COUNT
    note_line: str = _NOTE_LINE
    ending: str = _ENDING

    def build_info_rows(self, *, manager: str, workers: str) -> list[dict]:
        """Overview の定型 5 行を現時点の入力値から組み立てる。"""

        # 施工担当だけは Overview page 固有の入力欄を参照し、残り 4 行は Cover 由来の
        # 既定値をそのまま使う。
        staff_value = f"現場責任者　{manager}" if manager else ""
        staff_extra = [f"現場作業者　{workers}"] if workers else []
        return [
            {"number": "1", "label": "施工対象・名称", "value": self.target, "extra_values": []},
            {"number": "2", "label": "施工場所", "value": self.location, "extra_values": []},
            {"number": "3", "label": "施工内容", "value": self.content, "extra_values": []},
            {"number": "4", "label": "施工日時", "value": self.work_date_text, "extra_values": []},
            {"number": "5", "label": "施工担当", "value": staff_value, "extra_values": staff_extra},
        ]

    def build_payload(self, *, work_groups: list[dict], manager: str, workers: str) -> dict:
        """raw_report.overview 互換の辞書を返す。"""

        return {
            "recipient": self.recipient,
            "title": self.title,
            "company_lines": list(self.company_lines),
            "info_rows": self.build_info_rows(manager=manager, workers=workers),
            "work_section_title": self.work_section_title,
            "work_groups": work_groups,
            "blank_line_count": self.blank_line_count,
            "note_line": self.note_line,
            "ending": self.ending,
        }


@dataclass(frozen=True)
class WorkContentDefaults:
    """WorkContent page が cover から受け取る初期表示値。"""

    first_group_title: str


class PhotoWizardReadContext(Protocol):
    """photo 系 page が必要とする読み取り専用 API。"""

    def imported_photo_items(self) -> list[PhotoItem]: ...
    def arranged_photo_items(self) -> list[PhotoItem]: ...
    def photo_import_settings(self) -> PhotoImportSettings: ...


class PhotoWizardCommandContext(Protocol):
    """photo 系 page が必要とする更新操作 API。"""

    def add_imported_photo_items(self, items: list[PhotoItem]) -> None: ...
    def remove_imported_photo_items(self, items: list[PhotoItem]) -> None: ...
    def sync_imported_photo_defaults(self) -> None: ...
    def move_arranged_photo_left(self, photo: PhotoItem) -> int | None: ...
    def move_arranged_photo_right(self, photo: PhotoItem) -> int | None: ...


class PhotoWizardContext(PhotoWizardReadContext, PhotoWizardCommandContext, Protocol):
    """photo 系 page が依存する最小限の統合 context。"""

    pass


class WizardPhotoContext:
    """ReportWizard と軽量 wizard stub の両方を吸収する既定の context 実装。

    GUI テストでは full ReportWizard を組み立てず private page 属性だけ差し込むことがある。
    そのため、この実装は protocol を満たす最小限の adapter として振る舞う。
    """

    def __init__(self, *, photo_import_page=None, photo_arrange_page=None) -> None:
        self._photo_import_page = photo_import_page
        self._photo_arrange_page = photo_arrange_page

    def imported_photo_items(self) -> list[PhotoItem]:
        """Import page 側が保持する写真実体を安全に list 化して返す。"""
        if self._photo_import_page is None:
            return []
        return list(getattr(self._photo_import_page, "photo_items", []))

    def arranged_photo_items(self) -> list[PhotoItem]:
        """Arrange page の現在順を返す。ページ未接続時は空を返す。"""
        if self._photo_arrange_page is None:
            return []
        collector = getattr(self._photo_arrange_page, "collect_photo_items", None)
        if callable(collector):
            return cast(list[PhotoItem], collector())
        return []

    def photo_import_settings(self) -> PhotoImportSettings:
        """Import page の現在 UI 設定を値オブジェクト化して返す。"""
        if self._photo_import_page is None:
            raise AttributeError("Photo import page is not available")
        return PhotoImportSettings(
            dpi=self._photo_import_page.dpi(),
            jpeg_quality=self._photo_import_page.jpeg_quality(),
            png_quality_max=self._photo_import_page.png_quality_max(),
        )

    def add_imported_photo_items(self, items: list[PhotoItem]) -> None:
        if self._photo_import_page is not None:
            self._photo_import_page.add_photo_items(items)

    def remove_imported_photo_items(self, items: list[PhotoItem]) -> None:
        if self._photo_import_page is not None:
            self._photo_import_page.remove_photo_items(items)

    def sync_imported_photo_defaults(self) -> None:
        if self._photo_import_page is not None:
            self._photo_import_page.sync_photo_item_defaults()

    def move_arranged_photo_left(self, photo: PhotoItem) -> int | None:
        if self._photo_arrange_page is None:
            return None
        mover = getattr(self._photo_arrange_page, "move_photo_item_left", None)
        if callable(mover):
            return cast(int | None, mover(photo))
        return None

    def move_arranged_photo_right(self, photo: PhotoItem) -> int | None:
        if self._photo_arrange_page is None:
            return None
        mover = getattr(self._photo_arrange_page, "move_photo_item_right", None)
        if callable(mover):
            return cast(int | None, mover(photo))
        return None


def resolve_photo_wizard_context(wizard: object) -> PhotoWizardContext:
    """wizard から photo context を解決する単一入口。

    解決順は以下の通り。

    1. `photo_context()` メソッド
    2. `_photo_context` 属性
    3. `_photo_import_page` / `_photo_arrange_page` から組み立てる fallback context

    これにより、ページ本体は wizard の具体型やテスト fixture の作り方を知らずに済む。
    """

    context_getter = getattr(wizard, "photo_context", None)
    if callable(context_getter):
        context = context_getter()
        if context is not None:
            return cast(PhotoWizardContext, context)

    existing_context = getattr(wizard, "_photo_context", None)
    if existing_context is not None:
        return cast(PhotoWizardContext, existing_context)

    return WizardPhotoContext(
        photo_import_page=getattr(wizard, "_photo_import_page", None),
        photo_arrange_page=getattr(wizard, "_photo_arrange_page", None),
    )


def load_company_lines() -> list[str]:
    """company_info 設定から overview.company_lines を構築する。"""

    # Overview page は GUI 表示用ラベル更新と payload 組み立てに集中させたいので、
    # 永続化形式の解釈はこの helper に閉じ込める。
    from work_report_maker.gui.preset_manager import load_company_info

    company = load_company_info()
    lines: list[str] = []
    for address_line in company.get("address_lines", [""]):
        if address_line:
            lines.append(address_line)
    name = company.get("name", "")
    if name:
        lines.append(name)
    tel = company.get("tel", "")
    if tel:
        lines.append(f"TEL  {tel}")
    fax = company.get("fax", "")
    if fax:
        lines.append(f"FAX  {fax}")
    return lines
