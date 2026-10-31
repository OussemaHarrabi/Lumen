"""Valeurs de reference des mesures de l'atelier 3."""

from __future__ import annotations

import numpy as np
import pytest

from lumen_cv import metrics


def _squares() -> tuple[np.ndarray, np.ndarray]:
    """Deux carres de 5 x 5 qui se recouvrent sur 3 x 3 pixels."""
    a = np.zeros((10, 10), bool)
    b = np.zeros((10, 10), bool)
    a[2:7, 2:7] = True
    b[4:9, 4:9] = True
    return a, b


def test_squares_reference_values() -> None:
    a, b = _squares()
    assert metrics.dice(a, b) == pytest.approx(18 / 50, abs=1e-12)
    assert metrics.iou(a, b) == pytest.approx(9 / 41, abs=1e-12)
    assert metrics.recall(a, b) == pytest.approx(9 / 25, abs=1e-12)
    assert metrics.precision(a, b) == pytest.approx(9 / 25, abs=1e-12)


def test_iou_follows_dice_formula() -> None:
    """IoU = Dice / (2 - Dice) : relation exacte rappelee dans le compte rendu."""
    rng = np.random.default_rng(7)
    for _ in range(8):
        pred = rng.random((32, 32)) > 0.6
        ref = rng.random((32, 32)) > 0.55
        dice = metrics.dice(pred, ref)
        expected = dice / (2.0 - dice)
        assert metrics.iou(pred, ref) == pytest.approx(expected, abs=1e-12)


def test_accepts_boolean_and_uint8_masks() -> None:
    a = np.zeros((6, 6), np.uint8)
    a[1:4, 1:4] = 255
    b = np.zeros((6, 6), bool)
    b[1:4, 1:4] = True
    assert metrics.dice(a, b) == 1.0
    assert metrics.iou(a, b) == 1.0


def test_empty_masks_are_consistent() -> None:
    empty = np.zeros((8, 8), np.uint8)
    full = np.ones((8, 8), np.uint8)
    assert metrics.dice(empty, empty) == 1.0
    assert metrics.iou(empty, empty) == 1.0
    assert metrics.dice(empty, full) == 0.0
    assert metrics.iou(empty, full) == 0.0
    assert metrics.recall(empty, full) == 0.0
    assert metrics.precision(full, empty) == 0.0


def test_evaluate_returns_the_four_measures() -> None:
    a, b = _squares()
    result = metrics.evaluate(a, b)
    assert set(result) == {"dice", "iou", "recall", "precision"}
    assert all(isinstance(value, float) for value in result.values())
    assert result["dice"] == pytest.approx(0.36)
