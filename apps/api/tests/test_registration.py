"""Recalage: metriques, images de superposition et landmarks."""

from __future__ import annotations

from fastapi.testclient import TestClient
from helpers import copy_demo, png_bytes, requires_cv, upload, wait_for_job


def _fire_pair(client: TestClient) -> tuple[dict, dict, list[list[float]]]:
    fixed = copy_demo(client, "retines-fire", "fixed")
    moving = copy_demo(client, "retines-fire", "moving")
    demo = next(item for item in client.get("/api/demos").json() if item["slug"] == "retines-fire")
    return fixed, moving, demo["landmarks"]


def test_registration_requires_images(client: TestClient) -> None:
    mask = upload(client, png_bytes(32, 32, seed=3), kind="mask")
    image = upload(client, png_bytes(32, 32, seed=4))
    response = client.post(
        "/api/registrations",
        json={"fixed_asset_id": mask["id"], "moving_asset_id": image["id"], "method": "translation"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "registration_failed"


def test_registration_rejects_unknown_method(client: TestClient) -> None:
    response = client.post(
        "/api/registrations",
        json={"fixed_asset_id": "a", "moving_asset_id": "b", "method": "magie"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "registration_failed"


@requires_cv
def test_translation_registration_on_fire_pair(client: TestClient) -> None:
    fixed, moving, landmarks = _fire_pair(client)
    response = client.post(
        "/api/registrations",
        json={
            "fixed_asset_id": fixed["id"],
            "moving_asset_id": moving["id"],
            "method": "translation",
            "params": {},
        },
    )
    assert response.status_code == 202, response.text
    registration_id = response.json()["id"]
    finished = wait_for_job(client, registration_id)
    assert finished["status"] == "done", finished
    metrics = finished["metrics"]
    assert metrics["ncc"] is not None
    if metrics.get("confidence") is not None:
        assert 0 <= metrics["confidence"] <= 1
    assert finished["transform"] and len(finished["transform"]) == 3
    assert finished["overlay_url"].endswith("/overlay.png")
    assert finished["checkerboard_url"].endswith("/checkerboard.png")

    overlay = client.get(finished["overlay_url"])
    assert overlay.status_code == 200
    assert overlay.content[:8] == b"\x89PNG\r\n\x1a\n"
    board = client.get(finished["checkerboard_url"])
    assert board.status_code == 200

    measured = client.post(f"/api/registrations/{registration_id}/landmarks", json={"points": landmarks})
    assert measured.status_code == 200, measured.text
    body = measured.json()
    assert body["metrics"]["mean_landmark_error"] is not None
    assert 0 <= body["metrics"]["success_rate"] <= 100


def test_landmarks_validation(client: TestClient) -> None:
    response = client.post(
        "/api/registrations/00000000000000000000000000000000/landmarks",
        json={"points": [[1, 2, 3]]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "landmarks_invalid"
