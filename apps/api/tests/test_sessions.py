"""Isolation des sessions anonymes."""

from __future__ import annotations

from fastapi.testclient import TestClient
from helpers import png_bytes, upload

from app.main import app


def test_two_clients_have_separate_sessions() -> None:
    with TestClient(app) as first, TestClient(app) as second:
        mine = upload(first, png_bytes(20, 20))
        assert first.get("/api/assets").json()[0]["id"] == mine["id"]
        assert second.get("/api/assets").json() == []
        assert second.get(f"/api/assets/{mine['id']}").status_code == 404

        cookie_one = first.cookies.get("lum_session")
        cookie_two = second.cookies.get("lum_session")
        assert cookie_one and cookie_two and cookie_one != cookie_two


def test_analysis_from_other_session_is_hidden(client: TestClient) -> None:
    with TestClient(app) as other:
        response = other.get("/api/analyses/00000000000000000000000000000000")
        assert response.status_code == 404
