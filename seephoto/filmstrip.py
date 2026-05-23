"""Bottom thumbnail strip for the current folder."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEvent, QObject, Qt, QThreadPool, QRunnable, Signal
from PySide6.QtGui import QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from seephoto.formats import is_raw_path

THUMB_SIZE = 88
CELL_W = 96
CELL_H = 104


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
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.preview = QLabel()
        self.preview.setObjectName("ThumbPreview")
        self.preview.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setText("…")

        self.caption = QLabel(path.name)
        self.caption.setObjectName("ThumbCaption")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setMaximumWidth(CELL_W - 8)
        self.caption.setToolTip(path.name)
        fm = self.caption.fontMetrics()
        self.caption.setText(fm.elidedText(path.name, Qt.TextElideMode.ElideMiddle, CELL_W - 8))

        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.caption)

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
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.path)
        super().mousePressEvent(event)


class ThumbnailStrip(QWidget):
    image_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Filmstrip")
        self.setFixedHeight(CELL_H + 16)
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
        self._row.setContentsMargins(8, 6, 8, 6)
        self._row.setSpacing(6)
        self._row.addStretch(1)

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

        # 让 viewport 的滚轮事件转为横向滚动
        self._scroll.viewport().installEventFilter(self)

        self._cells: dict[Path, ThumbCell] = {}
        self._current: Path | None = None
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
        path = path.resolve() if path else None
        self._current = path
        for p, cell in self._cells.items():
            cell.set_selected(p == path)
        if path and path in self._cells:
            self._scroll.ensureWidgetVisible(self._cells[path], 24, 24)

    def _on_cell_clicked(self, path: Path) -> None:
        self.image_selected.emit(path)

    def _apply_thumb(self, path: Path, pixmap: QPixmap | None) -> None:
        key = Path(path).resolve()
        cell = self._cells.get(key)
        if cell:
            cell.set_pixmap(pixmap)
