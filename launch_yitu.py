"""易图启动器 — 首次解压到 AppData，之后直接启动缓存（无需安装）。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def _resource(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def _read_version() -> str:
    return _resource("VERSION").read_text(encoding="utf-8").strip()


def _cache_dir(version: str) -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "llso" / "yitu" / version


def _bundle_zip() -> Path:
    return _resource("yitu_bundle.zip")


def _app_exe(cache: Path) -> Path:
    return cache / "易图.exe"


def _cache_ok(cache: Path, version: str) -> bool:
    marker = cache / ".ok"
    exe = _app_exe(cache)
    return (
        marker.is_file()
        and marker.read_text(encoding="utf-8").strip() == version
        and exe.is_file()
    )


def _purge_old_caches(root: Path, keep: str) -> None:
    if not root.is_dir():
        return
    for child in root.iterdir():
        if child.is_dir() and child.name != keep:
            shutil.rmtree(child, ignore_errors=True)


def _extract(zip_path: Path, dest: Path, version: str) -> None:
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)
    (dest / ".ok").write_text(version, encoding="utf-8")


def _show_error(message: str) -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "易图", 0x10)
        except Exception:
            pass


def main() -> int:
    try:
        version = _read_version()
        cache_root = _cache_dir(version).parent
        cache = _cache_dir(version)
        exe = _app_exe(cache)

        if not _cache_ok(cache, version):
            _purge_old_caches(cache_root, version)
            _extract(_bundle_zip(), cache, version)

        if not exe.is_file():
            _show_error(f"启动失败：找不到程序文件\n{exe}")
            return 1

        args = [str(exe), *sys.argv[1:]]
        return subprocess.call(args)
    except Exception as exc:
        _show_error(f"易图启动失败：\n{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
