"""Fast display-sized image loading (avoids full-resolution decode)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from seephoto.formats import is_raw_path
from seephoto.loader import LoadError, _pil_to_rgb

_QT_IMAGE_FORMATS = frozenset(
    {".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".bmp", ".dib", ".webp", ".tif", ".tiff"}
)


@dataclass(frozen=True)
class DisplayResult:
    """Decoded image for on-screen display."""

    image: object  # QImage
    original_width: int
    original_height: int
    display_width: int
    display_height: int


def _fit_size(width: int, height: int, max_edge: int) -> tuple[int, int]:
    if max(width, height) <= max_edge:
        return width, height
    if width >= height:
        return max_edge, max(1, round(height * max_edge / width))
    return max(1, round(width * max_edge / height)), max_edge


def load_for_display(path: Path, max_edge: int = 3840) -> DisplayResult:
    path = Path(path)
    if not path.is_file():
        raise LoadError("文件不存在")

    suffix = path.suffix.lower()
    if suffix == ".svg":
        return _load_svg_display(path, max_edge)
    if is_raw_path(path):
        return _load_raw_display(path, max_edge)
    if suffix in _QT_IMAGE_FORMATS:
        result = _load_qt_scaled(path, max_edge)
        if result is not None:
            return result
    return _load_pil_display(path, max_edge)


def _load_qt_scaled(path: Path, max_edge: int) -> DisplayResult | None:
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage, QImageReader

    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    orig = reader.size()
    if not orig.isValid():
        return None

    ow, oh = orig.width(), orig.height()
    tw, th = _fit_size(ow, oh, max_edge)
    if (tw, th) != (ow, oh):
        reader.setScaledSize(QSize(tw, th))

    image = reader.read()
    if image.isNull():
        return None

    if image.format() != QImage.Format.Format_RGB888:
        image = image.convertToFormat(QImage.Format.Format_RGB888)

    return DisplayResult(image, ow, oh, image.width(), image.height())


def _load_pil_display(path: Path, max_edge: int) -> DisplayResult:
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            ow, oh = img.size
            img = _pil_to_rgb(img)
            tw, th = _fit_size(ow, oh, max_edge)
            if (tw, th) != (ow, oh):
                img = img.resize((tw, th), Image.Resampling.BILINEAR)
    except Exception as exc:
        raise LoadError(f"无法打开图片: {path.name}") from exc

    from PySide6.QtGui import QImage

    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
    return DisplayResult(qimg.copy(), ow, oh, img.width, img.height)


def load_raw_preview(path: Path, max_edge: int) -> DisplayResult | None:
    """
    极速通道：从 RAW 内嵌 JPEG 缩略图构建预览帧。
    相机写入的内嵌 JPEG 通常是完整分辨率，提取只需几十毫秒。
    返回 None 表示无内嵌缩略图或格式不支持，调用方应退回完整解码。
    """
    try:
        import rawpy
    except ImportError:
        return None

    try:
        with rawpy.imread(str(path)) as raw:
            try:
                thumb = raw.extract_thumb()
            except Exception:
                return None

            # 从内嵌数据读取 PIL 图像
            if thumb.format == rawpy.ThumbFormat.JPEG:
                from PIL import Image as PILImage
                import io as _io
                img = PILImage.open(_io.BytesIO(bytes(thumb.data)))
                img = img.convert("RGB")
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                from PIL import Image as PILImage
                import numpy as _np
                arr = _np.asarray(thumb.data)
                if arr.ndim != 3 or arr.shape[2] not in (3, 4):
                    return None
                if arr.shape[2] == 4:
                    arr = arr[:, :, :3]
                img = PILImage.fromarray(arr.astype(_np.uint8), mode="RGB")
            else:
                return None

            ow, oh = img.size
            if ow < 64 or oh < 64:
                return None

            tw, th = _fit_size(ow, oh, max_edge)
            if (tw, th) != (ow, oh):
                img = img.resize((tw, th), Image.Resampling.BILINEAR)

    except Exception:
        return None

    from PySide6.QtGui import QImage
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
    return DisplayResult(qimg.copy(), ow, oh, img.width, img.height)


def _load_raw_display(path: Path, max_edge: int) -> DisplayResult:
    try:
        import rawpy
    except ImportError as exc:
        raise LoadError("RAW 支持未安装 (rawpy)") from exc

    try:
        with rawpy.imread(str(path)) as raw:
            ow = raw.sizes.width or raw.sizes.raw_width
            oh = raw.sizes.height or raw.sizes.raw_height
            # 超过 12MP (约 4000×3000) 就用 half_size 加速解码，仍能满足显示
            use_half = (ow * oh) > 12_000_000 or max(ow, oh) > max_edge
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=use_half,
                no_auto_bright=False,
                output_bps=8,
            )
    except Exception as exc:
        raise LoadError(f"无法解码 RAW: {path.name}") from exc

    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise LoadError(f"RAW 数据格式异常: {path.name}")

    img = Image.fromarray(rgb.astype(np.uint8), mode="RGB")
    dw, dh = img.size
    tw, th = _fit_size(dw, dh, max_edge)
    if (tw, th) != (dw, dh):
        img = img.resize((tw, th), Image.Resampling.BILINEAR)

    from PySide6.QtGui import QImage

    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
    return DisplayResult(qimg.copy(), ow, oh, img.width, img.height)


def _load_svg_display(path: Path, max_edge: int) -> DisplayResult:
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        raise LoadError(f"无效 SVG: {path.name}")

    size = renderer.defaultSize()
    ow = max(size.width(), 800)
    oh = max(size.height(), 600)
    tw, th = _fit_size(ow, oh, max_edge)
    image = QImage(tw, th, QImage.Format.Format_RGB888)
    image.fill(0x16161A)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return DisplayResult(image, ow, oh, tw, th)
