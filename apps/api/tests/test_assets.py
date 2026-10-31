"""Televersement, metadonnees, service et suppression des assets."""

from __future__ import annotations

from fastapi.testclient import TestClient
from helpers import mask_bytes, png_bytes, upload


def test_upload_image_and_metadata(client: TestClient) -> None:
    data = png_bytes(64, 48)
    asset = upload(client, data)
    assert asset["kind"] == "image"
    assert asset["width"] == 64
    assert asset["height"] == 48
    assert asset["channels"] == 3
    assert asset["bytes"] == len(data)
    assert asset["created_at"].endswith("Z")
    assert 0 <= asset["meta"]["mean"] <= 255
    assert asset["meta"]["min"] <= asset["meta"]["mean"] <= asset["meta"]["max"]
    assert "mask_fraction" not in asset["meta"] or asset["meta"]["mask_fraction"] is None

    listing = client.get("/api/assets").json()
    assert [item["id"] for item in listing] == [asset["id"]]

    detail = client.get(f"/api/assets/{asset['id']}").json()
    assert detail["filename"] == "image.png"


def test_upload_mask_computes_fraction(client: TestClient) -> None:
    asset = upload(client, mask_bytes(64, 48), kind="mask")
    assert asset["kind"] == "mask"
    fraction = asset["meta"]["mask_fraction"]
    assert fraction is not None
    assert 0.05 < fraction < 0.1


def test_asset_file_is_served(client: TestClient) -> None:
    data = png_bytes(32, 24)
    asset = upload(client, data)
    response = client.get(f"/api/assets/{asset['id']}/file")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, max-age=3600"
    assert response.content == data


def test_rejects_non_image_payload(client: TestClient) -> None:
    response = client.post(
        "/api/assets",
        files={"file": ("faux.png", b"pas une image", "image/png")},
        data={"kind": "image"},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_type"


def test_rejects_unknown_kind(client: TestClient) -> None:
    response = client.post(
        "/api/assets",
        files={"file": ("image.png", png_bytes(), "image/png")},
        data={"kind": "video"},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_type"


def test_rejects_oversized_file(client: TestClient) -> None:
    big = png_bytes(500, 500, seed=7)
    assert len(big) > 600000
    response = client.post(
        "/api/assets",
        files={"file": ("gros.png", big, "image/png")},
        data={"kind": "image"},
    )
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "asset_too_large"
    assert error["details"]["bytes"] > 600000


def test_delete_asset(client: TestClient) -> None:
    asset = upload(client, png_bytes(16, 16))
    assert client.delete(f"/api/assets/{asset['id']}").status_code == 204
    response = client.get(f"/api/assets/{asset['id']}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "asset_not_found"


def test_missing_asset_returns_contract_error(client: TestClient) -> None:
    response = client.get("/api/assets/00000000000000000000000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "asset_not_found"
