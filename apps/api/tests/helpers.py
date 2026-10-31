"""Outils partages par les tests (module a plat: le nom `tests` est trop courant)."""

from __future__ import annotations

import time
from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services import cv_bridge


def png_bytes(width: int = 64, height: int = 48, seed: int = 1) -> bytes:
    rng = np.random.default_rng(seed)
    array = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    buffer = BytesIO()
    Image.fromarray(array, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def mask_bytes(width: int = 64, height: int = 48) -> bytes:
    array = np.zeros((height, width), dtype=np.uint8)
    array[height // 4 : height // 2, width // 4 : width // 2] = 255
    buffer = BytesIO()
    Image.fromarray(array, mode="L").save(buffer, format="PNG")
    return buffer.getvalue()


def upload(client: TestClient, data: bytes, kind: str = "image", name: str = "image.png") -> dict:
    response = client.post("/api/assets", files={"file": (name, data, "image/png")}, data={"kind": kind})
    assert response.status_code == 201, response.text
    return response.json()


def copy_demo(client: TestClient, slug: str, part: str | None = None) -> dict:
    url = f"/api/demos/{slug}/asset"
    if part:
        url = f"{url}?part={part}"
    response = client.post(url)
    assert response.status_code == 201, response.text
    return response.json()


def wait_for_job(client: TestClient, job_id: str, timeout: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/analyses/{job_id}")
        if response.status_code == 404:
            response = client.get(f"/api/registrations/{job_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        if body["status"] in {"done", "error"}:
            return body
        time.sleep(0.1)
    raise AssertionError(f"La tache {job_id} n'a pas terminé dans {timeout} s")


def has_cv() -> bool:
    return cv_bridge.available()


requires_cv = pytest.mark.skipif(not has_cv(), reason="lumen_cv indisponible dans cet environnement")
