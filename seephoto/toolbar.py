"""Bottom photo toolbar — Windows Photo Viewer style actions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class PhotoToolbar(QWidget):
    rotate_left = Signal()
    rotate_right = Signal()
    info_clicked = Signal()
    crop_clicked = Signal()
    adjust_clicked = Signal()
    fullscreen_clicked = Signal()
    print_clicked = Signal()
    delete_clicked = Signal()
    copy_clicked = Signal()
    save_as_clicked = Signal()
    reveal_folder_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PhotoToolbar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        def btn(text: str, tip: str, slot) -> QPushButton:
            b = QPushButton(text)
            b.setObjectName("ToolBtn")
            b.setToolTip(tip)
            b.setFixedSize(52, 48)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            layout.addWidget(b)
            return b

        layout.addStretch()
        btn("↺", "逆时针旋转 (Ctrl+,)", self.rotate_left.emit)
        btn("↻", "顺时针旋转 (Ctrl+.)", self.rotate_right.emit)
        self._sep(layout)
        btn("ℹ", "图片信息 / EXIF", self.info_clicked.emit)
        btn("✂", "裁剪", self.crop_clicked.emit)
        btn("◐", "专业调色 (Ctrl+Shift+L)", self.adjust_clicked.emit)
        btn("⛶", "全屏浏览 (F11 · Esc 退出)", self.fullscreen_clicked.emit)
        self._sep(layout)
        btn("⎙", "打印 (Ctrl+P)", self.print_clicked.emit)
        btn("📋", "复制到剪贴板", self.copy_clicked.emit)
        btn("💾", "另存为…", self.save_as_clicked.emit)
        btn("📁", "打开所在文件夹 (Ctrl+Shift+E)", self.reveal_folder_clicked.emit)
        self._sep(layout)
        btn("🗑", "删除 (Del)", self.delete_clicked.emit)
        layout.addStretch()

    @staticmethod
    def _sep(layout: QHBoxLayout) -> None:
        from PySide6.QtWidgets import QFrame

        line = QFrame()
        line.setObjectName("ToolSep")
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedHeight(36)
        layout.addWidget(line)
