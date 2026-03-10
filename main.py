from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path(__file__).resolve().parent
DEPENDENCIES_DIR = PROJECT_ROOT / "dependencies"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OUTPUT_PDF = PROJECT_ROOT / "full_report.pdf"
_DLL_DIRECTORIES: list[object] = []


def _prepend_env_path(name: str, value: Path) -> None:
    current = os.environ.get(name, "")
    entries = [entry for entry in current.split(os.pathsep) if entry]
    value_str = str(value)
    if value_str not in entries:
        os.environ[name] = os.pathsep.join([value_str, *entries]) if entries else value_str


def configure_weasyprint_runtime() -> None:
    if os.name != "nt":
        return

    bin_dir = DEPENDENCIES_DIR / "bin"
    loaders_dir = DEPENDENCIES_DIR / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders"
    loaders_cache = DEPENDENCIES_DIR / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders.cache"
    fonts_dir = DEPENDENCIES_DIR / "etc" / "fonts"
    fonts_conf = fonts_dir / "fonts.conf"
    share_dir = DEPENDENCIES_DIR / "share"

    required_paths = [bin_dir, loaders_dir, fonts_dir, fonts_conf, share_dir]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        missing = "\n".join(f"- {path}" for path in missing_paths)
        raise FileNotFoundError(
            "WeasyPrint dependencies are incomplete. Missing paths:\n"
            f"{missing}"
        )

    _prepend_env_path("PATH", bin_dir)
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is not None:
        _DLL_DIRECTORIES.append(add_dll_directory(str(bin_dir)))

    os.environ["GDK_PIXBUF_MODULEDIR"] = str(loaders_dir)
    if loaders_cache.exists():
        os.environ["GDK_PIXBUF_MODULE_FILE"] = str(loaders_cache)

    os.environ["FONTCONFIG_PATH"] = str(fonts_dir)
    os.environ["FONTCONFIG_FILE"] = str(fonts_conf)
    _prepend_env_path("XDG_DATA_DIRS", share_dir)


configure_weasyprint_runtime()

try:
    from weasyprint import HTML
except OSError as exc:
    raise RuntimeError(
        "Failed to load WeasyPrint runtime libraries from the bundled dependencies directory: "
        f"{DEPENDENCIES_DIR}"
    ) from exc


def generate_full_report() -> None:
    photo_data = [
        {
            "no": index + 1,
            "location": f"場所{index + 1}",
            "memo": f"備考{index + 1}",
            "photo_path": "sample.jpg",
        }
        for index in range(10)
    ]

    for item in photo_data:
        photo_path = Path(item["photo_path"])
        if not photo_path.is_absolute():
            photo_path = PROJECT_ROOT / photo_path
        item["photo_path"] = photo_path.resolve().as_uri()

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("report_tmp.html")

    html_content = template.render(
        report_title="令和8年度 現場写真報告書",
        create_date="2026年3月10日",
        author_name="山田 太郎",
        content_summary="本報告書は、現場の進捗状況を記録したものです。\n詳細は各ページの写真を参照してください。",
        photo_items=photo_data,
    )

    HTML(string=html_content, base_url=str(TEMPLATES_DIR.resolve())).write_pdf(OUTPUT_PDF)


if __name__ == "__main__":
    generate_full_report()