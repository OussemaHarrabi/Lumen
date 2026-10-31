"""Presets de pipeline fournis par lumen_cv, sans recalcul cote API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import ValidationError

from app.schemas import PresetOut, StepOut
from app.services import cv_bridge

router = APIRouter(tags=["presets"])
logger = logging.getLogger("lumen.presets")


def _to_out(raw: dict[str, Any]) -> PresetOut | None:
    data = dict(raw)
    preset_id = str(data.get("id") or "")
    data["id"] = preset_id
    data.setdefault("label_fr", preset_id)
    data.setdefault("label_en", preset_id)
    data.setdefault("description_fr", "")
    data.setdefault("description_en", "")
    data["steps"] = [
        StepOut(kind=str(step.get("kind", "")), params=step.get("params") or {})
        for step in data.get("steps") or []
        if isinstance(step, dict)
    ]
    try:
        return PresetOut.model_validate(data)
    except ValidationError:
        logger.warning("Preset ignoré, format inattendu: %s", preset_id, exc_info=True)
        return None


@router.get("/presets", response_model=list[PresetOut])
def list_presets() -> list[PresetOut]:
    presets = [item for item in (_to_out(raw) for raw in cv_bridge.presets()) if item is not None]
    return presets
