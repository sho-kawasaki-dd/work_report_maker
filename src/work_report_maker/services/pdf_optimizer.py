"""生成済み PDF の後処理をまとめる。 

WeasyPrint 側の出力結果を壊さずに構造最適化だけを担う層として分離し、
GUI/CLI のどちらからも同じ post-process を再利用できるようにする。
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def optimize_pdf_structure(pdf_path: Path) -> None:
    """pikepdf で PDF を再保存し、構造最適化を適用する。

    一時ファイルへ書き出してから置換するのは、同一パスへ直接保存して破損した場合でも
    元ファイルを失わないようにするためである。metadata は pikepdf の通常保存に任せ、
    ここでは削除系オプションを与えない。
    """

    try:
        import pikepdf
    except ImportError as exc:
        raise RuntimeError("pikepdf is required to optimize generated PDF files.") from exc

    target_path = Path(pdf_path)
    if not target_path.exists():
        raise FileNotFoundError(f"PDF file not found: {target_path}")

    # 置換前提の一時ファイルを同じディレクトリへ作ることで、rename を同一ボリューム内で完結させる。
    with tempfile.NamedTemporaryFile(
        prefix=f"{target_path.stem}_optimized_",
        suffix=target_path.suffix,
        dir=target_path.parent,
        delete=False,
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        with pikepdf.open(target_path) as pdf:
            pdf.save(tmp_path, linearize=True)
        tmp_path.replace(target_path)
    except Exception:
        # 中間ファイルだけは回収して、失敗時に呼び出し元へ例外を返す。
        if tmp_path.exists():
            tmp_path.unlink()
        raise