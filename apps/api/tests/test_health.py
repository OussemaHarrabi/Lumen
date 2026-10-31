"""Sante, cookie de session et schema du pipeline."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == get_settings().version
    assert set(body["models"]) == {"endoscopie", "busi"}
    assert all(isinstance(value, bool) for value in body["models"].values())


def test_session_cookie_is_issued(client: TestClient) -> None:
    response = client.get("/api/assets")
    assert response.status_code == 200
    cookie = response.cookies.get("lum_session")
    assert cookie is not None
    assert len(cookie) == 36


def test_unknown_route_uses_error_format(client: TestClient) -> None:
    response = client.get("/api/inconnu")
    assert response.status_code == 404
    payload = response.json()
    assert "code" in payload["error"]
    assert "message" in payload["error"]
