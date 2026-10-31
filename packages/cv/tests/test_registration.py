"""Recalage : translation, mesures de similarite, sequence et retines FIRE."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import find_peaks

from lumen_cv import registration

SCALE_FIRE = 0.5


def _first_peak(values: np.ndarray, inverse: bool = False) -> tuple[int, list[int]]:
    """Premier pic de la courbe, numerote comme dans le notebook (image i = indice + 2)."""
    curve = -values if inverse else values
    peaks, _ = find_peaks(curve, distance=8, prominence=0.25 * np.std(curve))
    indices = [int(peak) + 1 for peak in peaks]
    return indices[0], indices


def test_translation_recovers_a_known_shift() -> None:
    rng = np.random.default_rng(3)
    base = rng.integers(0, 255, (160, 200), dtype=np.uint8).astype(np.float32)
    shift = (7, -5)
    moving = np.roll(np.roll(base, shift[0], axis=0), shift[1], axis=1)

    transform, score = registration.estimate_translation(base, moving)
    assert transform.shape == (3, 3)
    assert transform[0, 2] == pytest.approx(-shift[1], abs=0.5)
    assert transform[1, 2] == pytest.approx(-shift[0], abs=0.5)
    assert score > 0.85

    warped = registration.apply_transform(moving, transform, base.shape)
    overlap = (slice(0, 160 - shift[0]), slice(-shift[1], 200))
    assert registration.ncc(base[overlap], warped[overlap]) > 0.999

    point = np.array([[50.0, 60.0, 45.0, 67.0]])
    assert registration.landmark_error(transform, point)["mean"] < 0.1


def test_warp_points_and_apply_transform_agree() -> None:
    transform = np.array([[1.0, 0.0, 12.0], [0.0, 1.0, -4.0], [0.0, 0.0, 1.0]])
    points = np.array([[10.0, 20.0], [30.0, 40.0]])
    moved = registration.warp_points(transform, points)
    assert moved == pytest.approx(np.array([[22.0, 16.0], [42.0, 36.0]]))

    image = np.zeros((50, 50), np.uint8)
    image[20, 10] = 255
    warped = registration.apply_transform(image, transform, (50, 50))
    assert warped[16, 22] == 255


def test_similarity_measures_on_identical_and_noise() -> None:
    rng = np.random.default_rng(11)
    image = rng.integers(0, 255, (64, 64), dtype=np.uint8)
    noise = rng.integers(0, 255, (64, 64), dtype=np.uint8)

    assert registration.ncc(image, image) == pytest.approx(1.0)
    assert registration.mse(image, image) == 0.0
    assert registration.nmi(image, image) == pytest.approx(1.0)

    assert registration.ncc(image, noise) < 0.2
    assert registration.mse(image, noise) > 1000.0
    assert registration.nmi(image, noise) < 0.5


def test_sequence_detects_the_cycle_restart(sequence: list[np.ndarray]) -> None:
    """Sur 100 images, les trois mesures repointent l'image 14 (cycle de 15 images)."""
    reference = sequence[0]
    correlations = np.array([registration.ncc(reference, image) for image in sequence[1:]])
    errors = np.array([registration.mse(reference, image) for image in sequence[1:]])
    mutual = np.array([registration.nmi(reference, image) for image in sequence[1:]])

    index_ncc, peaks_ncc = _first_peak(correlations)
    index_mse, peaks_mse = _first_peak(errors, inverse=True)
    index_nmi, peaks_nmi = _first_peak(mutual)

    assert index_ncc == 13, peaks_ncc
    assert index_mse == 13, peaks_mse
    assert index_nmi == 13, peaks_nmi
    assert peaks_ncc[:3] == [13, 27, 40]
    assert np.mean(np.diff(peaks_ncc)) == pytest.approx(13.3, abs=0.5)


def test_fire_homography_landmark_error(
    fire_pair: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    fixed, moving, points = fire_pair

    result = registration.register(fixed, moving, method="homography")
    assert result.transform.shape == (3, 3)
    assert result.success is True
    assert result.inliers >= 10
    assert result.warped.shape == fixed.shape

    errors = registration.landmark_error(result.transform, points)
    assert errors["mean"] * (1.0 / SCALE_FIRE) < 10.0
    assert errors["success_rate"] == 1.0
    assert len(errors["per_point"]) == points.shape[0]

    unwarped = registration.landmark_error(np.eye(3), points)
    assert unwarped["mean"] > errors["mean"]


def test_registration_metrics_are_reported(
    fire_pair: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    fixed, moving, _ = fire_pair
    result = registration.register(fixed, moving, method="affine")
    assert set(result.metrics) == {"ncc", "mse", "nmi"}
    assert 0.0 < result.metrics["ncc"] <= 1.0
    assert result.metrics["mse"] > 0.0
    assert 0.0 < result.metrics["nmi"] <= 1.0
    assert result.method == "affine"
    assert result.matches > result.inliers >= 10


def test_optical_flow_returns_a_dense_field(fire_pair: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
    fixed, moving, _ = fire_pair
    result = registration.register(fixed, moving, method="optical_flow")
    assert result.flow is not None
    assert result.flow.shape == (fixed.shape[0] // 4, fixed.shape[1] // 4, 2)
    assert result.transform.shape == (3, 3)
    assert np.isfinite(result.flow).all()
    assert np.isfinite(result.transform).all()
    assert 0.0 <= result.confidence <= 1.0


def test_optical_flow_landmark_error_stays_under_ten_pixels(
    fire_pair: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    """La transformation globale deduite du champ de flot ramene les landmarks sous 10 px."""
    fixed, moving, points = fire_pair
    result = registration.register(fixed, moving, method="optical_flow")

    errors = registration.landmark_error(result.transform, points)
    assert errors["mean"] * (1.0 / SCALE_FIRE) < 10.0
    assert result.success is True
    assert result.confidence > 0.2
    assert result.inliers > 20
    assert result.matches > result.inliers


def test_registration_confidence_is_reported(
    fire_pair: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    fixed, moving, _ = fire_pair
    for method in ("translation", "affine", "homography", "optical_flow"):
        result = registration.register(fixed, moving, method=method)
        assert 0.0 <= result.confidence <= 1.0, method
    homography = registration.register(fixed, moving, method="homography")
    assert homography.confidence == pytest.approx(homography.inliers / homography.matches, abs=1e-9)


def test_unknown_method_is_rejected(fire_pair: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
    fixed, moving, _ = fire_pair
    with pytest.raises(ValueError):
        registration.register(fixed, moving, method="magie")
