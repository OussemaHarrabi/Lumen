"""Configuration lue depuis l'environnement."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LUMEN_",
        env_file=REPO_ROOT / ".env",
        extra="ignore",
    )

    version: str = "0.1.0"
    session_cookie: str = "lum_session"
    session_max_age: int = 180 * 24 * 3600
    session_cookie_secure: bool = False
    max_upload_bytes: int = 25 * 1024 * 1024
    max_image_dimension: int = 12000
    cors_origin: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CORS_ORIGIN", "LUMEN_CORS_ORIGIN"),
    )
    storage_dir: Path = REPO_ROOT / "storage"
    database_url: str = f"sqlite:///{(REPO_ROOT / 'lumen.db').as_posix()}"
    models_dir: Path = REPO_ROOT / "models"
    demos_dir: Path = Path(__file__).resolve().parent / "demos"
    worker_threads: int = 2

    @property
    def cors_origins(self) -> list[str]:
        origins = ["http://localhost:3000"]
        if self.cors_origin:
            origins.extend(part.strip() for part in self.cors_origin.split(",") if part.strip())
        return list(dict.fromkeys(origins))


@lru_cache
def get_settings() -> Settings:
    return Settings()
