"""DTO de l'API, conformes au contrat."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import Analysis, Asset, Registration

Status = Literal["queued", "running", "done", "error"]


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    moment = value if value.tzinfo else value.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


class AssetMeta(BaseModel):
    dtype: str | None = None
    mean: float | None = None
    min: float | None = None
    max: float | None = None
    mask_fraction: float | None = None


class AssetOut(BaseModel):
    id: str
    kind: str
    filename: str
    width: int
    height: int
    channels: int
    bytes: int
    created_at: str
    meta: AssetMeta

    @classmethod
    def from_row(cls, asset: Asset) -> AssetOut:
        return cls(
            id=asset.id,
            kind=asset.kind,
            filename=asset.filename,
            width=asset.width,
            height=asset.height,
            channels=asset.channels,
            bytes=asset.nbytes,
            created_at=isoformat(asset.created_at) or "",
            meta=AssetMeta(
                dtype=asset.dtype,
                mean=asset.mean,
                min=asset.min_value,
                max=asset.max_value,
                mask_fraction=asset.mask_fraction,
            ),
        )


class DemoPart(BaseModel):
    name: str
    kind: str
    url: str
    width: int
    height: int


class DemoOut(BaseModel):
    slug: str
    label: dict[str, str]
    description: dict[str, str]
    kind: str
    width: int
    height: int
    has_reference_mask: bool
    parts: list[DemoPart]
    landmarks: list[list[float]] | None = None


class StepIn(BaseModel):
    kind: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class StepOut(BaseModel):
    kind: str
    params: dict[str, Any]


class PresetExpected(BaseModel):
    model_config = ConfigDict(extra="allow")

    dice: float | None = None
    iou: float | None = None


class PresetOut(BaseModel):
    """Preset de pipeline expose par lumen_cv.registry.presets()."""

    model_config = ConfigDict(extra="allow")

    id: str
    label_fr: str = ""
    label_en: str = ""
    description_fr: str = ""
    description_en: str = ""
    asset_hint: str | None = None
    steps: list[StepOut] = Field(default_factory=list)
    expected: PresetExpected | None = None


class AnalysisIn(BaseModel):
    asset_id: str
    reference_mask_id: str | None = None
    steps: list[StepIn]


class Metrics(BaseModel):
    dice: float | None = None
    iou: float | None = None
    recall: float | None = None
    precision: float | None = None


class Summary(BaseModel):
    dice: float | None = None
    iou: float | None = None
    recall: float | None = None
    precision: float | None = None
    total_ms: float | None = None


class AnalysisOut(BaseModel):
    id: str
    asset_id: str
    reference_mask_id: str | None = None
    steps: list[StepOut]
    status: Status
    progress: float
    message: str | None = None
    created_at: str
    finished_at: str | None = None
    error: str | None = None
    summary: Summary | None = None

    @classmethod
    def from_row(cls, analysis: Analysis) -> AnalysisOut:
        return cls(
            id=analysis.id,
            asset_id=analysis.asset_id,
            reference_mask_id=analysis.reference_mask_id,
            steps=[StepOut(kind=step.get("kind", ""), params=step.get("params") or {}) for step in analysis.steps],
            status=analysis.status,  # type: ignore[arg-type]
            progress=analysis.progress,
            message=analysis.message,
            created_at=isoformat(analysis.created_at) or "",
            finished_at=isoformat(analysis.finished_at),
            error=analysis.error,
            summary=Summary(**analysis.summary) if analysis.summary else None,
        )


class StepReportOut(BaseModel):
    kind: str
    params: dict[str, Any]
    duration_ms: float
    diagnostics: dict[str, Any] | None = None


class AnalysisResultOut(BaseModel):
    analysis_id: str
    mask_url: str | None
    overlay_url: str | None
    diagnostics: dict[str, Any]
    metrics: Metrics | None
    steps: list[StepReportOut]
    total_ms: float


class RegistrationIn(BaseModel):
    fixed_asset_id: str
    moving_asset_id: str
    method: Literal["translation", "affine", "homography", "optical_flow"]
    params: dict[str, Any] | None = None


class LandmarksIn(BaseModel):
    points: list[list[float]]

    @field_validator("points")
    @classmethod
    def _check_points(cls, points: list[list[float]]) -> list[list[float]]:
        if not points:
            raise ValueError("Au moins un point est requis.")
        cleaned: list[list[float]] = []
        for point in points:
            if len(point) != 4:
                raise ValueError("Chaque point doit contenir [x1, y1, x2, y2].")
            cleaned.append([float(value) for value in point])
        return cleaned


class RegistrationMetrics(BaseModel):
    mean_landmark_error: float | None = None
    success_rate: float | None = None
    ncc: float | None = None
    mse: float | None = None
    nmi: float | None = None
    confidence: float | None = None


class RegistrationOut(BaseModel):
    id: str
    fixed_asset_id: str
    moving_asset_id: str
    method: str
    status: Status
    progress: float
    metrics: RegistrationMetrics | None = None
    transform: list[list[float]] | None = None
    overlay_url: str | None = None
    checkerboard_url: str | None = None
    created_at: str
    finished_at: str | None = None
    error: str | None = None

    @classmethod
    def from_row(cls, registration: Registration) -> RegistrationOut:
        metrics = registration.metrics or {}
        return cls(
            id=registration.id,
            fixed_asset_id=registration.fixed_asset_id,
            moving_asset_id=registration.moving_asset_id,
            method=registration.method,
            status=registration.status,  # type: ignore[arg-type]
            progress=registration.progress,
            metrics=RegistrationMetrics(**metrics) if metrics else None,
            transform=registration.transform,
            overlay_url=f"/api/registrations/{registration.id}/overlay.png" if registration.overlay_key else None,
            checkerboard_url=(
                f"/api/registrations/{registration.id}/checkerboard.png" if registration.checkerboard_key else None
            ),
            created_at=isoformat(registration.created_at) or "",
            finished_at=isoformat(registration.finished_at),
            error=registration.error,
        )
