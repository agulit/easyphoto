"""关于对话框 — 展示软件信息、作者 logo。"""

from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget, QPushButton,
)

from seephoto import __version__

def _res(name: str) -> Path:
    """兼容 PyInstaller onefile 和开发模式的资源路径。"""
    import sys
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    return base / "assets" / name

_LOGO_PATH = _res("logo.png")
_ICON_PATH = _res("app_icon.png")


def _round_pixmap(px: QPixmap, radius: int = 12) -> QPixmap:
    """把 pixmap 裁成圆角，透明背景。"""
    out = QPixmap(px.size())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, px.width(), px.height(), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, px)
    p.end()
    return out


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 易图")
        self.setModal(True)
        self.setFixedSize(420, 320)
        self.setStyleSheet("""
            QDialog {
                background: #121218;
                border: 1px solid #2a2a3c;
                border-radius: 16px;
            }
            QLabel {
                background: transparent;
                color: #e8e8ec;
            }
            QPushButton#CloseBtn {
                background: #252535;
                color: #c0c0d0;
                border: 1px solid #3a3a50;
                border-radius: 8px;
                padding: 6px 24px;
                font-size: 13px;
            }
            QPushButton#CloseBtn:hover {
                background: #33334a;
                color: #ffffff;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

        # 顶部：app 图标 + 软件名
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        icon_label = QLabel()
        if _ICON_PATH.exists():
            px = QPixmap(str(_ICON_PATH)).scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(_round_pixmap(px, 16))
        icon_label.setFixedSize(72, 72)
        top_row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_lbl = QLabel("易图")
        name_lbl.setStyleSheet("font-size: 26px; font-weight: bold; color: #d8d8ee; letter-spacing: 4px;")
        ver_lbl = QLabel(f"版本 {__version__}")
        ver_lbl.setStyleSheet("font-size: 13px; color: #7878a0;")
        name_col.addWidget(name_lbl)
        name_col.addWidget(ver_lbl)
        top_row.addLayout(name_col)
        top_row.addStretch()
        root.addLayout(top_row)

        root.addSpacing(20)

        # 分割线
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #2a2a3c;")
        root.addWidget(line)
        root.addSpacing(20)

        # 作者 logo + 简介
        author_row = QHBoxLayout()
        author_row.setSpacing(20)

        logo_lbl = QLabel()
        if _LOGO_PATH.exists():
            px = QPixmap(str(_LOGO_PATH)).scaled(90, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            # logo 是白底黑字，做颜色反转以适应深色背景
            inv = QPixmap(px.size())
            inv.fill(QColor(30, 30, 40))
            p = QPainter(inv)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
            p.drawPixmap(0, 0, px)
            p.end()
            logo_lbl.setPixmap(_round_pixmap(inv, 8))
        logo_lbl.setFixedSize(100, 64)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_row.addWidget(logo_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(6)
        author_lbl = QLabel("作者  <b>llso</b>")
        author_lbl.setStyleSheet("font-size: 14px; color: #c0c0d4;")
        desc_lbl = QLabel("一款支持常见格式与 RAW 格式的轻量图片查看器\n支持 Nikon · Sony · DJI 等多厂商 RAW 文件")
        desc_lbl.setStyleSheet("font-size: 12px; color: #7070a0; line-height: 1.6;")
        desc_lbl.setWordWrap(True)

        # 联系方式（可点击）
        email = "58539199@qq.com"
        contact_lbl = QLabel(f'联系  <a href="mailto:{email}" style="color:#7baaf7;text-decoration:none;">{email}</a>')
        contact_lbl.setStyleSheet("font-size: 12px; color: #8080a8;")
        contact_lbl.setOpenExternalLinks(True)
        contact_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )

        info_col.addWidget(author_lbl)
        info_col.addWidget(desc_lbl)
        info_col.addWidget(contact_lbl)
        author_row.addLayout(info_col)
        root.addLayout(author_row)

        root.addStretch()

        # 关闭按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("CloseBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)
