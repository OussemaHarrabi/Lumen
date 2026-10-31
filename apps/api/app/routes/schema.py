"""Schema du catalogue d'etapes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services import cv_bridge

router = APIRouter(tags=["schema"])


@router.get("/schema/pipeline")
def pipeline_schema() -> dict[str, Any]:
    return cv_bridge.pipeline_schema()
