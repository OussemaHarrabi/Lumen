"""Creation, suivi et resultats des analyses."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, storage
from app.db import get_db
from app.errors import ApiError
from app.schemas import (
    AnalysisIn,
    AnalysisOut,
    AnalysisResultOut,
    Metrics,
    StepReportOut,
)
from app.services import cv_bridge, runner
from app.session import current_session

router = APIRouter(tags=["analyses"])


def get_analysis(db: Session, session_id: str, analysis_id: str) -> models.Analysis:
    analysis = db.scalars(
        select(models.Analysis).where(
            models.Analysis.id == analysis_id,
            models.Analysis.session_id == session_id,
        )
    ).first()
    if analysis is None:
        raise ApiError("asset_not_found", "Analyse introuvable.", {"analysis_id": analysis_id})
    return analysis


def _asset(db: Session, session_id: str, asset_id: str) -> models.Asset:
    asset = db.scalars(
        select(models.Asset).where(models.Asset.id == asset_id, models.Asset.session_id == session_id)
    ).first()
    if asset is None:
        raise ApiError("asset_not_found", "Ressource introuvable.", {"asset_id": asset_id})
    return asset


@router.post("/analyses", response_model=AnalysisOut, status_code=202)
def create_analysis(
    payload: AnalysisIn,
    request: Request,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> AnalysisOut:
    asset = _asset(db, session_id, payload.asset_id)
    reference: models.Asset | None = None
    if payload.reference_mask_id:
        reference = _asset(db, session_id, payload.reference_mask_id)
        if reference.kind != "mask":
            raise ApiError(
                "pipeline_invalid",
                "Le masque de référence doit être une ressource de type mask.",
                {"asset_id": reference.id, "kind": reference.kind},
            )
    steps = cv_bridge.validate_steps([step.model_dump() for step in payload.steps])
    analysis = models.Analysis(
        session_id=session_id,
        asset_id=asset.id,
        reference_mask_id=reference.id if reference is not None else None,
        steps=steps,
        status="queued",
        progress=0.0,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    request.app.state.jobs.submit(runner.execute_analysis, analysis.id)
    return AnalysisOut.from_row(analysis)


@router.get("/analyses", response_model=list[AnalysisOut])
def list_analyses(
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> list[AnalysisOut]:
    rows = db.scalars(
        select(models.Analysis)
        .where(models.Analysis.session_id == session_id)
        .order_by(models.Analysis.created_at.desc())
        .limit(50)
    ).all()
    return [AnalysisOut.from_row(row) for row in rows]


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis_detail(
    analysis_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> AnalysisOut:
    return AnalysisOut.from_row(get_analysis(db, session_id, analysis_id))


@router.get("/analyses/{analysis_id}/result", response_model=AnalysisResultOut)
def get_analysis_result(
    analysis_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> AnalysisResultOut:
    analysis = get_analysis(db, session_id, analysis_id)
    if analysis.status != "done" or not analysis.result:
        raise ApiError(
            "asset_not_found",
            "Le résultat n'est pas encore disponible.",
            {"analysis_id": analysis_id, "status": analysis.status},
        )
    stored: dict[str, Any] = analysis.result
    steps = [
        StepReportOut(
            kind=step.get("kind", ""),
            params=step.get("params") or {},
            duration_ms=float(step.get("duration_ms", 0.0)),
            diagnostics=step.get("diagnostics"),
        )
        for step in stored.get("steps", [])
    ]
    metrics = stored.get("metrics")
    return AnalysisResultOut(
        analysis_id=analysis.id,
        mask_url=f"/api/analyses/{analysis.id}/mask.png" if stored.get("mask_key") else None,
        overlay_url=f"/api/analyses/{analysis.id}/overlay.png" if stored.get("overlay_key") else None,
        diagnostics=stored.get("diagnostics") or {},
        metrics=Metrics(**metrics) if metrics else None,
        steps=steps,
        total_ms=float(stored.get("total_ms", 0.0)),
    )


@router.get("/analyses/{analysis_id}/mask.png")
def get_analysis_mask(
    analysis_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> FileResponse:
    analysis = get_analysis(db, session_id, analysis_id)
    key = (analysis.result or {}).get("mask_key") if analysis.result else None
    if not key:
        raise ApiError("asset_not_found", "Aucun masque pour cette analyse.", {"analysis_id": analysis_id})
    path = storage.path_for(key)
    if not path.is_file():
        raise ApiError("asset_not_found", "Masque introuvable sur le disque.", {"analysis_id": analysis_id})
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/analyses/{analysis_id}/overlay.png")
def get_analysis_overlay(
    analysis_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> FileResponse:
    analysis = get_analysis(db, session_id, analysis_id)
    key = (analysis.result or {}).get("overlay_key") if analysis.result else None
    if not key:
        raise ApiError("asset_not_found", "Aucune superposition pour cette analyse.", {"analysis_id": analysis_id})
    path = storage.path_for(key)
    if not path.is_file():
        raise ApiError("asset_not_found", "Superposition introuvable sur le disque.", {"analysis_id": analysis_id})
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(
    analysis_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> None:
    analysis = get_analysis(db, session_id, analysis_id)
    if analysis.result:
        storage.remove(analysis.result.get("mask_key"))
        storage.remove(analysis.result.get("overlay_key"))
    db.delete(analysis)
    db.commit()
