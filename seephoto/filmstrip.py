"""Bottom thumbnail strip for the current folder."""

from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEvent, QObject, Qt, QThreadPool, QRunnable, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from seephoto.formats import is_raw_path

THUMB_SIZE = 84
CAPTION_H = 18
CELL_MARGIN = 6
SEL_PAD = 4          # 选中时蓝色底衬露出的边宽
CELL_W = THUMB_SIZE + CELL_MARGIN * 2
CELL_H = THUMB_SIZE + SEL_PAD * 2 + 6 + CAPTION_H + CELL_MARGIN * 2


def _same_path(a: Path | None, b: Path | None) -> bool:
    if a is None or b is None:
        return False
    return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


def _make_thumbnail(path: Path) -> QPixmap | None:
    try:
        if is_raw_path(path):
            return _thumb_from_raw(path)
        with Image.open(path) as img:
            img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            elif img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (30, 30, 38))
                bg.paste(img, mask=img.split()[3])
                img = bg
            data = img.tobytes("raw", "RGB")
            from PySide6.QtGui import QImage

            qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qimg)
    except Exception:
        return None


def _thumb_from_raw(path: Path) -> QPixmap | None:
    try:
        import rawpy
    except ImportError:
        return None
    try:
        with rawpy.imread(str(path)) as raw:
            thumb = raw.extract_thumb()
            if thumb is None:
                return None
            if thumb.format == rawpy.ThumbFormat.JPEG:
                img = Image.open(io.BytesIO(thumb.data))
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                img = Image.fromarray(thumb.data)
            else:
                return None
            img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            data = img.tobytes("raw", "RGB")
            from PySide6.QtGui import QImage

            qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qimg)
    except Exception:
        return None


class _ThumbSignals(QObject):
    ready = Signal(object, object)  # Path, QPixmap | None


class _ThumbTask(QRunnable):
    def __init__(self, path: Path, signals: _ThumbSignals) -> None:
        super().__init__()
        self.path = path
        self.signals = signals

    def run(self) -> None:
        pix = _make_thumbnail(self.path)
        self.signals.ready.emit(self.path, pix)


class ThumbCell(QWidget):
    clicked = Signal(object)

    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = path.resolve()
        self.setObjectName("ThumbCell")
        self.setFixedSize(CELL_W, CELL_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(CELL_MARGIN, CELL_MARGIN, CELL_MARGIN, CELL_MARGIN)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.preview = QLabel()
        self.preview.setObjectName("ThumbPreview")
        self.preview.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setText("…")

        self.caption = QLabel(path.name)
        self.caption.setObjectName("ThumbCaption")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setFixedHeight(CAPTION_H)
        self.caption.setMaximumWidth(CELL_W - CELL_MARGIN * 2)
        self.caption.setToolTip(path.name)
        fm = self.caption.fontMetrics()
        self.caption.setText(
            fm.elidedText(path.name, Qt.TextElideMode.ElideMiddle, CELL_W - CELL_MARGIN * 2)
        )

        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.caption, 0, Qt.AlignmentFlag.AlignHCenter)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                THUMB_SIZE,
                THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview.setPixmap(scaled)
            self.preview.setText("")
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("RAW" if is_raw_path(self.path) else "?")

    def set_selected(self, selected: bool) -> None:
        val = "true" if selected else "false"
        if self.property("selected") == val:
            return
        self.setProperty("selected", val)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def paintEvent(self, event) -> None:
        if self.property("selected") == "true":
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r = self.preview.geometry().adjusted(
                -SEL_PAD, -SEL_PAD, SEL_PAD, SEL_PAD
            )
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#3d5afe"))
            p.drawRoundedRect(r, 6, 6)
        super().paintEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.path)
        super().mousePressEvent(event)


class ThumbnailStrip(QWidget):
    image_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Filmstrip")
        self.setFixedHeight(CELL_H + 12)
        self.setAcceptDrops(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("FilmstripScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._container = QWidget()
        self._container.setObjectName("FilmstripInner")
        self._row = QHBoxLayout(self._container)
        self._row.setContentsMargins(12, 6, 12, 6)
        self._row.setSpacing(14)
        self._row.addStretch(1)

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

        # 让 viewport 的滚轮事件转为横向滚动
        self._scroll.viewport().installEventFilter(self)

        self._cells: dict[Path, ThumbCell] = {}
        self._current: Path | None = None  # 已 resolve 的路径
        self._thumb_signals = _ThumbSignals()
        self._thumb_signals.ready.connect(self._apply_thumb)
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(4)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """把鼠标滚轮的竖向滚动转为横向滚动。"""
        if event.type() == QEvent.Type.Wheel:
            we: QWheelEvent = event  # type: ignore[assignment]
            hbar = self._scroll.horizontalScrollBar()
            # 优先用横向 delta，若没有则用纵向 delta 代替
            delta = we.angleDelta().x() or we.angleDelta().y()
            step = hbar.singleStep() * 3
            hbar.setValue(hbar.value() - (step if delta > 0 else -step))
            return True
        return super().eventFilter(obj, event)

    def set_images(self, images: list[Path], current: Path | None = None) -> None:
        while self._row.count() > 1:
            item = self._row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells.clear()

        for path in images:
            cell = ThumbCell(path)
            cell.clicked.connect(self._on_cell_clicked)
            self._row.insertWidget(self._row.count() - 1, cell)
            self._cells[path.resolve()] = cell
            self._pool.start(_ThumbTask(path, self._thumb_signals))

        self.set_current(current)
        self.setVisible(bool(images))

    def set_current(self, path: Path | None) -> None:
        """只更新上一个与当前两个格子，避免几百张图时整栏刷新卡顿。"""
        new_key = path.resolve() if path else None
        if _same_path(new_key, self._current):
            return

        if self._current is not None:
            old_cell = self._cells.get(self._current)
            if old_cell:
                old_cell.set_selected(False)

        self._current = new_key

        if new_key is not None:
            cell = self._cells.get(new_key)
            if cell:
                cell.set_selected(True)
                QTimer.singleShot(0, lambda c=cell: self._scroll.ensureWidgetVisible(c, 20, 20))

    def _on_cell_clicked(self, path: Path) -> None:
        # 先更新选中样式，再加载大图，点击反馈即时
        self.set_current(path)
        self.image_selected.emit(path)

    def _apply_thumb(self, path: Path, pixmap: QPixmap | None) -> None:
        key = Path(path).resolve()
        cell = self._cells.get(key)
        if cell:
            cell.set_pixmap(pixmap)
