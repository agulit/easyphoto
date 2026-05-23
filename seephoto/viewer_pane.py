"""Image area with side navigation arrows."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from seephoto.viewer import ImageCanvas


class ViewerPane(QWidget):
    prev_clicked = Signal()
    next_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ViewerPane")
        self.setAcceptDrops(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = ImageCanvas()
        layout.addWidget(self.canvas)

        self.btn_prev = QPushButton("‹", self.canvas)
        self.btn_prev.setObjectName("NavBtn")
        self.btn_prev.setFixedSize(48, 96)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setToolTip("上一张 (←)")
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        self.btn_prev.hide()

        self.btn_next = QPushButton("›", self.canvas)
        self.btn_next.setObjectName("NavBtn")
        self.btn_next.setFixedSize(48, 96)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setToolTip("下一张 (→)")
        self.btn_next.clicked.connect(self.next_clicked.emit)
        self.btn_next.hide()

    def set_navigation_visible(self, visible: bool) -> None:
        self.btn_prev.setVisible(visible)
        self.btn_next.setVisible(visible)
        if visible:
            self._position_nav_buttons()

    def _position_nav_buttons(self) -> None:
        h = self.canvas.height()
        y = max(0, (h - self.btn_prev.height()) // 2)
        self.btn_prev.move(12, y)
        self.btn_next.move(self.canvas.width() - self.btn_next.width() - 12, y)
        self.btn_prev.raise_()
        self.btn_next.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.btn_prev.isVisible():
            self._position_nav_buttons()
        # 通知主窗口重新定位欢迎遮罩
        win = self.window()
        if hasattr(win, "_position_hint"):
            win._position_hint()
