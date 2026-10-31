"""Presets de pipeline exposes par lumen_cv."""

from __future__ import annotations

import types

import pytest
from fastapi.testclient import TestClient
from helpers import requires_cv

from app.services import cv_bridge

SAMPLE = [
    {
        "id": "otsu",
        "label_fr": "Seuillage d'Otsu",
        "label_en": "Otsu thresholding",
        "description_fr": "Seuillage automatique sur l'histogramme.",
        "description_en": "Automatic threshold from the histogram.",
        "asset_hint": "endoscopie-cours",
        "steps": [
            {"kind": "preprocess.gray", "params": {}},
            {"kind": "segment.otsu", "params": {"invert": False}},
        ],
        "expected": {"dice": 0.62, "iou": 0.45},
    },
    {"id": "unet", "steps": [{"kind": "dl.unet_endoscopie", "params": {}}]},
]


def test_presets_empty_when_registry_missing(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(cv_bridge, "presets", list)
    response = client.get("/api/presets")
    assert response.status_code == 200
    assert response.json() == []


def test_presets_passthrough(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(cv_bridge, "presets", lambda: SAMPLE)
    response = client.get("/api/presets")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [preset["id"] for preset in body] == ["otsu", "unet"]

    first = body[0]
    assert first["label_fr"] == "Seuillage d'Otsu"
    assert first["asset_hint"] == "endoscopie-cours"
    assert [step["kind"] for step in first["steps"]] == ["preprocess.gray", "segment.otsu"]
    assert first["expected"] == {"dice": 0.62, "iou": 0.45}
    assert body[1]["label_fr"] == "unet"


def test_presets_route_in_openapi(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert "/api/presets" in spec["paths"]


def test_presets_are_cached_and_copied(monkeypatch) -> None:
    calls = []

    def reader():
        calls.append(1)
        return [{"id": "otsu", "steps": []}]

    module = types.SimpleNamespace(registry=types.SimpleNamespace(presets=reader))
    monkeypatch.setattr(cv_bridge, "_load", lambda: module)
    monkeypatch.setattr(cv_bridge, "_presets_cache", None)

    first = cv_bridge.presets()
    first[0]["id"] = "modifie"
    second = cv_bridge.presets()

    assert second[0]["id"] == "otsu"
    assert len(calls) == 1


@requires_cv
def test_presets_from_lumen_cv_are_usable(client: TestClient) -> None:
    response = client.get("/api/presets")
    assert response.status_code == 200
    presets = response.json()
    if not presets:
        pytest.skip("lumen_cv n'expose pas encore presets()")
    ids = {preset["id"] for preset in presets}
    assert {"otsu", "kmeans", "watershed", "chan-vese", "unet"} <= ids
    catalogue = client.get("/api/schema/pipeline").json()["catalogue"]
    for preset in presets:
        assert preset["steps"], preset["id"]
        assert preset["asset_hint"]
        for step in preset["steps"]:
            assert step["kind"] in catalogue, (preset["id"], step["kind"])
