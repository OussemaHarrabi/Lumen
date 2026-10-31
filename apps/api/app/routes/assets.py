"""Televersement, lecture et suppression des assets."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, storage
from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.schemas import AssetOut
from app.services import asset_store
from app.session import current_session

router = APIRouter(tags=["assets"])
settings = get_settings()
CHUNK = 1 << 20


async def _read_limited(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_bytes:
            limit = settings.max_upload_bytes
            raise ApiError(
                "asset_too_large",
                f"Le fichier dépasse {limit // (1024 * 1024)} Mo.",
                {"bytes": total, "limit": limit},
            )
        chunks.append(chunk)
    return b"".join(chunks)


def sanitize_filename(name: str | None, fallback: str = "image") -> str:
    base = Path(name or fallback).name.strip()
    return (base or fallback)[:200]


def get_asset(db: Session, session_id: str, asset_id: str) -> models.Asset:
    asset = db.scalars(
        select(models.Asset).where(models.Asset.id == asset_id, models.Asset.session_id == session_id)
    ).first()
    if asset is None:
        raise ApiError("asset_not_found", "Ressource introuvable.", {"asset_id": asset_id})
    return asset


@router.post("/assets", response_model=AssetOut, status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    kind: str = Form("image"),
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> AssetOut:
    if kind not in asset_store.VALID_KINDS:
        raise ApiError(
            "unsupported_type",
            "Le type de ressource doit être image ou mask.",
            {"kind": kind},
        )
    data = await _read_limited(file)
    if not data:
        raise ApiError("unsupported_type", "Le fichier est vide.", {"filename": file.filename})
    asset = asset_store.store_asset(db, session_id, data, sanitize_filename(file.filename), kind)
    return AssetOut.from_row(asset)


@router.get("/assets", response_model=list[AssetOut])
def list_assets(
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> list[AssetOut]:
    assets = db.scalars(
        select(models.Asset)
        .where(models.Asset.session_id == session_id)
        .order_by(models.Asset.created_at.desc())
    ).all()
    return [AssetOut.from_row(asset) for asset in assets]


@router.get("/assets/{asset_id}", response_model=AssetOut)
def get_asset_detail(
    asset_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> AssetOut:
    return AssetOut.from_row(get_asset(db, session_id, asset_id))


@router.get("/assets/{asset_id}/file")
def get_asset_file(
    asset_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> FileResponse:
    asset = get_asset(db, session_id, asset_id)
    path = storage.path_for(asset.storage_key)
    if not path.is_file():
        raise ApiError("asset_not_found", "Le fichier de la ressource est introuvable.", {"asset_id": asset_id})
    return FileResponse(
        path,
        media_type=asset.mime,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(
    asset_id: str,
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> None:
    asset = get_asset(db, session_id, asset_id)
    storage.remove(asset.storage_key)
    db.delete(asset)
    db.commit()
