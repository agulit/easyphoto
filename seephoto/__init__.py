"""SeePhoto - portable image viewer with RAW support."""

__version__ = "1.5.0"
APP_NAME = "易图"
APP_AUTHOR = "llso"


def version_short() -> str:
    """窗口标题用短版本号，如 1.5.0 → 1.5"""
    parts = __version__.split(".")
    return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else __version__
