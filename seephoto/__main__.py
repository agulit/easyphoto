"""Entry: python -m seephoto [image_or_folder]"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv

    # 先显示界面骨架，再加载较重模块
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QSplashScreen

    app = QApplication(argv)
    app.setApplicationName("易图")
    app.setOrganizationName("llso")
    app.setStyle("Fusion")

    # 设置全局图标（标题栏 + 任务栏）
    import sys as _sys
    from PySide6.QtGui import QIcon
    _base = Path(getattr(_sys, "_MEIPASS", Path(__file__).parent.parent))
    _icon_path = _base / "assets" / "icon.ico"
    if not _icon_path.exists():
        _icon_path = _base / "assets" / "app_icon.png"
    if _icon_path.exists():
        app.setWindowIcon(QIcon(str(_icon_path)))

    splash_pix = QPixmap(420, 100)
    splash_pix.fill(QColor("#121218"))
    painter = QPainter(splash_pix)
    painter.setPen(QColor("#c8d4ff"))
    painter.drawText(splash_pix.rect(), Qt.AlignmentFlag.AlignCenter, "易图  启动中…")
    painter.end()
    splash = QSplashScreen(splash_pix)
    splash.show()
    app.processEvents()

    from seephoto.mainwindow import MainWindow
    from seephoto.theme import STYLESHEET

    app.setStyleSheet(STYLESHEET)

    initial: Path | None = None
    if len(argv) > 1:
        p = Path(argv[1])
        if p.exists():
            initial = p

    window = MainWindow(initial)
    window.show()
    splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
