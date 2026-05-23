"""Windows 资源管理器右键菜单：用易图打开。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from seephoto.formats import ALL_EXTENSIONS

if sys.platform == "win32":
    import winreg

_MARKER = r"Software\llso\Yitu"
_ASSOC_ROOT = r"Software\Classes\SystemFileAssociations"
_SHELL_NAME = "YituOpen"
_MENU_LABEL = "用易图打开"


def app_executable() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(sys.argv[0]).resolve()


def is_registered() -> bool:
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _MARKER) as key:
            winreg.QueryValueEx(key, "ContextMenu")
            return True
    except OSError:
        return False


def register(exe_path: Path | None = None) -> None:
    if sys.platform != "win32":
        raise OSError("仅支持 Windows")

    exe = Path(exe_path or app_executable()).resolve()
    if not exe.is_file():
        raise FileNotFoundError(f"找不到程序：{exe}")

    command = f'"{exe}" "%1"'
    icon = str(exe)

    for ext in sorted(ALL_EXTENSIONS):
        base = f"{_ASSOC_ROOT}\\{ext}\\shell\\{_SHELL_NAME}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as sk:
            winreg.SetValueEx(sk, "", 0, winreg.REG_SZ, _MENU_LABEL)
            winreg.SetValueEx(sk, "Icon", 0, winreg.REG_SZ, icon)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{base}\\command") as ck:
            winreg.SetValueEx(ck, "", 0, winreg.REG_SZ, command)

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _MARKER) as mk:
        winreg.SetValueEx(mk, "ContextMenu", 0, winreg.REG_SZ, "1")
        winreg.SetValueEx(mk, "Executable", 0, winreg.REG_SZ, str(exe))


def unregister() -> None:
    if sys.platform != "win32":
        return

    for ext in sorted(ALL_EXTENSIONS):
        base = f"{_ASSOC_ROOT}\\{ext}\\shell\\{_SHELL_NAME}"
        _delete_tree(winreg.HKEY_CURRENT_USER, base)

    _delete_tree(winreg.HKEY_CURRENT_USER, _MARKER)


def _delete_tree(root, subkey: str) -> None:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            while True:
                try:
                    child = winreg.EnumKey(key, 0)
                    _delete_tree(root, f"{subkey}\\{child}")
                except OSError:
                    break
        winreg.DeleteKey(root, subkey)
    except OSError:
        pass
