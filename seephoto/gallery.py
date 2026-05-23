"""Directory image list and navigation."""

from __future__ import annotations

from pathlib import Path

from seephoto.formats import ALL_EXTENSIONS


def list_images(directory: Path) -> list[Path]:
    directory = Path(directory)
    if not directory.is_dir():
        return []

    files = [
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in ALL_EXTENSIONS
    ]
    files = [p.resolve() for p in files]
    files.sort(key=lambda p: p.name.lower())
    return files


def index_of(images: list[Path], current: Path) -> int:
    current = current.resolve()
    try:
        return images.index(current)
    except ValueError:
        return -1


def neighbor(images: list[Path], current: Path, delta: int) -> Path | None:
    if not images:
        return None
    idx = index_of(images, current)
    if idx < 0:
        return images[0] if delta >= 0 else images[-1]
    nxt = (idx + delta) % len(images)
    return images[nxt]
