"""Demonstrations embarquees."""

from __future__ import annotations

from fastapi.testclient import TestClient
from helpers import copy_demo

EXPECTED = {"endoscopie-cours", "endoscopie-unet", "mammaire-busi", "retines-fire"}


def test_demo_catalog(client: TestClient) -> None:
    response = client.get("/api/demos")
    assert response.status_code == 200
    demos = {demo["slug"]: demo for demo in response.json()}
    assert set(demos) == EXPECTED
    for demo in demos.values():
        assert demo["label"]["fr"] and demo["label"]["en"]
        assert demo["description"]["fr"] and demo["description"]["en"]
        assert demo["parts"]

    pairs = {part["name"]: part for part in demos["retines-fire"]["parts"]}
    assert set(pairs) == {"fixed", "moving"}
    assert len(demos["retines-fire"]["landmarks"]) == 10
    assert demos["endoscopie-cours"]["has_reference_mask"] is True


def test_demo_files_are_served(client: TestClient) -> None:
    response = client.get("/api/demos/endoscopie-cours/file/image")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    mask = client.get("/api/demos/endoscopie-cours/file/mask")
    assert mask.status_code == 200


def test_copy_demo_as_asset(client: TestClient) -> None:
    image = copy_demo(client, "endoscopie-cours")
    assert image["kind"] == "image"
    assert (image["width"], image["height"]) == (640, 480)
    mask = copy_demo(client, "mammaire-busi", "mask")
    assert mask["kind"] == "mask"
    assert mask["meta"]["mask_fraction"] is not None


def test_copy_unknown_demo_returns_error(client: TestClient) -> None:
    response = client.post("/api/demos/inexistante/asset")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "asset_not_found"
