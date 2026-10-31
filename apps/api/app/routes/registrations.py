"""Recalage de paires d'images."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, storage
from app.db import get_db
from app.errors import ApiError
from app.schemas import LandmarksIn, RegistrationIn, RegistrationOut
from app.services import cv_bridge, runner
from app.session import current_session

router = APIRouter(tags=["registrations"])


def get_registration(db: Session, session_id: str, registration_id: str) -> models.Registration:
    registration = db.scalars(
        select(models.Registration).where(
            models.Registration.id == registration_id,
            models.Registration.session_id == session_id,
        )
    ).first()
    if registration is None:
        raise ApiError("asset_not_found", "Recalage introuvable.", {"registration_id": registration_id})
    return registration


def _asset(db: Session, session_id: str, asset_id: str) -> models.Asset:
    asset = db.scalars(
        select(models.Asset).where(models.Asset.id == asset_id, models.Asset.session_id == session_id)
    ).first()
    if asset is None:
        raise ApiError("asset_not_found", "Ressource introuvable.", {"asset_id": asset_id})
    return asset


@router.post("/registrations", response_model=RegistrationOut, status_code=202)
def create_registration(
    payload: RegistrationIn,
    request: Request,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> RegistrationOut:
    fixed = _asset(db, session_id, payload.fixed_asset_id)
    moving = _asset(db, session_id, payload.moving_asset_id)
    if fixed.kind != "image" or moving.kind != "image":
        raise ApiError(
            "registration_failed",
            "Le recalage attend deux images.",
            {"fixed": fixed.kind, "moving": moving.kind},
            422,
        )
    registration = models.Registration(
        session_id=session_id,
        fixed_asset_id=fixed.id,
        moving_asset_id=moving.id,
        method=payload.method,
        params=payload.params or {},
        status="queued",
        progress=0.0,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    request.app.state.jobs.submit(runner.execute_registration, registration.id)
    return RegistrationOut.from_row(registration)


@router.get("/registrations/{registration_id}", response_model=RegistrationOut)
def get_registration_detail(
    registration_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> RegistrationOut:
    return RegistrationOut.from_row(get_registration(db, session_id, registration_id))


@router.post("/registrations/{registration_id}/landmarks", response_model=RegistrationOut)
def set_landmarks(
    registration_id: str,
    payload: LandmarksIn,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> RegistrationOut:
    registration = get_registration(db, session_id, registration_id)
    for point in payload.points:
        if not all(math.isfinite(value) and value >= 0 for value in point):
            raise ApiError(
                "landmarks_invalid",
                "Les points doivent être des coordonnées positives.",
                {"point": point},
            )
    if registration.status != "done" or registration.transform is None:
        raise ApiError(
            "registration_failed",
            "Le recalage doit être terminé avant de mesurer les points.",
            {"registration_id": registration_id, "status": registration.status},
            409,
        )
    error = cv_bridge.landmark_error(registration.transform, payload.points)
    metrics = dict(registration.metrics or {})
    metrics["mean_landmark_error"] = error["mean"]
    metrics["success_rate"] = error["success_rate"]
    registration.landmarks = [[float(value) for value in point] for point in payload.points]
    registration.metrics = metrics
    db.commit()
    db.refresh(registration)
    return RegistrationOut.from_row(registration)


def _result_file(db: Session, session_id: str, registration_id: str, which: str) -> FileResponse:
    registration = get_registration(db, session_id, registration_id)
    key = registration.overlay_key if which == "overlay" else registration.checkerboard_key
    if not key:
        raise ApiError("asset_not_found", "Aucune image de recalage disponible.", {"registration_id": registration_id})
    path = storage.path_for(key)
    if not path.is_file():
        raise ApiError("asset_not_found", "Image introuvable sur le disque.", {"registration_id": registration_id})
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/registrations/{registration_id}/overlay.png")
def registration_overlay(
    registration_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> FileResponse:
    return _result_file(db, session_id, registration_id, "overlay")


@router.get("/registrations/{registration_id}/checkerboard.png")
def registration_checkerboard(
    registration_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> FileResponse:
    return _result_file(db, session_id, registration_id, "checkerboard")
