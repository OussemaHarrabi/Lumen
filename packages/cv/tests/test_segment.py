"""Segmentation de frame442.png : valeurs de reference de l'atelier 3.

L'image de reference et son masque du glottis viennent du cours. Les valeurs
attendues sont celles du notebook complete (Dice 0.461 pour k-means, 0.484 pour
Chan-Vese recadre) ; les tolerances couvrent les differences de version entre
scikit-learn et scikit-image.
"""

from __future__ import annotations

from time import perf_counter

import numpy as np
import pytest

from lumen_cv import metrics, segment


def test_field_of_view_matches_notebook(frame442: np.ndarray) -> None:
    """Le champ de vision du notebook fait 202 022 pixels, soit 65,8 % de l'image."""
    fov = segment.field_of_view(frame442)
    pixels = int(fov.sum())
    assert fov.shape == frame442.shape[:2]
    assert 195_000 <= pixels <= 208_000, pixels
    assert 0.62 <= pixels / frame442.shape[0] / frame442.shape[1] <= 0.68


def test_kmeans_dice_reference(frame442: np.ndarray, glottis: np.ndarray) -> None:
    start = perf_counter()
    mask, diagnostics = segment.kmeans(frame442)
    elapsed = perf_counter() - start

    assert elapsed < 90.0, elapsed
    assert mask.dtype == np.uint8
    assert set(np.unique(mask)) <= {0, 1}
    assert 18_000 <= int(mask.sum()) <= 19_200
    assert metrics.dice(mask, glottis) == pytest.approx(0.461, abs=0.02)
    assert metrics.iou(mask, glottis) == pytest.approx(0.300, abs=0.02)
    assert diagnostics["darkest_class"] == 2
    assert diagnostics["classes"] == [0, 1, 2]
    assert 32.0 <= diagnostics["class_levels"][2] <= 33.5


def test_otsu_threshold_is_plausible(frame442: np.ndarray, glottis: np.ndarray) -> None:
    """Otsu separe les tissus brillants du fond sombre : seuil proche de 116."""
    bright, diagnostics = segment.otsu(frame442)
    dark, _ = segment.otsu(frame442, invert=True)

    assert 100.0 <= diagnostics["threshold"] <= 135.0
    assert diagnostics["mask_pixels"] > 50_000
    assert metrics.dice(bright, glottis) < 0.01
    assert metrics.recall(dark, glottis) > 0.99


def test_chan_vese_cropped_dice_reference(frame442: np.ndarray, glottis: np.ndarray) -> None:
    mask, diagnostics = segment.chan_vese(frame442)
    assert metrics.dice(mask, glottis) == pytest.approx(0.484, abs=0.03)
    assert metrics.iou(mask, glottis) == pytest.approx(0.319, abs=0.03)
    assert diagnostics["crop"] is True
    assert diagnostics["window"][1] - diagnostics["window"][0] <= 240
    assert abs(diagnostics["center"][0] - 188) <= 4
    assert abs(diagnostics["center"][1] - 312) <= 4


def test_chan_vese_full_image_is_worse(frame442: np.ndarray, glottis: np.ndarray) -> None:
    """Sans recadrage, la methode separe le fond noir des tissus (Dice 0.088)."""
    full, diagnostics = segment.chan_vese(frame442, crop=False)
    assert diagnostics["crop"] is False
    assert metrics.dice(full, glottis) < 0.25


def test_watershed_returns_plausible_mask(frame442: np.ndarray, glottis: np.ndarray) -> None:
    mask, diagnostics = segment.watershed(frame442)
    fraction = float(mask.mean())
    assert 0.03 <= fraction <= 0.15, fraction
    assert metrics.dice(mask, glottis) > 0.60
    assert diagnostics["foreground_pixels"] > 0
    assert diagnostics["marker_ratio"] == pytest.approx(0.5)
    gray_mask, _ = segment.watershed(segment.to_gray(frame442))
    assert np.array_equal(mask, gray_mask)


def test_watershed_pipeline_default_locks_dice_above_080(
    frame442: np.ndarray, glottis: np.ndarray
) -> None:
    """Preset watershed : gray, watershed par defaut, ouverture, plus grande composante."""
    from lumen_cv import pipeline

    result = pipeline.run_pipeline(
        frame442,
        [
            {"kind": "preprocess.gray", "params": {}},
            {"kind": "segment.watershed", "params": {}},
            {"kind": "postprocess.open", "params": {"ksize": 3}},
            {"kind": "postprocess.largest_component", "params": {}},
        ],
    )
    assert result.steps[1].params == {"marker_ratio": 0.5}
    assert metrics.dice(result.mask, glottis) > 0.80
    assert 5_000 <= int(result.mask.sum()) <= 20_000


def test_meanshift_runs_under_two_minutes(frame442: np.ndarray, glottis: np.ndarray) -> None:
    """MeanShift sur l'image entiere avec un pixel sur 9 : 52 s mesurees, 3 regions."""
    start = perf_counter()
    mask, diagnostics = segment.meanshift(frame442, subsample=3)
    elapsed = perf_counter() - start

    assert elapsed < 120.0, elapsed
    assert diagnostics["regions"] == 3
    assert diagnostics["sample_pixels"] == 34_240
    assert int(mask.sum()) == 16_966
    assert metrics.dice(mask, glottis) == pytest.approx(0.461, abs=0.02)


def test_darkest_mask_without_field_of_view_collapses(
    frame442: np.ndarray, glottis: np.ndarray, kmeans_labels: tuple[np.ndarray, np.ndarray]
) -> None:
    """Sans restriction au champ de vision, la classe sombre est le fond (Dice 0.09)."""
    labels, _ = kmeans_labels
    naive, _ = segment.darkest_mask(labels, frame442)
    restricted, _ = segment.darkest_mask(labels, frame442, segment.field_of_view(frame442))
    assert metrics.dice(naive, glottis) < 0.2
    assert metrics.dice(restricted, glottis) > 0.4
