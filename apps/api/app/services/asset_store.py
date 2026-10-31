"""Creation d'assets a partir de donnees brutes (televersement ou demo)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models, storage
from app.config import get_settings
from app.services import imaging

settings = get_settings()
VALID_KINDS = {"image", "mask"}


def store_asset(db: Session, session_id: str, data: bytes, filename: str, kind: str) -> models.Asset:
    if not data:
        raise ValueError("Fichier vide.")
    info = imaging.inspect(data, kind, settings.max_image_dimension)
    asset_id = models.new_id()
    key = storage.asset_key(session_id, asset_id, info.extension)
    storage.write_bytes(key, data)
    asset = models.Asset(
        id=asset_id,
        session_id=session_id,
        kind=kind,
        filename=filename,
        storage_key=key,
        mime=info.mime,
        width=info.width,
        height=info.height,
        channels=info.channels,
        nbytes=len(data),
        dtype=info.dtype,
        mean=info.mean,
        min_value=info.min_value,
        max_value=info.max_value,
        mask_fraction=info.mask_fraction,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
