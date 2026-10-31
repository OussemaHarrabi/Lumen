"""Inference ONNX : disponibilite des modeles, pretraitement et Dice de reference."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lumen_cv import dl, io, metrics


def test_both_models_are_available() -> None:
    available = dl.models_available()
    assert available == {"endoscopie": True, "busi": True}
    registry = dl.ModelRegistry()
    assert registry.path("endoscopie").name == "unet_endoscopie.onnx"
    assert registry.path("busi").is_file()


def test_preprocessing_matches_the_tp4_recipe(frame442: np.ndarray) -> None:
    import cv2

    inputs = dl.preprocess_unet(frame442)
    assert inputs.shape == (1, 256, 256, 3)
    assert inputs.dtype == np.float32
    assert np.allclose(inputs[..., 0], inputs[..., 1])
    assert np.allclose(inputs[..., 1], inputs[..., 2])

    resized = cv2.resize(
        dl.to_gray(frame442), (256, 256), interpolation=cv2.INTER_LINEAR
    ).astype(np.float32)
    batch = resized[None, :, :, None]
    squared = np.sum(batch ** 2, axis=1, keepdims=True)
    expected = (batch / np.sqrt(np.maximum(squared, 1e-7)))[0, :, :, 0]
    assert np.allclose(inputs[0, :, :, 0], expected, atol=1e-6)
    column_norms = np.sqrt(np.sum(inputs[0] ** 2, axis=0))
    assert np.allclose(column_norms, 1.0, atol=1e-5)


def test_endoscopie_model_reaches_training_dice(data_dir: Path) -> None:
    image = io.read_image(data_dir / "endoscopy_rgb.png")
    reference = io.to_gray(io.read_image(data_dir / "endoscopy_mask.png")) > 127

    mask, diagnostics = dl.predict("endoscopie", image, threshold=0.5)
    assert mask.shape == image.shape[:2]
    assert set(np.unique(mask)) <= {0, 1}
    assert metrics.dice(mask, reference) > 0.85
    assert diagnostics["probability_max"] > 0.9
    assert diagnostics["mask_pixels"] > 0


def test_unknown_model_name_is_rejected(frame442: np.ndarray) -> None:
    with pytest.raises(KeyError):
        dl.predict("radiographie", frame442)


def test_missing_models_report_false(tmp_path: Path) -> None:
    registry = dl.ModelRegistry(tmp_path)
    assert registry.available() == {"endoscopie": False, "busi": False}
    with pytest.raises(dl.ModelMissingError):
        registry.predict("endoscopie", np.zeros((32, 32), np.uint8))
