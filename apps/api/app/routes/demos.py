"""Demonstrations embarquees."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.schemas import AssetOut, DemoOut, DemoPart
from app.services import asset_store, demo_catalog
from app.session import current_session

router = APIRouter(tags=["demos"])


def _to_out(demo: demo_catalog.Demo) -> DemoOut:
    return DemoOut(
        slug=demo.slug,
        label=demo.label,
        description=demo.description,
        kind=demo.kind,
        width=demo.primary.width,
        height=demo.primary.height,
        has_reference_mask=demo.reference is not None,
        parts=[
            DemoPart(
                name=part.name,
                kind=part.kind,
                url=f"/api/demos/{demo.slug}/file/{part.name}",
                width=part.width,
                height=part.height,
            )
            for part in demo.parts
        ],
        landmarks=demo.landmarks,
    )


@router.get("/demos", response_model=list[DemoOut])
def list_demos() -> list[DemoOut]:
    return [_to_out(demo) for demo in demo_catalog.catalog()]


@router.get("/demos/{slug}/file/{part}")
def demo_file(slug: str, part: str) -> FileResponse:
    demo = demo_catalog.get(slug)
    _chosen, path = demo_catalog.part_path(demo, part)
    suffix = path.suffix.lower()
    media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".tif": "image/tiff", ".bmp": "image/bmp"}
    return FileResponse(
        path,
        media_type=media.get(suffix, "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/demos/{slug}/asset", response_model=AssetOut, status_code=201)
def copy_demo_asset(
    slug: str,
    part: str | None = Query(default=None),
    session_id: str = Depends(current_session),
    db: Session = Depends(get_db),
) -> AssetOut:
    demo = demo_catalog.get(slug)
    chosen, data = demo_catalog.read_part(demo, part)
    if not data:
        raise ApiError("asset_not_found", "Démonstration vide.", {"slug": slug})
    filename = f"{slug}-{chosen.name}{chosen.filename[chosen.filename.rfind('.'):]}"
    asset = asset_store.store_asset(db, session_id, data, filename, chosen.kind)
    return AssetOut.from_row(asset)
