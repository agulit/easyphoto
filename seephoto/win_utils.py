"""Windows DWM 标题栏黑化工具（Windows 10 1903+ / Windows 11）。"""

from __future__ import annotations

import sys


def apply_dark_titlebar(hwnd: int) -> None:
    """让窗口标题栏使用深色主题，并在 Win11 上直接设置为 app 背景色。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import ctypes.wintypes

        dwmapi = ctypes.windll.dwmapi
        hwnd_c = ctypes.wintypes.HWND(hwnd)

        # 1. DWMWA_USE_IMMERSIVE_DARK_MODE
        #    属性 20 = Win10 20H1+  属性 19 = Win10 1903–19H2（预发布）
        for attr in (20, 19):
            try:
                val = ctypes.c_int(1)
                if dwmapi.DwmSetWindowAttribute(
                    hwnd_c, attr, ctypes.byref(val), ctypes.sizeof(val)
                ) == 0:
                    break
            except Exception:
                pass

        # 2. Win11 专有：DWMWA_CAPTION_COLOR (35) — 直接设置标题栏颜色
        #    COLORREF = 0x00BBGGRR，对应 #121218 → B=0x12 G=0x12 R=0x18
        try:
            color = ctypes.c_int(0x00121218)   # COLORREF: BGR 顺序
            dwmapi.DwmSetWindowAttribute(hwnd_c, 35, ctypes.byref(color), ctypes.sizeof(color))
        except Exception:
            pass

        # 3. Win11：DWMWA_BORDER_COLOR (34) — 边框颜色
        try:
            border = ctypes.c_int(0x00323248)
            dwmapi.DwmSetWindowAttribute(hwnd_c, 34, ctypes.byref(border), ctypes.sizeof(border))
        except Exception:
            pass

        # 4. Win11：DWMWA_TEXT_COLOR (36) — 标题文字颜色
        try:
            text_color = ctypes.c_int(0x00EFE8E8)
            dwmapi.DwmSetWindowAttribute(hwnd_c, 36, ctypes.byref(text_color), ctypes.sizeof(text_color))
        except Exception:
            pass

    except Exception:
        pass
