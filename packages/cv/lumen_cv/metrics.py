"""Mesures de qualite d'un masque : Dice, IoU, rappel et precision.

Les formules sont celles de l'atelier 3, ecrites explicitement dans le notebook.
Les masques peuvent etre booleens, 0/1 ou 0/255.
"""

from __future__ import annotations

import numpy as np

from .io import to_mask


def _pair(pred: np.ndarray, ref: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = to_mask(pred).astype(bool)
    b = to_mask(ref).astype(bool)
    if a.shape != b.shape:
        raise ValueError(f"Formes incompatibles : {a.shape} et {b.shape}")
    return a, b


def _ratio(numerator: float, denominator: float) -> float:
    """Rapport, avec le cas vide traite de facon symetrique."""
    if denominator == 0:
        return 1.0 if numerator == 0 else 0.0
    return float(numerator / denominator)


def dice(pred: np.ndarray, ref: np.ndarray) -> float:
    """Dice : 2 x intersection / (pixels de A + pixels de B)."""
    a, b = _pair(pred, ref)
    return _ratio(2.0 * float(np.logical_and(a, b).sum()), float(a.sum() + b.sum()))


def iou(pred: np.ndarray, ref: np.ndarray) -> float:
    """IoU (Jaccard) : intersection / union."""
    a, b = _pair(pred, ref)
    union = float(np.logical_or(a, b).sum())
    return _ratio(float(np.logical_and(a, b).sum()), union)


def recall(pred: np.ndarray, ref: np.ndarray) -> float:
    """Rappel : part de la reference retrouvee par la prediction."""
    a, b = _pair(pred, ref)
    return _ratio(float(np.logical_and(a, b).sum()), float(b.sum()))


def precision(pred: np.ndarray, ref: np.ndarray) -> float:
    """Precision : part des pixels predits qui appartiennent a la reference."""
    a, b = _pair(pred, ref)
    return _ratio(float(np.logical_and(a, b).sum()), float(a.sum()))


def evaluate(pred: np.ndarray, ref: np.ndarray) -> dict[str, float]:
    """Les quatre mesures en un dictionnaire, dans l'ordre du contrat."""
    return {
        "dice": dice(pred, ref),
        "iou": iou(pred, ref),
        "recall": recall(pred, ref),
        "precision": precision(pred, ref),
    }
