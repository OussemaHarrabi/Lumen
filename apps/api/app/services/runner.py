"""Execution des analyses et des recalages en tache de fond."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np

from app import models, storage
from app.db import SessionLocal
from app.errors import ApiError
from app.services import cv_bridge, imaging


def _now() -> datetime:
    return datetime.now(UTC)


def _to_display(array: np.ndarray) -> np.ndarray:
    """Ramene une sortie de recalage en RGB uint8 affichable."""
    values = np.asarray(array)
    if values.ndim == 2:
        values = np.stack([values] * 3, axis=-1)
    if values.shape[2] == 1:
        values = np.repeat(values, 3, axis=2)
    if values.dtype != np.uint8:
        values = values.astype(np.float64)
        peak = float(values.max()) if values.size else 0.0
        if peak <= 1.5:
            values = values * 255.0
        values = np.clip(values, 0, 255).astype(np.uint8)
    return values[:, :, :3]


def _fail_analysis(analysis_id: str, error: ApiError) -> None:
    with SessionLocal() as db:
        analysis = db.get(models.Analysis, analysis_id)
        if analysis is None:
            return
        analysis.status = "error"
        analysis.error = error.message
        analysis.message = None
        analysis.finished_at = _now()
        db.commit()


def _fail_registration(registration_id: str, message: str) -> None:
    with SessionLocal() as db:
        registration = db.get(models.Registration, registration_id)
        if registration is None:
            return
        registration.status = "error"
        registration.error = message
        registration.message = None
        registration.finished_at = _now()
        db.commit()


def _progress(analysis_id: str, index: int, total: int, kind: str) -> None:
    with SessionLocal() as db:
        analysis = db.get(models.Analysis, analysis_id)
        if analysis is None:
            return
        analysis.progress = min(0.95, 0.05 + 0.9 * (index / max(total, 1)))
        analysis.message = kind
        db.commit()


def execute_analysis(analysis_id: str) -> None:
    try:
        with SessionLocal() as db:
            analysis = db.get(models.Analysis, analysis_id)
            if analysis is None:
                return
            analysis.status = "running"
            analysis.progress = 0.02
            analysis.message = "Préparation"
            db.commit()
            asset = db.get(models.Asset, analysis.asset_id)
            reference = db.get(models.Asset, analysis.reference_mask_id) if analysis.reference_mask_id else None
            steps = [dict(step) for step in analysis.steps]
            session_id = analysis.session_id
            if asset is None:
                raise ApiError("asset_not_found", "L'image source a été supprimée.")
            image = imaging.load_rgb_file(storage.path_for(asset.storage_key))
            reference_mask = None
            if reference is not None:
                reference_mask = imaging.normalize_mask(
                    imaging.load_rgb_file(storage.path_for(reference.storage_key))[:, :, 0]
                )
    except ApiError as exc:
        _fail_analysis(analysis_id, exc)
        return
    except Exception as exc:  # noqa: BLE001 - la tache doit finir en erreur, jamais en cours
        _fail_analysis(analysis_id, ApiError("step_failed", f"Lecture des images impossible : {exc}"))
        return

    try:
        outcome = cv_bridge.run_pipeline(image, steps, on_step=lambda i, n, kind: _progress(analysis_id, i, n, kind))
    except ApiError as exc:
        _fail_analysis(analysis_id, exc)
        return
    except Exception as exc:  # noqa: BLE001 - garde-fou: jamais de tache muette
        _fail_analysis(analysis_id, ApiError("step_failed", str(exc) or "Échec du traitement."))
        return

    mask_key: str | None = None
    overlay_key: str | None = None
    metrics: dict[str, Any] | None = None
    try:
        if outcome.mask is not None:
            mask_key = storage.result_key(session_id, analysis_id, "mask.png")
            imaging.save_mask(outcome.mask, storage.path_for(mask_key))
            overlay_key = storage.result_key(session_id, analysis_id, "overlay.png")
            imaging.save_overlay(image, outcome.mask, storage.path_for(overlay_key))
            if reference_mask is not None:
                resized = imaging.resize_mask(reference_mask, outcome.mask.shape[:2])
                metrics = cv_bridge.evaluate(outcome.mask, resized)
    except ApiError as exc:
        _fail_analysis(analysis_id, exc)
        return
    except Exception as exc:  # noqa: BLE001 - un rendu rate ne doit pas laisser la tache en cours
        _fail_analysis(analysis_id, ApiError("step_failed", f"Écriture des résultats impossible : {exc}"))
        return

    summary: dict[str, Any] = {"total_ms": round(outcome.total_ms, 2)}
    if metrics:
        summary.update(metrics)
    result = {
        "mask_key": mask_key,
        "overlay_key": overlay_key,
        "diagnostics": outcome.diagnostics,
        "metrics": metrics,
        "steps": [report.as_dict() for report in outcome.steps],
        "total_ms": round(outcome.total_ms, 2),
    }

    with SessionLocal() as db:
        analysis = db.get(models.Analysis, analysis_id)
        if analysis is None:
            return
        analysis.status = "done"
        analysis.progress = 1.0
        analysis.message = None
        analysis.error = None
        analysis.summary = summary
        analysis.result = result
        analysis.finished_at = _now()
        db.commit()


def execute_registration(registration_id: str) -> None:
    try:
        with SessionLocal() as db:
            registration = db.get(models.Registration, registration_id)
            if registration is None:
                return
            registration.status = "running"
            registration.progress = 0.1
            registration.message = registration.method
            db.commit()
            fixed = db.get(models.Asset, registration.fixed_asset_id)
            moving = db.get(models.Asset, registration.moving_asset_id)
            method = registration.method
            params = dict(registration.params or {})
            session_id = registration.session_id
            if fixed is None or moving is None:
                raise ApiError("asset_not_found", "Une des deux images a été supprimée.")
            fixed_image = imaging.load_rgb_file(storage.path_for(fixed.storage_key))
            moving_image = imaging.load_rgb_file(storage.path_for(moving.storage_key))
    except ApiError as exc:
        _fail_registration(registration_id, exc.message)
        return
    except Exception as exc:  # noqa: BLE001 - la tache doit finir en erreur, jamais en cours
        _fail_registration(registration_id, f"Lecture des images impossible : {exc}")
        return

    try:
        outcome = cv_bridge.register(fixed_image, moving_image, method, params)
    except ApiError as exc:
        _fail_registration(registration_id, exc.message)
        return
    except Exception as exc:  # noqa: BLE001 - l'etat doit rester en base
        _fail_registration(registration_id, str(exc) or "Échec du recalage.")
        return

    try:
        warped = _to_display(outcome.warped)
        overlay_key = storage.result_key(session_id, registration_id, "overlay.png")
        checker_key = storage.result_key(session_id, registration_id, "checkerboard.png")
        imaging.save_rgb(imaging.blend(fixed_image, warped), storage.path_for(overlay_key))
        imaging.save_rgb(imaging.checkerboard(fixed_image, warped), storage.path_for(checker_key))
    except Exception as exc:  # noqa: BLE001 - un rendu rate ne doit pas laisser la tache en cours
        _fail_registration(registration_id, f"Rendu impossible : {exc}")
        return

    with SessionLocal() as db:
        registration = db.get(models.Registration, registration_id)
        if registration is None:
            return
        registration.status = "done"
        registration.progress = 1.0
        registration.message = None
        registration.error = None
        registration.transform = outcome.transform
        registration.metrics = dict(
            outcome.metrics,
            **({"confidence": outcome.confidence} if outcome.confidence is not None else {}),
        )
        registration.overlay_key = overlay_key
        registration.checkerboard_key = checker_key
        registration.finished_at = _now()
        db.commit()
