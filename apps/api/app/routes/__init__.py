"""Routes de l'API Lumen."""

from __future__ import annotations

from fastapi import APIRouter

from app.routes import analyses, assets, demos, health, jobs, presets, registrations, schema

api = APIRouter(prefix="/api")
for module in (health, assets, demos, presets, analyses, jobs, registrations, schema):
    api.include_router(module.router)

__all__ = ["api"]
