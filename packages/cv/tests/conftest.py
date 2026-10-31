"""Fixtures partagees : images d'exemple reduites du dossier data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lumen_cv import io

DATA = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    assert DATA.is_dir(), f"Dossier de donnees absent : {DATA}"
    return DATA


@pytest.fixture(scope="session")
def frame442(data_dir: Path) -> np.ndarray:
    return io.read_image(data_dir / "frame442.png")


@pytest.fixture(scope="session")
def glottis(data_dir: Path) -> np.ndarray:
    return (io.read_image(data_dir / "frame442_glottis.png")[:, :, 0] > 127).astype(np.uint8)


@pytest.fixture(scope="session")
def sequence(data_dir: Path) -> list[np.ndarray]:
    files = sorted((data_dir / "sequence").glob("frame_*.png"))
    assert len(files) == 100, f"100 images attendues, {len(files)} trouvees"
    return [io.read_gray(path) for path in files]


@pytest.fixture(scope="session")
def fire_pair(data_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    folder = data_dir / "fire"
    fixed = io.read_image(folder / "S01_1.jpg")
    moving = io.read_image(folder / "S01_2.jpg")
    points = np.loadtxt(folder / "S01_points.txt")
    return fixed, moving, points


@pytest.fixture(scope="session")
def kmeans_labels(frame442: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    from lumen_cv import segment

    return segment._kmeans_labels(frame442, 3, 42)
