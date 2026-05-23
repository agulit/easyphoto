"""LRU cache for decoded display pixmaps."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtGui import QPixmap

from seephoto.display_loader import DisplayResult


class PixmapCache:
    def __init__(self, max_items: int = 16) -> None:
        self._max = max_items
        self._data: OrderedDict[Path, tuple[QPixmap, DisplayResult]] = OrderedDict()

    def get(self, path: Path) -> tuple[QPixmap, DisplayResult] | None:
        key = path.resolve()
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, path: Path, pixmap: QPixmap, meta: DisplayResult) -> None:
        key = path.resolve()
        self._data[key] = (pixmap, meta)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()
