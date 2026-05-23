"""Interactive crop dialog."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)


class CropCanvas(QWidget):
    """Draw image and rubber-band crop selection."""

    crop_changed = Signal(QRect)

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = pixmap
        self._scaled = pixmap.scaled(
            900,
            600,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._offset = QPoint(0, 0)
        self._drag_start: QPoint | None = None
        self._selection = QRect()
        self.setMinimumSize(self._scaled.width() + 40, self._scaled.height() + 40)
        self.setMouseTracking(True)

    def _image_rect(self) -> QRect:
        x = (self.width() - self._scaled.width()) // 2
        y = (self.height() - self._scaled.height()) // 2
        return QRect(x, y, self._scaled.width(), self._scaled.height())

    def _clamp_selection(self, rect: QRect) -> QRect:
        img = self._image_rect()
        r = rect.normalized().intersected(img)
        if r.width() < 4 or r.height() < 4:
            return QRect()
        return r

    def selection_in_source(self) -> QRect | None:
        """Map widget selection to source pixmap coordinates."""
        if self._selection.isEmpty():
            return None
        img = self._image_rect()
        sel = self._selection.intersected(img)
        if sel.isEmpty():
            return None
        sx = self._source.width() / self._scaled.width()
        sy = self._source.height() / self._scaled.height()
        rel_x = sel.x() - img.x()
        rel_y = sel.y() - img.y()
        return QRect(
            int(rel_x * sx),
            int(rel_y * sy),
            max(1, int(sel.width() * sx)),
            max(1, int(sel.height() * sy)),
        )

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.GlobalColor.black)
        img_rect = self._image_rect()
        p.drawPixmap(img_rect.topLeft(), self._scaled)
        if not self._selection.isEmpty():
            p.setPen(Qt.GlobalColor.white)
            p.setBrush(Qt.GlobalColor.transparent)
            p.drawRect(self._selection)
            p.fillRect(self._selection, QColor(0, 0, 0, 100))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self._selection = QRect(self._drag_start, self._drag_start)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            end = event.position().toPoint()
            self._selection = self._clamp_selection(
                QRect(self._drag_start, end)
            )
            self.crop_changed.emit(self._selection)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self._selection = self._clamp_selection(self._selection)
            self.update()

    def sizeHint(self):
        return QSize(
            self._scaled.width() + 48,
            self._scaled.height() + 48,
        )


class CropDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("裁剪")
        self.resize(960, 680)

        layout = QVBoxLayout(self)
        hint = QLabel("在图片上拖动鼠标框选要保留的区域")
        hint.setObjectName("CropHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self.canvas = CropCanvas(pixmap)
        layout.addWidget(self.canvas, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._result_rect: QRect | None = None

    def _on_ok(self) -> None:
        rect = self.canvas.selection_in_source()
        if not rect:
            QMessageBox.information(self, "裁剪", "请先框选裁剪区域。")
            return
        self._result_rect = rect
        self.accept()

    def crop_rect(self) -> QRect | None:
        return self._result_rect
