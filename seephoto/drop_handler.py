"""Drag-and-drop helpers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

from seephoto.formats import ALL_EXTENSIONS


def mime_has_urls(event) -> bool:
    return event.mimeData().hasUrls()


def accept_file_drag(event: QDragEnterEvent | QDragMoveEvent) -> None:
    event.setDropAction(Qt.DropAction.CopyAction)
    event.accept()


def paths_from_drop(event: QDropEvent) -> list[Path]:
    paths: list[Path] = []
    for url in event.mimeData().urls():
        p = Path(url.toLocalFile())
        if p.exists():
            paths.append(p)
    return paths


def pick_open_path(paths: list[Path]) -> Path | None:
    for path in paths:
        path = Path(path)
        if path.is_dir():
            return path
        if path.is_file():
            ext = path.suffix.lower()
            if not ext or ext in ALL_EXTENSIONS:
                return path
    return Path(paths[0]) if paths else None
