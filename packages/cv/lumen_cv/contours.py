"""Cartes de contours : Sobel, Laplacien et gradient morphologique.

Reprise de l'atelier 2. Les deux operateurs differentiels renvoient une carte de
reponse flottante brute, le gradient morphologique une carte uint8.
"""

from __future__ import annotations

import cv2
import numpy as np

from .io import to_gray


def sobel(image: np.ndarray) -> tuple[np.ndarray, dict]:
    """Magnitude du gradient de Sobel 3 x 3, en float32."""
    gray = to_gray(image)
    gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(gradient_x ** 2 + gradient_y ** 2).astype(np.float32)
    return magnitude, {"min": float(magnitude.min()), "max": float(magnitude.max())}


def laplace(image: np.ndarray) -> tuple[np.ndarray, dict]:
    """Valeur absolue du Laplacien, en float32."""
    gray = to_gray(image)
    response = np.abs(cv2.Laplacian(gray, cv2.CV_64F)).astype(np.float32)
    return response, {"min": float(response.min()), "max": float(response.max())}


def morph_gradient(image: np.ndarray, ksize: int = 3) -> tuple[np.ndarray, dict]:
    """Gradient morphologique : dilatation moins erosion, en uint8."""
    size = int(ksize)
    if size < 1:
        raise ValueError("La taille du noyau doit etre superieure ou egale a 1")
    if size % 2 == 0:
        size += 1
    gray = to_gray(image)
    gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((size, size), np.uint8))
    return gradient, {"ksize": size, "min": int(gradient.min()), "max": int(gradient.max())}
