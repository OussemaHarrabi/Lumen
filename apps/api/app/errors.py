"""Erreurs applicatives au format du contrat."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

DEFAULT_STATUS = {
    "asset_too_large": 413,
    "unsupported_type": 415,
    "asset_not_found": 404,
    "pipeline_invalid": 422,
    "step_failed": 500,
    "model_missing": 503,
    "registration_failed": 500,
    "landmarks_invalid": 422,
}


class ApiError(Exception):
    """Erreur métier renvoyée au format {"error": {code, message, details}}."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code or DEFAULT_STATUS.get(code, 400)


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_payload(code, message, details))


def code_for_path(path: str) -> str:
    """Choisit le code du contrat quand une erreur vient de la validation FastAPI."""
    if path.endswith("/landmarks"):
        return "landmarks_invalid"
    if "/registrations" in path:
        return "registration_failed"
    if "/assets" in path or "/demos" in path:
        return "unsupported_type"
    return "pipeline_invalid"


async def api_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {
            "loc": [str(part) for part in error.get("loc", ())],
            "msg": error.get("msg", "Valeur invalide."),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return error_response(422, code_for_path(request.url.path), "Requête invalide.", {"errors": errors})


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = "asset_not_found" if exc.status_code == 404 else code_for_path(request.url.path)
    message = str(exc.detail) if exc.detail else "Ressource indisponible."
    return error_response(exc.status_code, code, message)
