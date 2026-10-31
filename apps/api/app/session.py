"""Session anonyme portee par le cookie lum_session."""

from __future__ import annotations

import uuid

from fastapi import Request

from app.config import get_settings

settings = get_settings()


def is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def current_session(request: Request) -> str:
    stored = getattr(request.state, "session_id", None)
    if isinstance(stored, str) and is_uuid(stored):
        return stored
    cookie = request.cookies.get(settings.session_cookie)
    if is_uuid(cookie):
        request.state.session_id = cookie
        return cookie  # type: ignore[return-value]
    fresh = str(uuid.uuid4())
    request.state.session_id = fresh
    return fresh
