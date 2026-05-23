"""Supported image and RAW extensions."""

COMMON_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".jpe",
        ".jfif",
        ".png",
        ".gif",
        ".bmp",
        ".dib",
        ".webp",
        ".tif",
        ".tiff",
        ".ico",
        ".cur",
        ".ppm",
        ".pgm",
        ".pbm",
        ".pnm",
        ".jp2",
        ".j2k",
        ".jpf",
        ".jpx",
        ".jpm",
        ".mj2",
        ".heic",
        ".heif",
        ".avif",
        ".svg",
        ".psd",
        ".xcf",
    }
)

# LibRaw / rawpy — Nikon, Sony, Canon, DJI (DNG), Fuji, Olympus, Panasonic, etc.
RAW_EXTENSIONS = frozenset(
    {
        ".raw",
        ".dng",  # Adobe / DJI / many phones
        ".nef",
        ".nrw",  # Nikon
        ".arw",
        ".srf",
        ".sr2",  # Sony
        ".cr2",
        ".cr3",
        ".crw",  # Canon
        ".raf",  # Fuji
        ".orf",  # Olympus
        ".rw2",  # Panasonic
        ".pef",
        ".ptx",  # Pentax
        ".srw",  # Samsung
        ".x3f",  # Sigma
        ".3fr",
        ".fff",  # Hasselblad / Leaf
        ".iiq",  # Phase One
        ".kdc",
        ".dcr",
        ".drf",  # Kodak
        ".mos",
        ".mrw",  # Minolta
        ".rwl",  # Leica
        ".erf",  # Epson
        ".mef",  # Mamiya
        ".mdc",  # Minolta
        ".bay",  # Casio
        ".cap",
        ".iiq",
        ".eip",
    }
)

ALL_EXTENSIONS = COMMON_EXTENSIONS | RAW_EXTENSIONS


def is_image_path(path) -> bool:
    return path.suffix.lower() in ALL_EXTENSIONS


def is_raw_path(path) -> bool:
    return path.suffix.lower() in RAW_EXTENSIONS
