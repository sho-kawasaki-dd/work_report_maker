from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEPENDENCIES_DIR = PROJECT_ROOT / "dependencies"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
DEFAULT_REPORT_JSON = PROJECT_ROOT / "data" / "raw_report.json"
LEGACY_REPORT_JSON = PROJECT_ROOT / "data" / "report.json"
OUTPUT_PDF = PROJECT_ROOT / "full_report.pdf"

PHOTO_WIDTH_MM = 100.0
PHOTO_HEIGHT_MM = 75.0
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

_DLL_DIRECTORIES: list[object] = []
_runtime_configured = False


def _prepend_env_path(name: str, value: Path) -> None:
    current = os.environ.get(name, "")
    entries = [entry for entry in current.split(os.pathsep) if entry]
    value_str = str(value)
    if value_str not in entries:
        os.environ[name] = os.pathsep.join([value_str, *entries]) if entries else value_str


def configure_weasyprint_runtime() -> None:
    global _runtime_configured
    if _runtime_configured:
        return
    if os.name != "nt":
        _runtime_configured = True
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

    _runtime_configured = True
