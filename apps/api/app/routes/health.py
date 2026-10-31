"""Etat de sante et disponibilite des modeles."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.services import cv_bridge

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": settings.version,
        "models": cv_bridge.models_available(),
    }
