"""Cycle complet d'une analyse, erreurs de pipeline et flux SSE."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from helpers import copy_demo, has_cv, png_bytes, requires_cv, upload, wait_for_job

from app.errors import ApiError
from app.services import cv_bridge

STEPS = [
    {"kind": "preprocess.gray", "params": {}},
    {"kind": "preprocess.median", "params": {"ksize": 5}},
    {"kind": "segment.otsu", "params": {"invert": False}},
    {"kind": "postprocess.largest_component", "params": {}},
]


@requires_cv
def test_full_analysis_on_demo_image(client: TestClient) -> None:
    image = copy_demo(client, "endoscopie-cours")
    mask = copy_demo(client, "endoscopie-cours", "mask")
    response = client.post(
        "/api/analyses",
        json={"asset_id": image["id"], "reference_mask_id": mask["id"], "steps": STEPS},
    )
    assert response.status_code == 202, response.text
    analysis = response.json()
    assert analysis["status"] in {"queued", "running"}
    assert analysis["progress"] <= 1

    finished = wait_for_job(client, analysis["id"])
    assert finished["status"] == "done", finished
    assert finished["finished_at"] is not None
    assert finished["summary"]["total_ms"] > 0
    assert 0 <= finished["summary"]["dice"] <= 1

    result = client.get(f"/api/analyses/{analysis['id']}/result")
    assert result.status_code == 200
    payload = result.json()
    assert payload["mask_url"].endswith("/mask.png")
    assert payload["overlay_url"].endswith("/overlay.png")
    assert payload["metrics"]["dice"] is not None
    assert len(payload["steps"]) == len(STEPS)
    assert all(step["duration_ms"] >= 0 for step in payload["steps"])

    mask_png = client.get(payload["mask_url"])
    assert mask_png.status_code == 200
    assert mask_png.headers["content-type"] == "image/png"
    assert mask_png.content[:8] == b"\x89PNG\r\n\x1a\n"

    overlay = client.get(payload["overlay_url"])
    assert overlay.status_code == 200
    assert overlay.content[:8] == b"\x89PNG\r\n\x1a\n"


@requires_cv
def test_job_events_stream(client: TestClient) -> None:
    image = copy_demo(client, "endoscopie-cours")
    response = client.post("/api/analyses", json={"asset_id": image["id"], "steps": STEPS[:3]})
    analysis_id = response.json()["id"]
    with client.stream("GET", f"/api/jobs/{analysis_id}/events") as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        body = "".join(stream.iter_text())
    assert "event: progress" in body or "event: done" in body
    events = [line for line in body.splitlines() if line.startswith("data: ")]
    assert events
    last = json.loads(events[-1].removeprefix("data: "))
    assert last["id"] == analysis_id
    assert last["status"] == "done"


def test_invalid_step_is_rejected(client: TestClient) -> None:
    asset = upload(client, png_bytes())
    response = client.post(
        "/api/analyses",
        json={"asset_id": asset["id"], "steps": [{"kind": "segment.inexistant", "params": {}}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pipeline_invalid"


@requires_cv
def test_out_of_range_param_is_rejected(client: TestClient) -> None:
    asset = upload(client, png_bytes())
    response = client.post(
        "/api/analyses",
        json={"asset_id": asset["id"], "steps": [{"kind": "preprocess.median", "params": {"ksize": 99}}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pipeline_invalid"
    assert response.json()["error"]["details"]["param"] == "ksize"


@requires_cv
def test_unknown_param_is_rejected(client: TestClient) -> None:
    asset = upload(client, png_bytes())
    response = client.post(
        "/api/analyses",
        json={"asset_id": asset["id"], "steps": [{"kind": "preprocess.gray", "params": {"flou": 3}}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pipeline_invalid"


def test_empty_pipeline_is_rejected(client: TestClient) -> None:
    asset = upload(client, png_bytes())
    response = client.post("/api/analyses", json={"asset_id": asset["id"], "steps": []})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pipeline_invalid"


def test_result_unavailable_before_creation(client: TestClient) -> None:
    response = client.get("/api/analyses/00000000000000000000000000000000/result")
    assert response.status_code == 404


@requires_cv
def test_reference_mask_must_be_a_mask(client: TestClient) -> None:
    asset = upload(client, png_bytes())
    response = client.post(
        "/api/analyses",
        json={"asset_id": asset["id"], "reference_mask_id": asset["id"], "steps": STEPS},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pipeline_invalid"


def test_pipeline_schema(client: TestClient) -> None:
    if not has_cv():
        response = client.get("/api/schema/pipeline")
        assert response.status_code == 503
        return
    response = client.get("/api/schema/pipeline")
    assert response.status_code == 200
    catalogue = response.json()["catalogue"]
    assert "segment.otsu" in catalogue

@requires_cv
def test_failed_step_marks_analysis_error(client: TestClient) -> None:
    asset = upload(client, png_bytes(48, 32, seed=11))
    response = client.post(
        "/api/analyses",
        json={"asset_id": asset["id"], "steps": [{"kind": "postprocess.largest_component", "params": {}}]},
    )
    assert response.status_code == 202, response.text
    analysis_id = response.json()["id"]
    finished = wait_for_job(client, analysis_id)
    assert finished["status"] == "error", finished
    assert finished["error"]
    assert client.get(f"/api/analyses/{analysis_id}/result").status_code == 404

    with client.stream("GET", f"/api/jobs/{analysis_id}/events") as stream:
        body = "".join(stream.iter_text())
    assert "event: error" in body


def test_degrades_without_lumen_cv(client: TestClient, monkeypatch) -> None:
    """Sans lumen_cv, l'API reste debout et les analyses renvoient step_failed."""
    monkeypatch.setattr(cv_bridge, "_module", None)
    monkeypatch.setattr(
        cv_bridge,
        "_import_error",
        ApiError("step_failed", "Le moteur de traitement lumen_cv n'est pas disponible.", None, 503),
    )
    assert client.get("/api/health").json()["status"] == "ok"
    asset = upload(client, png_bytes())
    response = client.post(
        "/api/analyses",
        json={"asset_id": asset["id"], "steps": [{"kind": "segment.otsu", "params": {}}]},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "step_failed"
    assert client.get("/api/schema/pipeline").status_code == 503
