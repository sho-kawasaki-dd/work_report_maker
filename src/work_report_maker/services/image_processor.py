from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from PIL import Image
from PIL.Image import Resampling

from work_report_maker.config import (
    PHOTO_HEIGHT_MM,
    PHOTO_WIDTH_MM,
    SUPPORTED_IMAGE_EXTENSIONS,
)

_MAX_ZIP_RECURSION = 5


def load_image(path: Path) -> Image.Image:
    """対応拡張子(.jpg/.jpeg/.png)の画像を読み込む。"""
    ext = path.suffix.lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(f"未対応の画像形式です: {ext}")
    img = Image.open(path)
    img.load()
    return img


def _crop_to_4_3(img: Image.Image) -> Image.Image:
    """画像を中央クロップして 4:3 のアスペクト比に整形する。"""
    w, h = img.size
    target_ratio = 4 / 3

    current_ratio = w / h
    if abs(current_ratio - target_ratio) < 1e-6:
        return img

    if current_ratio > target_ratio:
        # 横長すぎる → 横を切る
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    else:
        # 縦長すぎる → 縦を切る
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        return img.crop((0, top, w, top + new_h))


def resize_for_template(img: Image.Image, dpi: int = 150) -> Image.Image:
    """テンプレート上の画像サイズ (100mm x 75mm) と指定DPIからリサイズする。

    アスペクト比が 4:3 でない場合は中央クロップしてから縮小する。
    元画像がターゲットより小さい場合はリサイズしない。
    """
    img = _crop_to_4_3(img)

    px_w = int(PHOTO_WIDTH_MM * dpi / 25.4)
    px_h = int(PHOTO_HEIGHT_MM * dpi / 25.4)

    w, h = img.size
    if w <= px_w and h <= px_h:
        return img

    return img.resize((px_w, px_h), Resampling.LANCZOS)


def compress_jpeg(img: Image.Image, quality: int = 75) -> bytes:
    """Pillow で JPEG 圧縮し bytes で返す。"""
    import io

    buf = io.BytesIO()
    rgb = img.convert("RGB") if img.mode != "RGB" else img
    rgb.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def is_pngquant_available() -> bool:
    return shutil.which("pngquant") is not None


def compress_png(img: Image.Image, quality_max: int = 75) -> bytes:
    """PNG 圧縮。pngquant があれば使い、なければ Pillow quantize() でフォールバック。"""
    import io

    if is_pngquant_available():
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        quality_min = max(quality_max - 20, 0)
        try:
            result = subprocess.run(
                [
                    "pngquant",
                    "--quality",
                    f"{quality_min}-{quality_max}",
                    "--speed",
                    "3",
                    "-",
                ],
                input=png_bytes,
                capture_output=True,
                check=False,
            )
            # pngquant の終了コード 99 は品質範囲外（入力をそのまま返す）
            if result.returncode in (0, 99):
                return result.stdout if result.returncode == 0 else png_bytes
        except OSError:
            pass
        # subprocess 失敗時はフォールバック
        return png_bytes

    # pngquant が無い場合: Pillow quantize
    quantized = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    buf = io.BytesIO()
    quantized.save(buf, format="PNG")
    return buf.getvalue()


def process_image(
    path: Path,
    dpi: int = 150,
    jpeg_quality: int = 75,
    png_quality_max: int = 75,
) -> tuple[bytes, str]:
    """load → resize → compress の統合パイプライン。

    Returns:
        (圧縮後バイト列, フォーマット文字列 "jpeg" or "png")
    """
    img = load_image(path)
    img = resize_for_template(img, dpi)

    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return compress_jpeg(img, jpeg_quality), "jpeg"
    else:
        return compress_png(img, png_quality_max), "png"


def _is_safe_path(base: Path, target: Path) -> bool:
    """展開先が base ディレクトリ内であることを検証する (パストラバーサル対策)。"""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def extract_images_from_zip(
    zip_path: Path,
    tmp_dir: Path,
    _depth: int = 0,
) -> list[Path]:
    """ZIP 内の対象拡張子ファイルを tmp_dir に展開しパスリストを返す。

    ZIP 内に ZIP があれば再帰展開する。無限ループ防止のため深さ制限あり。
    """
    if _depth >= _MAX_ZIP_RECURSION:
        return []

    results: list[Path] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            member_path = tmp_dir / info.filename
            if not _is_safe_path(tmp_dir, member_path):
                continue

            ext = Path(info.filename).suffix.lower()
            if ext not in SUPPORTED_IMAGE_EXTENSIONS and ext != ".zip":
                continue

            member_path.parent.mkdir(parents=True, exist_ok=True)
            zf.extract(info, tmp_dir)

            if ext == ".zip":
                nested_dir = tmp_dir / f"_nested_{_depth}_{Path(info.filename).stem}"
                nested_dir.mkdir(parents=True, exist_ok=True)
                results.extend(
                    extract_images_from_zip(member_path, nested_dir, _depth + 1)
                )
            else:
                results.append(member_path)

    return results


def collect_image_paths(source: Path) -> list[Path]:
    """フォルダなら再帰走査、ZIP なら temp 展開、ファイルならそのまま返す。

    注意: ZIP の場合、返されるパスは一時ディレクトリ内を指す。
    呼び出し側で TemporaryDirectory のライフサイクルを管理すること。
    """
    if source.is_dir():
        paths: list[Path] = []
        for child in sorted(source.rglob("*")):
            if not child.is_file():
                continue
            ext = child.suffix.lower()
            if ext in SUPPORTED_IMAGE_EXTENSIONS:
                paths.append(child)
            elif ext == ".zip":
                tmp = tempfile.mkdtemp(prefix="wrmzip_")
                paths.extend(extract_images_from_zip(child, Path(tmp)))
        return paths

    ext = source.suffix.lower()
    if ext == ".zip":
        tmp = tempfile.mkdtemp(prefix="wrmzip_")
        return extract_images_from_zip(source, Path(tmp))

    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        return [source]

    return []
