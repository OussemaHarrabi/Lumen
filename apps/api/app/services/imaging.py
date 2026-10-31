"""Lecture, metadonnees et rendus PNG des images (cote API uniquement)."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from app.errors import ApiError

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

ALLOWED_TYPES = {
    "png": (".png", "image/png"),
    "jpeg": (".jpg", "image/jpeg"),
    "tiff": (".tif", "image/tiff"),
    "bmp": (".bmp", "image/bmp"),
}

OVERLAY_COLOR = np.array([210, 84, 74], dtype=np.float64)
EDGE_COLOR = np.array([250, 249, 245], dtype=np.uint8)


@dataclass
class ImageInfo:
    extension: str
    mime: str
    width: int
    height: int
    channels: int
    dtype: str
    min_value: float
    max_value: float
    mean: float
    mask_fraction: float | None


def sniff_type(data: bytes) -> str | None:
    """Detecte le format reel par l'entete du fichier."""
    if data.startswith(PNG_MAGIC):
        return "png"
    if data.startswith(JPEG_MAGIC):
        return "jpeg"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    if data.startswith(b"BM"):
        return "bmp"
    return None


def _pil_from(data: bytes | Path) -> Image.Image:
    source: BytesIO | Path = BytesIO(data) if isinstance(data, bytes) else data
    try:
        image = Image.open(source)
        image.load()
        return image
    except Exception as exc:  # image illisible ou tronquee
        raise ApiError("unsupported_type", "Le fichier n'est pas une image lisible.", {"detail": str(exc)}) from exc


def _depth_mode(mode: str) -> int:
    if mode in {"1", "L", "I", "F", "I;16", "I;16B", "I;16L", "I;16N"}:
        return 1
    if mode in {"LA", "La"}:
        return 2
    if mode in {"RGB", "YCbCr", "HSV"}:
        return 3
    if mode in {"RGBA", "RGBX", "CMYK"}:
        return 4
    return 3


def _to_uint8_array(image: Image.Image) -> np.ndarray:
    """Ramene n'importe quel mode en RGB uint8 (alpha aplati sur blanc)."""
    mode = image.mode
    if mode.startswith("I;16") or mode == "I":
        arr = np.asarray(image).astype(np.float64)
        arr = np.clip(arr / 257.0, 0, 255).astype(np.uint8)
        return np.stack([arr] * 3, axis=-1)
    if mode == "F":
        arr = np.asarray(image, dtype=np.float64)
        peak = float(np.nanmax(arr)) or 1.0
        arr = np.clip(arr / peak * 255.0, 0, 255).astype(np.uint8)
        return np.stack([arr] * 3, axis=-1)
    if mode == "1":
        arr = (np.asarray(image, dtype=bool).astype(np.uint8)) * 255
        return np.stack([arr] * 3, axis=-1)
    if mode in {"L", "LA", "La"}:
        gray = np.asarray(image.convert("L"), dtype=np.uint8)
        return np.stack([gray] * 3, axis=-1)
    if mode == "RGBA":
        rgba = np.asarray(image, dtype=np.uint8).astype(np.float64)
        alpha = rgba[..., 3:4] / 255.0
        rgb = rgba[..., :3] * alpha + 255.0 * (1.0 - alpha)
        return np.clip(rgb, 0, 255).astype(np.uint8)
    if mode == "P":
        return np.asarray(image.convert("RGB"), dtype=np.uint8)
    if mode in {"RGB", "YCbCr", "HSV", "CMYK", "LAB"}:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)
    return np.asarray(image.convert("RGB"), dtype=np.uint8)


def load_rgb(data: bytes | Path) -> tuple[np.ndarray, Image.Image]:
    image = _pil_from(data)
    return _to_uint8_array(image), image


def load_rgb_file(path: Path) -> np.ndarray:
    if not path.is_file():
        raise ApiError("asset_not_found", "Le fichier de l'image est introuvable.", {"path": str(path)})
    array, _ = load_rgb(path)
    return array


def _bounded(array: np.ndarray, max_dimension: int) -> None:
    height, width = array.shape[:2]
    if max(height, width) > max_dimension:
        raise ApiError(
            "asset_too_large",
            f"Les dimensions dépassent {max_dimension} pixels de côté.",
            {"width": width, "height": height},
        )
    if height < 2 or width < 2:
        raise ApiError("unsupported_type", "L'image est trop petite pour être traitée.", {"width": width, "height": height})


def inspect(data: bytes, kind: str, max_dimension: int) -> ImageInfo:
    """Verifie le type reel et calcule les metadonnees."""
    detected = sniff_type(data)
    if detected is None:
        raise ApiError(
            "unsupported_type",
            "Format non pris en charge. Types acceptés : PNG, JPEG, TIFF, BMP.",
            {"bytes": len(data)},
        )
    array, image = load_rgb(data)
    _bounded(array, max_dimension)

    height, width = array.shape[:2]
    channels = _depth_mode(image.mode)
    dtype = "uint8"
    values = array.astype(np.float64)
    gray = array.max(axis=2).astype(np.float64)

    mask_fraction: float | None = None
    if kind == "mask":
        mask_fraction = float((gray > 127).mean())
        flat = gray
    else:
        flat = values

    extension, mime = ALLOWED_TYPES[detected]
    return ImageInfo(
        extension=extension,
        mime=mime,
        width=width,
        height=height,
        channels=channels,
        dtype=dtype,
        min_value=float(flat.min()),
        max_value=float(flat.max()),
        mean=float(flat.mean()),
        mask_fraction=mask_fraction,
    )


def normalize_mask(mask: np.ndarray) -> np.ndarray:
    """Ramene un masque en uint8 0/1 quelle que soit la convention d'entree."""
    array = np.asarray(mask)
    if array.dtype == bool:
        return array.astype(np.uint8)
    values = array.astype(np.float64)
    peak = float(values.max()) if values.size else 0.0
    if peak > 1.0:
        return (values > 127).astype(np.uint8)
    return (values > 0.5).astype(np.uint8)


def save_mask(mask: np.ndarray, path: Path) -> None:
    binary = normalize_mask(mask)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(binary * 255, mode="L").save(path, format="PNG")


def _outline(mask: np.ndarray) -> np.ndarray:
    binary = normalize_mask(mask) * 255
    eroded = np.asarray(Image.fromarray(binary, mode="L").filter(ImageFilter.MinFilter(3)))
    return (binary > 0) & (eroded == 0)


def save_overlay(image_rgb: np.ndarray, mask: np.ndarray, path: Path) -> None:
    """Superpose le masque en teinte et son contour sur l'image d'origine."""
    binary = normalize_mask(mask)
    if binary.shape != image_rgb.shape[:2]:
        binary = np.asarray(
            Image.fromarray(binary * 255, mode="L").resize(
                (image_rgb.shape[1], image_rgb.shape[0]), Image.Resampling.NEAREST
            )
        )
        binary = (binary > 127).astype(np.uint8)
    selected = binary.astype(bool)
    canvas = image_rgb.astype(np.float64).copy()
    if selected.any():
        canvas[selected] = 0.55 * canvas[selected] + 0.45 * OVERLAY_COLOR
    edge = _outline(binary)
    canvas[edge] = EDGE_COLOR
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), mode="RGB").save(path, format="PNG")


def checkerboard(first: np.ndarray, second: np.ndarray, blocks: int = 10) -> np.ndarray:
    """Damier alternant deux images de meme taille."""
    height = min(first.shape[0], second.shape[0])
    width = min(first.shape[1], second.shape[1])
    left = first[:height, :width]
    right = second[:height, :width]
    block = max(8, min(height, width) // max(blocks, 2))
    rows = np.arange(height)[:, None] // block
    cols = np.arange(width)[None, :] // block
    pattern = ((rows + cols) % 2 == 0)[..., None]
    return np.where(pattern, left, right)


def blend(first: np.ndarray, second: np.ndarray, weight: float = 0.5) -> np.ndarray:
    """Melange deux images pour la vue de superposition."""
    height = min(first.shape[0], second.shape[0])
    width = min(first.shape[1], second.shape[1])
    mixed = weight * first[:height, :width].astype(np.float64) + (1.0 - weight) * second[:height, :width]
    return np.clip(mixed, 0, 255).astype(np.uint8)


def save_rgb(array: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), mode="RGB").save(path, format="PNG")


def resize_mask(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    binary = normalize_mask(mask)
    if binary.shape == shape:
        return binary
    resized = np.asarray(
        Image.fromarray(binary * 255, mode="L").resize((shape[1], shape[0]), Image.Resampling.NEAREST)
    )
    return (resized > 127).astype(np.uint8)
