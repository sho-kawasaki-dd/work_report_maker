"""ReportWizard 完了時の payload 組み立てを補助するヘルパー。

GUI は photo data をメモリ上の bytes として保持しているが、既存の raw report 形式は
`photo_path` を前提にしている。このモジュールは、その変換を UI クラス本体から分離し、
一時ディレクトリの所有権を呼び出し側へ返す。
"""

from __future__ import annotations

from dataclasses import dataclass
import tempfile
from pathlib import Path
from typing import Any, Sequence

from work_report_maker.gui.pages.photo_import_page import PhotoItem


@dataclass(frozen=True)
class BuiltPhotos:
    """photos 配列と、その裏で確保した一時ディレクトリを束ねる戻り値。"""

    photos: list[dict]
    temp_dir: tempfile.TemporaryDirectory[str] | None


@dataclass(frozen=True)
class ReportBuildResult:
    """最終 payload と一時ディレクトリ所有権をまとめた戻り値。"""

    payload: dict[str, Any]
    photo_tmp_dir: tempfile.TemporaryDirectory[str] | None


def build_photos_payload(photo_items: Sequence[PhotoItem]) -> BuiltPhotos:
    """PhotoItem 群を raw_report.photos 互換の辞書配列へ変換する。

    ここで作る file URI は、GUI 内で編集中の bytes を既存の PDF 生成経路へ受け渡すための
    橋渡しである。呼び出し側は返された TemporaryDirectory を保持し、PDF 生成が終わるまで
    破棄しないことが前提になる。
    """

    items = list(photo_items)
    if not items:
        return BuiltPhotos(photos=[], temp_dir=None)

    temp_dir = tempfile.TemporaryDirectory(prefix="wrm_photos_")
    tmp_path = Path(temp_dir.name)
    photos: list[dict] = []

    for index, item in enumerate(items, start=1):
        # 写真番号とファイル名は現在の arrange 順を正とする。以降の report 生成系は
        # この順序をそのまま完成版の photo_pages へ反映する。
        ext = "jpg" if item.format == "jpeg" else item.format
        filename = f"{index:04d}.{ext}"
        file_path = tmp_path / filename
        file_path.write_bytes(item.data)

        photos.append({
            "no": index,
            "photo_path": file_path.as_uri(),
            "site": item.site,
            "work_date": item.work_date,
            "location": item.location,
            "work_content": item.work_content,
            "remarks": item.remarks,
        })

    return BuiltPhotos(photos=photos, temp_dir=temp_dir)


def build_report_payload(
    *,
    project_name: Any,
    cover: dict,
    overview: dict,
    photo_items: Sequence[PhotoItem],
) -> ReportBuildResult:
    """ReportWizard が出力する raw payload を組み立てる。

    GUI 側ではプロジェクト名も保持しているが、PDF 生成の共通バックエンドが期待する raw report
    契約では最上位 `title` が必須である。したがってここでは cover.title を正とし、未入力時だけ
    project_name を fallback として補う。
    """

    built_photos = build_photos_payload(photo_items)
    report_title = str(cover.get("title") or project_name or "")
    return ReportBuildResult(
        payload={
            "title": report_title,
            "project_name": project_name,
            "cover": cover,
            "overview": overview,
            "photos": built_photos.photos,
        },
        photo_tmp_dir=built_photos.temp_dir,
    )