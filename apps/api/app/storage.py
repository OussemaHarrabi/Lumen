"""Stockage des fichiers hors du dossier public, un dossier par session."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings

settings = get_settings()


def root() -> Path:
    return settings.storage_dir


def session_dir(session_id: str) -> Path:
    path = root() / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_key(session_id: str, asset_id: str, ext: str) -> str:
    return f"{session_id}/{asset_id}{ext}"


def results_dir(session_id: str) -> Path:
    path = session_dir(session_id) / "results"
    path.mkdir(parents=True, exist_ok=True)
    return path


def result_key(session_id: str, job_id: str, name: str) -> str:
    return f"{session_id}/results/{job_id}_{name}"


def path_for(key: str) -> Path:
    return root() / key


def write_bytes(key: str, data: bytes) -> Path:
    path = path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def remove(key: str | None) -> None:
    if not key:
        return
    path = path_for(key)
    if path.is_file():
        path.unlink()
