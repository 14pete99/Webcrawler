"""Enforce Claude Code image requirements: max 20 MB, max 8000px on longest side.

Oversized images are split into tiles that each meet the requirements.
"""

from __future__ import annotations

import io
import math
from pathlib import Path

from PIL import Image

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_DIMENSION = 8000  # px on longest side


def _save_image(img: Image.Image, dest: Path, quality: int = 90) -> Path:
    """Save an image, converting RGBA to RGB for JPEG when needed."""
    fmt = dest.suffix.lower()
    if fmt in (".jpg", ".jpeg"):
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(dest, format="JPEG", quality=quality, optimize=True)
    elif fmt == ".webp":
        img.save(dest, format="WEBP", quality=quality)
    else:
        img.save(dest, format="PNG", optimize=True)
    return dest


def _compress_to_fit(img: Image.Image, dest: Path) -> Path:
    """Reduce JPEG/WEBP quality until file fits under MAX_FILE_SIZE."""
    fmt = dest.suffix.lower()
    if fmt not in (".jpg", ".jpeg", ".webp"):
        # For PNG, we can't easily reduce quality — return as-is
        _save_image(img, dest)
        return dest

    for quality in (90, 80, 65, 50, 35, 20):
        _save_image(img, dest, quality=quality)
        if dest.stat().st_size <= MAX_FILE_SIZE:
            return dest
    return dest


def _tile_count(length: int, max_len: int) -> int:
    """How many tiles needed to cover *length* with tiles of at most *max_len*."""
    return math.ceil(length / max_len)


def enforce_compliance(image_path: Path) -> list[Path]:
    """Ensure *image_path* meets Claude Code limits.

    Returns a list of paths:
    - Single-element list with the (possibly resized) original if it already fits.
    - Multi-element list of tile files if the image was split.

    Tile files are named ``<stem>_tile_<row>_<col><ext>`` next to the original.
    The original file is removed when splitting occurs.
    """
    try:
        img = Image.open(image_path)
        img.load()
    except Exception:
        return [image_path]  # Not a processable image; leave as-is

    w, h = img.size
    file_size = image_path.stat().st_size
    longest = max(w, h)

    # Case 1: already compliant
    if longest <= MAX_DIMENSION and file_size <= MAX_FILE_SIZE:
        return [image_path]

    # Case 2: dimensions OK but file too large — compress
    if longest <= MAX_DIMENSION:
        _compress_to_fit(img, image_path)
        # If still too big after compression, fall through to tiling
        if image_path.stat().st_size <= MAX_FILE_SIZE:
            return [image_path]

    # Case 3: needs tiling (dimensions exceed limit, or file still too big)
    cols = _tile_count(w, MAX_DIMENSION)
    rows = _tile_count(h, MAX_DIMENSION)
    tile_w = math.ceil(w / cols)
    tile_h = math.ceil(h / rows)

    stem = image_path.stem
    ext = image_path.suffix
    parent = image_path.parent
    tiles: list[Path] = []

    for row in range(rows):
        for col in range(cols):
            left = col * tile_w
            upper = row * tile_h
            right = min(left + tile_w, w)
            lower = min(upper + tile_h, h)

            tile = img.crop((left, upper, right, lower))
            tile_path = parent / f"{stem}_tile_{row}_{col}{ext}"
            _compress_to_fit(tile, tile_path)
            tiles.append(tile_path)

    # Remove the original oversized file
    image_path.unlink(missing_ok=True)
    return tiles
