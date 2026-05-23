"""Rich image metadata dialog — file info + full EXIF display."""

from __future__ import annotations

import io
import math
from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from seephoto.formats import is_raw_path


# ---------------------------------------------------------------------------
# EXIF helpers
# ---------------------------------------------------------------------------

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"


def _rational_to_float(v) -> float | None:
    """Convert PIL IFDRational / tuple(num, den) / float to float."""
    try:
        if isinstance(v, tuple) and len(v) == 2:
            d = v[1]
            return v[0] / d if d else None
        return float(v)
    except Exception:
        return None


def _fmt_shutter(v) -> str:
    s = _rational_to_float(v)
    if s is None:
        return str(v)
    if s >= 1:
        return f"{s:.1f} s"
    return f"1/{round(1 / s)} s"


def _fmt_aperture(v) -> str:
    f = _rational_to_float(v)
    return f"f/{f:.1f}" if f else str(v)


def _fmt_focal(v) -> str:
    f = _rational_to_float(v)
    return f"{f:.0f} mm" if f else str(v)


def _fmt_ev(v) -> str:
    f = _rational_to_float(v)
    if f is None:
        return str(v)
    sign = "+" if f > 0 else ""
    return f"{sign}{f:.1f} EV"


def _fmt_flash(code) -> str:
    if not isinstance(code, int):
        return str(code)
    fired = code & 0x1
    return "已闪光" if fired else "未闪光"


def _fmt_metering(code) -> str:
    TABLE = {
        0: "未知", 1: "平均测光", 2: "中央重点", 3: "点测光",
        4: "多点", 5: "多区测光", 6: "局部", 255: "其他",
    }
    return TABLE.get(code, str(code))


def _fmt_wb(code) -> str:
    return {0: "自动", 1: "手动"}.get(code, str(code))


def _fmt_exp_mode(code) -> str:
    return {0: "程序自动", 1: "手动曝光", 2: "自动包围"}.get(code, str(code))


def _fmt_scene(code) -> str:
    TABLE = {0: "标准", 1: "风景", 2: "人像", 3: "夜景"}
    return TABLE.get(code, str(code))


def _fmt_resolution_unit(code) -> str:
    return {1: "无单位", 2: "DPI", 3: "DPCM"}.get(code, str(code))


def _fmt_color_space(code) -> str:
    return {1: "sRGB", 65535: "未校准"}.get(code, str(code))


def _dms_to_decimal(dms, ref: str) -> float | None:
    """Degrees-Minutes-Seconds tuple → decimal degrees."""
    try:
        d = _rational_to_float(dms[0]) or 0
        m = _rational_to_float(dms[1]) or 0
        s = _rational_to_float(dms[2]) or 0
        val = d + m / 60 + s / 3600
        if ref in ("S", "W"):
            val = -val
        return val
    except Exception:
        return None


def _fmt_gps_dms(decimal: float, is_lat: bool) -> str:
    if decimal is None:
        return ""
    direction = ("N" if decimal >= 0 else "S") if is_lat else ("E" if decimal >= 0 else "W")
    decimal = abs(decimal)
    d = int(decimal)
    m = int((decimal - d) * 60)
    s = (decimal - d - m / 60) * 3600
    return f"{d}° {m}' {s:.2f}\" {direction}"


def _parse_gps(gps_ifd: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    lat_dms = gps_ifd.get(GPSTAGS.get("GPSLatitude", 2))
    lat_ref = gps_ifd.get(GPSTAGS.get("GPSLatitudeRef", 1), "N")
    lon_dms = gps_ifd.get(GPSTAGS.get("GPSLongitude", 4))
    lon_ref = gps_ifd.get(GPSTAGS.get("GPSLongitudeRef", 3), "E")
    alt_r   = gps_ifd.get(GPSTAGS.get("GPSAltitude", 6))
    alt_ref = gps_ifd.get(GPSTAGS.get("GPSAltitudeRef", 5), 0)

    # Try numeric keys if string keys fail
    if lat_dms is None:
        lat_dms = gps_ifd.get(2)
        lat_ref = gps_ifd.get(1, "N")
        lon_dms = gps_ifd.get(4)
        lon_ref = gps_ifd.get(3, "E")
        alt_r   = gps_ifd.get(6)
        alt_ref = gps_ifd.get(5, 0)

    if lat_dms and lon_dms:
        lat = _dms_to_decimal(lat_dms, lat_ref)
        lon = _dms_to_decimal(lon_dms, lon_ref)
        if lat is not None and lon is not None:
            rows.append(("纬度", _fmt_gps_dms(lat, True)))
            rows.append(("经度", _fmt_gps_dms(lon, False)))
            rows.append(("十进制坐标", f"{lat:.6f}, {lon:.6f}"))
            map_url = f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"
            rows.append(("查看地图", f'<a href="{map_url}" style="color:#6c8eff">Google Maps ↗</a>'))
    if alt_r is not None:
        alt = _rational_to_float(alt_r)
        if alt is not None:
            sign = -1 if alt_ref else 1
            rows.append(("海拔", f"{sign * alt:.1f} m"))
    return rows


def _get_pil_exif(img: Image.Image) -> dict[str, object]:
    """Return dict mapping tag-name → value from PIL image."""
    result: dict[str, object] = {}
    try:
        raw_exif = img.getexif()
    except Exception:
        return result
    if not raw_exif:
        return result
    for tag_id, value in raw_exif.items():
        name = TAGS.get(tag_id, str(tag_id))
        result[name] = value
    # IFD sub-tags
    try:
        from PIL.ExifTags import IFD
        for ifd_tag in IFD:
            try:
                ifd = raw_exif.get_ifd(ifd_tag)
                for k, v in ifd.items():
                    n = TAGS.get(k, str(k))
                    if n not in result:
                        result[n] = v
            except Exception:
                pass
    except Exception:
        pass
    return result


def _get_exif(path: Path) -> dict[str, object]:
    """Extract EXIF. For RAW, reads embedded JPEG to get full camera tags."""
    if is_raw_path(path):
        try:
            import rawpy
            with rawpy.imread(str(path)) as raw:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    img = Image.open(io.BytesIO(bytes(thumb.data)))
                    exif = _get_pil_exif(img)
                    if exif:
                        return exif
        except Exception:
            pass
    try:
        with Image.open(path) as img:
            return _get_pil_exif(img)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# HTML report builder
# ---------------------------------------------------------------------------

_CSS = """
body { font-family:'Segoe UI','Microsoft YaHei UI',sans-serif;
       font-size:13px; background:#1a1a24; color:#d8d8ec; margin:0; padding:8px; }
table { border-collapse:collapse; width:100%; }
td { padding:5px 10px; vertical-align:top; }
td.k { color:#9090b8; white-space:nowrap; width:140px; font-size:12px; }
td.v { color:#e8e8f8; }
h3   { color:#7888ff; font-size:13px; font-weight:600;
       margin:14px 0 4px 0; padding:6px 10px;
       background:#22223a; border-left:3px solid #5566ff;
       border-radius:0 6px 6px 0; }
hr   { border:none; border-top:1px solid #2a2a3c; margin:4px 0; }
"""


def _row(key: str, val) -> str:
    if val is None or val == "":
        return ""
    val_str = str(val) if not str(val).startswith("<a ") else val
    return f"<tr><td class='k'>{key}</td><td class='v'>{val_str}</td></tr>"


def _section(title: str, rows: list[tuple[str, str]]) -> str:
    if not rows:
        return ""
    inner = "".join(_row(k, v) for k, v in rows if v not in (None, ""))
    if not inner:
        return ""
    return f"<h3>{title}</h3><table>{inner}</table>"


def build_html_report(path: Path) -> str:
    path = Path(path).resolve()
    exif = _get_exif(path)
    stat = path.stat()

    # --- 文件信息 ---
    mtime = datetime.fromtimestamp(stat.st_mtime)
    file_rows: list[tuple[str, str]] = [
        ("文件名", path.name),
        ("路径",   str(path.parent)),
        ("大小",   _fmt_size(stat.st_size)),
        ("修改时间", mtime.strftime("%Y-%m-%d %H:%M:%S")),
    ]
    ctime = exif.get("DateTimeOriginal") or exif.get("DateTime")
    if ctime:
        file_rows.append(("拍摄时间", str(ctime).replace(":", "-", 2)))

    # --- 图像规格 ---
    img_rows: list[tuple[str, str]] = []
    if is_raw_path(path):
        img_rows.append(("格式", f"RAW ({path.suffix.upper().lstrip('.')})"))
        try:
            import rawpy
            with rawpy.imread(str(path)) as raw:
                ow = raw.sizes.width or raw.sizes.raw_width
                oh = raw.sizes.height or raw.sizes.raw_height
                mp = ow * oh / 1_000_000
                img_rows.append(("尺寸", f"{ow} × {oh}  ({mp:.1f} MP)"))
                if raw.color_desc:
                    img_rows.append(("色彩描述", raw.color_desc.decode("ascii", errors="replace")))
        except Exception:
            pass
    else:
        try:
            with Image.open(path) as img:
                ow, oh = img.size
                mp = ow * oh / 1_000_000
                img_rows.append(("格式", img.format or path.suffix.upper()))
                img_rows.append(("尺寸", f"{ow} × {oh}  ({mp:.1f} MP)"))
                img_rows.append(("色彩模式", img.mode))
                dpi = img.info.get("dpi")
                if dpi:
                    img_rows.append(("分辨率", f"{dpi[0]:.0f} × {dpi[1]:.0f} DPI"))
        except Exception:
            pass

    xres = _rational_to_float(exif.get("XResolution"))
    yres = _rational_to_float(exif.get("YResolution"))
    res_unit = exif.get("ResolutionUnit")
    if xres and yres and not any(k == "分辨率" for k, _ in img_rows):
        unit_str = _fmt_resolution_unit(res_unit) if res_unit else "DPI"
        img_rows.append(("分辨率", f"{xres:.0f} × {yres:.0f} {unit_str}"))
    cs = exif.get("ColorSpace")
    if cs:
        img_rows.append(("色彩空间", _fmt_color_space(cs)))

    # --- 相机信息 ---
    cam_rows: list[tuple[str, str]] = []
    make  = str(exif.get("Make", "")).strip()
    model = str(exif.get("Model", "")).strip()
    if model:
        cam_rows.append(("相机", model if model.startswith(make) else f"{make} {model}".strip()))
    lens = exif.get("LensModel") or exif.get("Lens")
    lens_make = exif.get("LensMake", "")
    if lens:
        cam_rows.append(("镜头", str(lens).strip()))
    elif lens_make:
        cam_rows.append(("镜头品牌", str(lens_make).strip()))
    sw = exif.get("Software", "")
    if sw:
        cam_rows.append(("软件", str(sw).strip()))

    # --- 曝光参数 ---
    exp_rows: list[tuple[str, str]] = []
    et = exif.get("ExposureTime")
    fn = exif.get("FNumber")
    iso = exif.get("ISOSpeedRatings") or exif.get("ISO")
    fl  = exif.get("FocalLength")
    fl35 = exif.get("FocalLengthIn35mmFilm")
    ev  = exif.get("ExposureBiasValue")
    metering = exif.get("MeteringMode")
    flash    = exif.get("Flash")
    wb       = exif.get("WhiteBalance")
    exp_mode = exif.get("ExposureMode")
    scene    = exif.get("SceneCaptureType")

    if et   is not None: exp_rows.append(("快门速度", _fmt_shutter(et)))
    if fn   is not None: exp_rows.append(("光圈",     _fmt_aperture(fn)))
    if iso  is not None: exp_rows.append(("ISO",      str(iso)))
    if fl   is not None:
        fl_str = _fmt_focal(fl)
        if fl35:
            fl_str += f"  (等效 {fl35} mm)"
        exp_rows.append(("焦距", fl_str))
    if ev   is not None: exp_rows.append(("曝光补偿", _fmt_ev(ev)))
    if metering is not None: exp_rows.append(("测光模式", _fmt_metering(metering)))
    if flash    is not None: exp_rows.append(("闪光灯",   _fmt_flash(flash)))
    if wb       is not None: exp_rows.append(("白平衡",   _fmt_wb(wb)))
    if exp_mode is not None: exp_rows.append(("曝光模式", _fmt_exp_mode(exp_mode)))
    if scene    is not None: exp_rows.append(("场景类型", _fmt_scene(scene)))

    # --- GPS ---
    gps_ifd = exif.get("GPSInfo")
    gps_rows = _parse_gps(gps_ifd) if isinstance(gps_ifd, dict) else []

    # --- 著作权 ---
    credit_rows: list[tuple[str, str]] = []
    for tag, label in (("Artist", "作者"), ("Copyright", "版权"), ("ImageDescription", "描述")):
        v = exif.get(tag)
        if v:
            credit_rows.append((label, str(v).strip()))

    # --- 组合 HTML ---
    parts = [f"<style>{_CSS}</style>"]
    parts.append(_section("📄  文件信息",   file_rows))
    parts.append(_section("📐  图像规格",   img_rows))
    parts.append(_section("📷  相机信息",   cam_rows))
    parts.append(_section("⚙️  曝光参数",   exp_rows))
    if gps_rows:
        parts.append(_section("📍  GPS 位置", gps_rows))
    if credit_rows:
        parts.append(_section("©  著作权",   credit_rows))

    return "".join(parts)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class PropertiesDialog(QDialog):
    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"图片信息 — {path.name}")
        self.setMinimumSize(560, 540)
        self.resize(620, 660)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QDialog { background:#1a1a24; color:#d8d8ec; }"
            "QScrollArea { background:#1a1a24; border:none; }"
            "QDialogButtonBox QPushButton {"
            "  background:#2a2a3c; border:1px solid #404058; border-radius:6px;"
            "  padding:6px 20px; min-width:80px; color:#d8d8ec; }"
            "QDialogButtonBox QPushButton:hover {"
            "  background:#3d5afe; border-color:#3d5afe; color:#fff; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        browser.setStyleSheet("QTextBrowser { background:#1a1a24; color:#d8d8ec; }")
        browser.setHtml(build_html_report(path))
        layout.addWidget(browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.setContentsMargins(12, 0, 12, 0)
        layout.addWidget(buttons)
