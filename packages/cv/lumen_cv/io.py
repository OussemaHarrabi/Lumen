"""Lecture et ecriture d'images.

Convention du package : les images couleur sont en RGB, les images en niveaux de
gris sont des tableaux HxW. Les masques sont des tableaux HxW uint8 valant 0 ou 1.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

PathLike = str | Path


def _to_uint8(image: np.ndarray) -> np.ndarray:
    """Ramene une image quelconque en uint8 sans changer ses canaux."""
    if image.dtype == np.uint8:
        return image
    if np.issubdtype(image.dtype, np.floating):
        maximum = float(np.nanmax(image)) if image.size else 0.0
        if maximum <= 1.0:
            image = image * 255.0
        return np.clip(image, 0, 255).astype(np.uint8)
    if image.dtype == np.uint16:
        return np.clip(image / 257.0, 0, 255).astype(np.uint8)
    return np.clip(image, 0, 255).astype(np.uint8)


def _to_rgb(image: np.ndarray) -> np.ndarray:
    """Normalise une image lue par OpenCV (BGR ou BGRA) en RGB uint8 HxWx3."""
    image = _to_uint8(image)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    if image.shape[2] == 4:
        bgr = image[:, :, :3]
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
        rgb = rgb * alpha + 255.0 * (1.0 - alpha)
        return np.clip(rgb, 0, 255).astype(np.uint8)
    if image.shape[2] == 1:
        return cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def read_image(path: PathLike) -> np.ndarray:
    """Lit une image et la renvoie en RGB uint8 HxWx3.

    Accepte PNG, JPEG, TIFF et BMP. Les images 16 bits sont ramenees en 8 bits et
    la transparence est aplatie sur du blanc.
    """
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        raise ValueError(f"Fichier image vide ou introuvable : {path}")
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Format d'image non reconnu : {path}")
    return _to_rgb(image)


def read_gray(path: PathLike) -> np.ndarray:
    """Lit une image en niveaux de gris uint8."""
    return to_gray(read_image(path))


def write_image(path: PathLike, image: np.ndarray) -> None:
    """Ecrit une image RGB (ou en niveaux de gris) sur disque.

    Le format suit l'extension du chemin, PNG par defaut.
    """
    path = Path(path)
    suffix = path.suffix.lower() or ".png"
    array = np.asarray(image)
    if array.ndim == 3:
        if array.shape[2] == 4:
            encoded = array
        else:
            encoded = cv2.cvtColor(_to_uint8(array), cv2.COLOR_RGB2BGR)
    else:
        encoded = _to_uint8(array)
    ok, buffer = cv2.imencode(suffix, encoded)
    if not ok:
        raise ValueError(f"Impossible d'encoder l'image en {suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer.tofile(str(path))


def to_gray(image: np.ndarray) -> np.ndarray:
    """Image en niveaux de gris uint8 HxW, sans copie si elle l'est deja."""
    array = np.asarray(image)
    if array.ndim == 2:
        return _to_uint8(array)
    if array.shape[2] == 1:
        return _to_uint8(array[:, :, 0])
    return cv2.cvtColor(to_color(array), cv2.COLOR_RGB2GRAY)


def to_color(image: np.ndarray) -> np.ndarray:
    """Image RGB uint8 HxWx3, sans copie si elle l'est deja.

    Une image a trois canaux est consideree comme deja en RGB.
    """
    array = np.asarray(image)
    if array.ndim == 2:
        return cv2.cvtColor(_to_uint8(array), cv2.COLOR_GRAY2RGB)
    if array.shape[2] == 3:
        return _to_uint8(array)
    if array.shape[2] == 1:
        return cv2.cvtColor(_to_uint8(array[:, :, 0]), cv2.COLOR_GRAY2RGB)
    rgb = _to_uint8(array[:, :, :3])
    alpha = array[:, :, 3:4].astype(np.float32) / 255.0
    blended = rgb.astype(np.float32) * alpha + 255.0 * (1.0 - alpha)
    return np.clip(blended, 0, 255).astype(np.uint8)


def is_color(image: np.ndarray) -> bool:
    """Vrai si l'image a trois canaux de couleur."""
    array = np.asarray(image)
    return array.ndim == 3 and array.shape[2] >= 3


def to_mask(mask: np.ndarray) -> np.ndarray:
    """Normalise un masque en uint8 HxW valant 0 ou 1.

    Accepte les masques booleens, 0/1 et 0/255.
    """
    array = np.asarray(mask)
    if array.ndim == 3:
        array = array[:, :, 0]
    if array.dtype == bool:
        return array.astype(np.uint8)
    if array.size and float(array.max()) > 1.0:
        return (array > 127).astype(np.uint8)
    return (array > 0).astype(np.uint8)


def mask_to_uint8(mask: np.ndarray) -> np.ndarray:
    """Masque 0/1 vers 0/255, utile pour l'affichage et l'ecriture PNG."""
    return (to_mask(mask) * 255).astype(np.uint8)
