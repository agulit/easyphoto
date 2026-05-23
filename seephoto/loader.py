"""Load raster images and camera RAW files."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from seephoto.formats import is_raw_path

# Optional HEIC
try:
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
except ImportError:
    pass


class LoadError(Exception):
    pass


def _pil_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (18, 18, 22))
        if img.mode == "RGBA":
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img.convert("RGBA"), mask=img.split()[1])
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def load_common(path: Path) -> Image.Image:
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            return _pil_to_rgb(img.copy())
    except Exception as exc:
        raise LoadError(f"无法打开图片: {path.name}") from exc


def load_raw(path: Path) -> Image.Image:
    try:
        import rawpy
    except ImportError as exc:
        raise LoadError("RAW 支持未安装 (rawpy)") from exc

    try:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=False,
                output_bps=8,
            )
    except Exception as exc:
        raise LoadError(f"无法解码 RAW: {path.name}") from exc

    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise LoadError(f"RAW 数据格式异常: {path.name}")

    return Image.fromarray(rgb.astype(np.uint8), mode="RGB")


def load_image(path: Path) -> Image.Image:
    path = Path(path)
    if not path.is_file():
        raise LoadError("文件不存在")

    suffix = path.suffix.lower()
    if suffix == ".svg":
        return _load_svg(path)
    if is_raw_path(path):
        return load_raw(path)
    return load_common(path)


def _load_svg(path: Path) -> Image.Image:
    try:
        from PySide6.QtCore import QByteArray, QBuffer, QIODevice
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except ImportError as exc:
        raise LoadError("SVG 需要 PySide6.QtSvg") from exc

    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        raise LoadError(f"无效 SVG: {path.name}")

    size = renderer.defaultSize()
    w = max(size.width(), 800)
    h = max(size.height(), 600)
    image = QImage(w, h, QImage.Format.Format_RGB888)
    image.fill(0x16161A)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(ba.data()))).convert("RGB")
