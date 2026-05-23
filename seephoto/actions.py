"""File actions: print, copy, save, delete, crop."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

def pixmap_to_pil(pixmap: QPixmap) -> Image.Image:
    """QPixmap → PIL（兼容 PySide6 memoryview，无 setsize）。"""
    qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = qimg.width(), qimg.height()
    bpl = qimg.bytesPerLine()
    ptr = qimg.constBits()
    nbytes = bpl * h
    raw = bytes(ptr)[:nbytes]
    if bpl == w * 4:
        return Image.frombytes("RGBA", (w, h), raw).convert("RGB")
    rows = bytearray()
    for y in range(h):
        row = raw[y * bpl : y * bpl + w * 4]
        rows.extend(row)
    return Image.frombytes("RGBA", (w, h), bytes(rows)).convert("RGB")


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    """PIL → QPixmap（copy 避免缓冲区被回收）。"""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


def crop_pixmap(pixmap: QPixmap, rect: QRect) -> QPixmap:
    cropped = pixmap.copy(rect)
    return cropped


def copy_pixmap_to_clipboard(pixmap: QPixmap) -> None:
    QApplication.clipboard().setPixmap(pixmap)


def save_pixmap_as(pixmap: QPixmap, parent, default_name: str) -> Path | None:
    path, _ = QFileDialog.getSaveFileName(
        parent,
        "另存为",
        default_name,
        "JPEG (*.jpg);;PNG (*.png);;BMP (*.bmp);;所有文件 (*.*)",
    )
    if not path:
        return None
    p = Path(path)
    if not p.suffix:
        p = p.with_suffix(".jpg")
    img = pixmap_to_pil(pixmap)
    fmt = p.suffix.lower().lstrip(".")
    if fmt in ("jpg", "jpeg"):
        img.save(p, "JPEG", quality=92)
    elif fmt == "png":
        img.save(p, "PNG")
    else:
        img.save(p)
    return p


def print_pixmap(pixmap: QPixmap, parent) -> bool:
    try:
        from PySide6.QtGui import QPageLayout, QPageSize
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
    except ImportError:
        return _print_via_shell(pixmap, parent)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageOrientation(QPageLayout.Orientation.Portrait)
    dialog = QPrintDialog(printer, parent)
    if dialog.exec() != QPrintDialog.DialogCode.Accepted:
        return False

    from PySide6.QtGui import QPainter

    painter = QPainter(printer)
    rect = painter.viewport()
    scaled = pixmap.scaled(
        rect.size(),
        aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
        mode=Qt.TransformationMode.SmoothTransformation,
    )
    x = (rect.width() - scaled.width()) // 2
    y = (rect.height() - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    return True


def _print_via_shell(pixmap: QPixmap, parent) -> bool:
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = Path(tmp.name)
            pixmap.save(str(path))
        if sys.platform == "win32":
            os.startfile(str(path), "print")
            return True
        QMessageBox.information(parent, "打印", "请使用「另存为」后手动打印。")
        return False
    except Exception as exc:
        QMessageBox.warning(parent, "打印", f"打印失败: {exc}")
        return False


def reveal_file_in_folder(path: Path, parent=None) -> bool:
    """在系统文件管理器中打开所在文件夹并选中该文件。"""
    path = Path(path).resolve()
    if not path.is_file():
        if parent is not None:
            QMessageBox.warning(parent, "易图", f"文件不存在：\n{path}")
        return False
    folder = path.parent
    try:
        if sys.platform == "win32":
            import subprocess

            # explorer /select,"完整路径"
            subprocess.Popen(["explorer", "/select,", str(path)])
            return True
        if sys.platform == "darwin":
            import subprocess

            subprocess.Popen(["open", "-R", str(path)])
            return True
        import subprocess

        subprocess.Popen(["xdg-open", str(folder)])
        return True
    except Exception as exc:
        if parent is not None:
            QMessageBox.warning(parent, "易图", f"无法打开文件夹：{exc}")
        return False


def delete_file_with_confirm(path: Path, parent) -> bool:
    reply = QMessageBox.question(
        parent,
        "删除",
        f"确定要永久删除此文件吗？\n\n{path.name}",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return False
    try:
        path.unlink()
        return True
    except Exception as exc:
        QMessageBox.warning(parent, "删除", f"无法删除: {exc}")
        return False


def load_full_pixmap(path: Path, max_edge: int = 8192) -> QPixmap:
    """Load image at higher resolution for crop/save operations."""
    from seephoto.display_loader import load_for_display

    result = load_for_display(path, max_edge)
    return QPixmap.fromImage(result.image)
