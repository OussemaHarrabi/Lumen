"""Pretraitement : filtrage, niveaux de gris et rehaussement de contraste.

Portage des cellules de l'atelier 2 (filtre median 5 x 5, moyenneur, gaussien,
CLAHE) avec les memes parametres par defaut.
"""

from __future__ import annotations

import cv2
import numpy as np

from .io import is_color, to_color, to_gray


def _odd(ksize: int) -> int:
    """Taille de noyau impaire, au moins 1."""
    size = round(float(ksize))
    if size < 1:
        raise ValueError("La taille du noyau doit etre superieure ou egale a 1")
    if size % 2 == 0:
        size += 1
    return size


def gray(image: np.ndarray) -> tuple[np.ndarray, dict]:
    """Passage en niveaux de gris (luminance Rec. 601 d'OpenCV)."""
    result = to_gray(image)
    return result, {"channels": 1, "shape": list(result.shape)}


def median(image: np.ndarray, ksize: int = 5) -> tuple[np.ndarray, dict]:
    """Filtre median ksize x ksize, comme cv2.medianBlur de l'atelier 2."""
    size = _odd(ksize)
    source = to_color(image) if is_color(image) else to_gray(image)
    result = cv2.medianBlur(source, size)
    return result, {"ksize": size}


def gaussian(image: np.ndarray, ksize: int = 5, sigma: float = 0.0) -> tuple[np.ndarray, dict]:
    """Filtre gaussien, sigma = 0 laisse OpenCV deduire l'ecart type du noyau."""
    size = _odd(ksize)
    source = to_color(image) if is_color(image) else to_gray(image)
    result = cv2.GaussianBlur(source, (size, size), float(sigma))
    return result, {"ksize": size, "sigma": float(sigma)}


def mean(image: np.ndarray, ksize: int = 5) -> tuple[np.ndarray, dict]:
    """Filtre moyenneur ksize x ksize."""
    size = _odd(ksize)
    source = to_color(image) if is_color(image) else to_gray(image)
    result = cv2.blur(source, (size, size))
    return result, {"ksize": size}


def clahe(image: np.ndarray, clip: float = 2.0, grid: int = 8) -> tuple[np.ndarray, dict]:
    """Egalisation adaptative du contraste (CLAHE).

    Sur une image couleur, seul le canal de luminance L est rehausse, puis
    l'image est reconvertie en RGB.
    """
    clip_limit = float(np.clip(clip, 1.0, 8.0))
    tiles = int(np.clip(grid, 2, 16))
    operator = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tiles, tiles))
    if is_color(image):
        rgb = to_color(image)
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        lab[:, :, 0] = operator.apply(lab[:, :, 0])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    else:
        result = operator.apply(to_gray(image))
    return result, {"clip": clip_limit, "grid": tiles}
