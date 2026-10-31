"""Preparation de l'environnement de test avant l'import de l'application."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TMP = Path(tempfile.mkdtemp(prefix="lumen-tests-"))

os.environ.setdefault("LUMEN_STORAGE_DIR", str(TMP / "storage"))
os.environ.setdefault("LUMEN_DATABASE_URL", f"sqlite:///{(TMP / 'lumen-test.db').as_posix()}")
os.environ.setdefault("LUMEN_MAX_UPLOAD_BYTES", "600000")
os.environ.setdefault("LUMEN_MODELS_DIR", str(ROOT / "models"))
os.environ.setdefault("LUMEN_WORKER_THREADS", "2")

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
