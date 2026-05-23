"""Zoomable image canvas."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeyEvent, QPainter, QPixmap, QTransform, QWheelEvent

from seephoto.adjustments import AdjustParams, apply_adjustments
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)


_NAV_KEYS = frozenset(
    {
        Qt.Key.Key_Left,
        Qt.Key.Key_Right,
        Qt.Key.Key_Up,
        Qt.Key.Key_Down,
    }
)


class ImageCanvas(QGraphicsView):
    zoom_changed = Signal(float)

    ZOOM_MIN = 0.05
    ZOOM_MAX = 32.0
    ZOOM_STEP = 1.15

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)

        self.setRenderHints(
            self.renderHints()
            | QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # 关掉滚动条：平移靠鼠标拖拽，避免 QAbstractScrollArea 吞掉 ←→ 键
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setStyleSheet("background: #0e0e14; border: none;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 拖放由 MainWindow 的 eventFilter 处理，这里保持 False 避免内部干扰
        self.setAcceptDrops(False)

        self._zoom = 1.0
        self._pixmap: QPixmap | None = None
        self._source_pixmap: QPixmap | None = None
        self._base_pixmap: QPixmap | None = None
        self._adjust_params = AdjustParams()
        self._rotation = 0
        self._fit_mode = True
        self._original_size: tuple[int, int] = (0, 0)

    def clear_image(self) -> None:
        self._pixmap = None
        self._source_pixmap = None
        self._base_pixmap = None
        self._adjust_params = AdjustParams()
        self._rotation = 0
        self._item.setPixmap(QPixmap())
        self._scene.setSceneRect(0, 0, 0, 0)
        self.resetTransform()
        self._zoom = 1.0

    def set_pixmap(
        self,
        pixmap: QPixmap,
        original_size: tuple[int, int] | None = None,
        *,
        reset_view: bool = True,
    ) -> None:
        self._source_pixmap = pixmap
        self._adjust_params = AdjustParams()
        self._base_pixmap = pixmap
        self._rotation = 0
        self._original_size = original_size or (pixmap.width(), pixmap.height())
        if reset_view:
            # 切换图片时恢复「适应窗口」，不沿用上一张的缩放比例
            self._fit_mode = True
            self._zoom = 1.0
        self._apply_pixmap(pixmap)

    def source_pixmap(self) -> QPixmap | None:
        return self._source_pixmap

    def adjust_params(self) -> AdjustParams:
        return self._adjust_params

    def set_adjust_params(
        self, params: AdjustParams, *, rendered: QPixmap | None = None
    ) -> None:
        if not self._source_pixmap or self._source_pixmap.isNull():
            return
        self._adjust_params = params
        if rendered is not None and not rendered.isNull():
            base = rendered
        elif params.is_default():
            base = self._source_pixmap
        else:
            base = apply_adjustments(self._source_pixmap, params)
            if base is None:
                base = self._source_pixmap
        self._base_pixmap = base
        self._apply_pixmap(self._transformed(self._base_pixmap, self._rotation))

    def rotation_angle(self) -> int:
        return self._rotation

    def rotate_left(self) -> None:
        self._rotate_by(-90)

    def rotate_right(self) -> None:
        self._rotate_by(90)

    def reset_rotation(self) -> None:
        if self._rotation == 0 or not self._base_pixmap:
            return
        self._rotation = 0
        self._apply_pixmap(self._base_pixmap)

    def set_display_pixmap(self, pixmap: QPixmap) -> None:
        """Replace visible pixmap (e.g. after crop) and keep rotation cleared."""
        self._source_pixmap = pixmap
        self._adjust_params = AdjustParams()
        self._base_pixmap = pixmap
        self._rotation = 0
        self._original_size = (pixmap.width(), pixmap.height())
        self._apply_pixmap(pixmap)

    def current_pixmap(self) -> QPixmap | None:
        return self._pixmap

    def _rotate_by(self, delta: int) -> None:
        if not self._base_pixmap or self._base_pixmap.isNull():
            return
        self._rotation = (self._rotation + delta) % 360
        self._apply_pixmap(self._transformed(self._base_pixmap, self._rotation))

    def _transformed(self, pixmap: QPixmap, angle: int) -> QPixmap:
        if angle == 0:
            return pixmap
        t = QTransform().rotate(angle)
        return pixmap.transformed(
            t, Qt.TransformationMode.SmoothTransformation
        )

    def _apply_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._item.setPixmap(pixmap)
        self._scene.setSceneRect(pixmap.rect())
        self.centerOn(self._item)
        if self._fit_mode:
            self.fit_to_window()
        else:
            self.resetTransform()
            self.scale(self._zoom, self._zoom)
            self.centerOn(self._item)

    def pixmap_size(self) -> tuple[int, int]:
        return self._original_size

    def display_size(self) -> tuple[int, int]:
        if self._pixmap is None or self._pixmap.isNull():
            return 0, 0
        return self._pixmap.width(), self._pixmap.height()

    def zoom_factor(self) -> float:
        return self._zoom

    def set_fit_mode(self, enabled: bool) -> None:
        self._fit_mode = enabled
        if enabled and self._pixmap and not self._pixmap.isNull():
            self.fit_to_window()

    def fit_to_window(self) -> None:
        if not self._pixmap or self._pixmap.isNull():
            return
        self._fit_mode = True
        self.resetTransform()
        self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.transform().m11()
        self.zoom_changed.emit(self._zoom)

    def zoom_actual(self) -> None:
        if not self._pixmap or self._pixmap.isNull():
            return
        self._fit_mode = False
        self.resetTransform()
        self._zoom = 1.0
        self.centerOn(self._item)
        self.zoom_changed.emit(self._zoom)

    def zoom_in(self) -> None:
        self._zoom_by(self.ZOOM_STEP)

    def zoom_out(self) -> None:
        self._zoom_by(1.0 / self.ZOOM_STEP)

    def _zoom_by(self, factor: float) -> None:
        if not self._pixmap or self._pixmap.isNull():
            return
        self._fit_mode = False
        new_zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self._zoom * factor))
        scale = new_zoom / self._zoom
        self._zoom = new_zoom
        self.scale(scale, scale)
        self.zoom_changed.emit(self._zoom)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.angleDelta().y() > 0:
            self.zoom_in()
        elif event.angleDelta().y() < 0:
            self.zoom_out()
        event.accept()

    def _handle_nav_key(self, key: int) -> bool:
        if key not in _NAV_KEYS:
            return False
        win = self.window()
        if hasattr(win, "_navigate"):
            delta = -1 if key in (Qt.Key.Key_Left, Qt.Key.Key_Up) else 1
            win._navigate(delta)
            return True
        return False

    def event(self, e: QEvent) -> bool:
        # Intercept before QAbstractScrollArea scrolls horizontally on ← →
        if e.type() == QEvent.Type.KeyPress and isinstance(e, QKeyEvent):
            if self._handle_nav_key(e.key()):
                return True
        return super().event(e)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._handle_nav_key(event.key()):
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_mode and self._pixmap and not self._pixmap.isNull():
            self.fit_to_window()
