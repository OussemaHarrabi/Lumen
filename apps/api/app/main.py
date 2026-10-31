"""Application FastAPI de Lumen."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.db import init_db
from app.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    validation_error_handler,
)
from app.routes import api
from app.services import cv_bridge
from app.services.jobs import JobRunner
from app.session import is_uuid

settings = get_settings()
logger = logging.getLogger("lumen")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    app.state.jobs = JobRunner(settings.worker_threads)
    # Importe lumen_cv au demarrage: le cout (onnxruntime, skimage) ne doit pas tomber sur une requete.
    if cv_bridge.available():
        logger.info("lumen_cv chargé, modèles %s", cv_bridge.models_available())
    else:
        logger.warning("lumen_cv indisponible: les analyses renverront step_failed")
    logger.info("API Lumen prête, stockage dans %s", settings.storage_dir)
    try:
        yield
    finally:
        app.state.jobs.shutdown()


app = FastAPI(
    title="Lumen API",
    version=settings.version,
    description="Plateforme d'analyse d'images médicales.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def session_cookie(request: Request, call_next):
    cookie = request.cookies.get(settings.session_cookie)
    issued = False
    if is_uuid(cookie):
        request.state.session_id = cookie
    else:
        request.state.session_id = str(uuid.uuid4())
        issued = True
    response = await call_next(request)
    if issued:
        response.set_cookie(
            settings.session_cookie,
            request.state.session_id,
            max_age=settings.session_max_age,
            httponly=True,
            samesite="lax",
            secure=settings.session_cookie_secure,
            path="/",
        )
    return response


app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.include_router(api)

__all__ = ["app"]
