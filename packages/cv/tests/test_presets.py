"""Presets de la plateforme : chaque chaine reproduit le Dice mesure au TP."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lumen_cv import io, metrics, pipeline
from lumen_cv.registry import presets

REQUIRED_KEYS = {
    "id",
    "label_fr",
    "label_en",
    "description_fr",
    "description_en",
    "asset_hint",
    "steps",
    "expected",
}


def test_presets_are_complete() -> None:
    catalogue = presets()
    assert [preset["id"] for preset in catalogue] == [
        "otsu", "kmeans", "watershed", "chan-vese", "unet",
    ]
    for preset in catalogue:
        assert set(preset) == REQUIRED_KEYS
        assert preset["label_fr"] and preset["label_en"]
        assert preset["description_fr"] and preset["description_en"]
        assert preset["asset_hint"] in {"endoscopie-cours", "endoscopie-unet"}
        assert set(preset["expected"]) == {"dice", "iou"}
        assert preset["steps"]
        assert all({"kind", "params"} <= set(step) for step in preset["steps"])


def test_presets_return_independent_copies() -> None:
    catalogue = presets()
    catalogue[0]["steps"].clear()
    catalogue[0]["expected"]["dice"] = 0.0
    fresh = presets()
    assert len(fresh[0]["steps"]) == 4
    assert fresh[0]["expected"]["dice"] == pytest.approx(0.086)


def test_presets_cover_both_assets() -> None:
    hints = {preset["asset_hint"] for preset in presets()}
    assert hints == {"endoscopie-cours", "endoscopie-unet"}
    assert sum(preset["asset_hint"] == "endoscopie-unet" for preset in presets()) == 1


def test_presets_reproduce_expected_scores(
    frame442: np.ndarray, glottis: np.ndarray, data_dir: Path
) -> None:
    """Chaque preset est execute et compare a son Dice et son IoU attendus (tolerance 0,05)."""
    endoscopy = io.read_image(data_dir / "endoscopy_rgb.png")
    endoscopy_truth = io.to_gray(io.read_image(data_dir / "endoscopy_mask.png")) > 127
    assets = {
        "endoscopie-cours": (frame442, glottis),
        "endoscopie-unet": (endoscopy, endoscopy_truth),
    }

    for preset in presets():
        image, reference = assets[preset["asset_hint"]]
        result = pipeline.run_pipeline(image, preset["steps"])
        assert result.mask is not None, preset["id"]
        scores = metrics.evaluate(result.mask, reference)
        expected = preset["expected"]
        assert abs(scores["dice"] - expected["dice"]) <= 0.05, (preset["id"], scores, expected)
        assert abs(scores["iou"] - expected["iou"]) <= 0.05, (preset["id"], scores, expected)
        assert result.total_ms >= 0.0
