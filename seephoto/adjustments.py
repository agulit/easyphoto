"""Image tone / color adjustments (Pillow + NumPy)."""

from __future__ import annotations

from dataclasses import dataclass, fields

import numpy as np
from PIL import Image, ImageEnhance

from seephoto.actions import pil_to_pixmap, pixmap_to_pil


@dataclass(frozen=True)
class AdjustParams:
    brightness: int = 0    # 亮度
    contrast: int = 0      # 对比度
    highlights: int = 0    # 高光
    shadows: int = 0       # 阴影
    saturation: int = 0    # 饱和度
    warmth: int = 0        # 色温
    hue: int = 0           # 色相

    def is_default(self) -> bool:
        return all(getattr(self, f.name) == 0 for f in fields(self))


def _enhance_factor(value: int, span: float = 1.0) -> float:
    return max(0.05, 1.0 + (value / 100.0) * span)


def _apply_warmth(img: Image.Image, warmth: int) -> Image.Image:
    if warmth == 0:
        return img
    shift = int(warmth * 0.85)
    r, g, b = img.split()
    r = r.point(lambda i, s=shift: min(255, i + s))
    b = b.point(lambda i, s=shift: max(0, i - s))
    return Image.merge("RGB", (r, g, b))


def _apply_hue(img: Image.Image, hue: int) -> Image.Image:
    if hue == 0:
        return img
    hsv = img.convert("HSV")
    h, s, v = hsv.split()
    shift = int(hue / 100.0 * 128)
    h = h.point(lambda i, sh=shift: int((i + sh) % 256))
    return Image.merge("HSV", (h, s, v)).convert("RGB")


def _apply_shadows_highlights(arr: np.ndarray, shadows: int, highlights: int) -> np.ndarray:
    """Lift shadows / adjust highlights via luminance mask."""
    if shadows == 0 and highlights == 0:
        return arr
    lum = (
        0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    ) / 255.0
    if shadows != 0:
        amount = shadows / 100.0 * 90.0
        mask = np.clip(1.0 - lum * 1.8, 0.0, 1.0) ** 1.4
        arr = arr + mask[:, :, np.newaxis] * amount
    if highlights != 0:
        amount = highlights / 100.0 * 90.0
        mask = np.clip((lum - 0.42) * 2.0, 0.0, 1.0) ** 1.3
        arr = arr + mask[:, :, np.newaxis] * amount
    return arr


def apply_adjustments_pil(img: Image.Image, params: AdjustParams) -> Image.Image:
    if params.is_default():
        return img.copy()

    out = img.convert("RGB")

    if params.brightness != 0:
        out = ImageEnhance.Brightness(out).enhance(_enhance_factor(params.brightness))
    if params.contrast != 0:
        out = ImageEnhance.Contrast(out).enhance(_enhance_factor(params.contrast))

    if params.shadows != 0 or params.highlights != 0:
        arr = np.asarray(out, dtype=np.float32)
        arr = _apply_shadows_highlights(arr, params.shadows, params.highlights)
        out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    if params.saturation != 0:
        out = ImageEnhance.Color(out).enhance(_enhance_factor(params.saturation))
    if params.warmth != 0:
        out = _apply_warmth(out, params.warmth)
    if params.hue != 0:
        out = _apply_hue(out, params.hue)
    return out


def downscale_for_preview(img: Image.Image, max_edge: int = 1200) -> Image.Image:
    """缩小副本用于拖动预览，减轻卡顿。"""
    w, h = img.size
    m = max(w, h)
    if m <= max_edge:
        return img
    scale = max_edge / m
    nw, nh = int(w * scale), int(h * scale)
    return img.resize((max(1, nw), max(1, nh)), Image.Resampling.BILINEAR)


def apply_adjustments(pixmap, params: AdjustParams):
    from PySide6.QtGui import QPixmap

    if pixmap is None or pixmap.isNull() or params.is_default():
        return pixmap
    pil = pixmap_to_pil(pixmap)
    adjusted = apply_adjustments_pil(pil, params)
    return pil_to_pixmap(adjusted)
