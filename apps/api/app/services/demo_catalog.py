"""Catalogue des demonstrations embarquees dans app/demos."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.errors import ApiError
from app.services import imaging

settings = get_settings()


@dataclass
class DemoPart:
    name: str
    kind: str
    filename: str
    width: int
    height: int


@dataclass
class Demo:
    slug: str
    kind: str
    label: dict[str, str]
    description: dict[str, str]
    parts: list[DemoPart]
    reference: str | None = None
    landmarks: list[list[float]] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def primary(self) -> DemoPart:
        return self.parts[0]


def _read_demo(directory: Path) -> Demo:
    manifest = directory / "demo.json"
    if not manifest.is_file():
        raise ApiError("asset_not_found", "Démonstration incomplète.", {"path": str(manifest)}, 500)
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    parts: list[DemoPart] = []
    for item in raw.get("parts", []):
        path = directory / item["file"]
        if not path.is_file():
            raise ApiError("asset_not_found", "Fichier de démonstration manquant.", {"path": str(path)}, 500)
        array, _ = imaging.load_rgb(path)
        height, width = array.shape[:2]
        parts.append(DemoPart(name=item["name"], kind=item["kind"], filename=item["file"], width=width, height=height))
    landmarks = raw.get("landmarks")
    return Demo(
        slug=raw.get("slug", directory.name),
        kind=raw.get("kind", "image"),
        label=raw.get("label", {"fr": directory.name, "en": directory.name}),
        description=raw.get("description", {"fr": "", "en": ""}),
        parts=parts,
        reference=raw.get("reference"),
        landmarks=landmarks if isinstance(landmarks, list) else None,
    )


@lru_cache(maxsize=1)
def catalog() -> tuple[Demo, ...]:
    """Catalogue statique, decode une seule fois (les fichiers ne changent pas a chaud)."""
    root = settings.demos_dir
    if not root.is_dir():
        return ()
    return tuple(
        _read_demo(path) for path in sorted(root.iterdir()) if path.is_dir() and (path / "demo.json").is_file()
    )


def get(slug: str) -> Demo:
    for demo in catalog():
        if demo.slug == slug:
            return demo
    raise ApiError("asset_not_found", f"Démonstration inconnue : {slug}.", {"slug": slug})


def demo_dir(slug: str) -> Path:
    return settings.demos_dir / slug


def part_path(demo: Demo, part_name: str | None) -> tuple[DemoPart, Path]:
    for part in demo.parts:
        if part_name is None or part.name == part_name:
            return part, demo_dir(demo.slug) / part.filename
    raise ApiError(
        "asset_not_found",
        f"Partie inconnue pour {demo.slug}.",
        {"slug": demo.slug, "part": part_name, "available": [part.name for part in demo.parts]},
    )


def read_part(demo: Demo, part_name: str | None) -> tuple[DemoPart, bytes]:
    part, path = part_path(demo, part_name)
    return part, path.read_bytes()
