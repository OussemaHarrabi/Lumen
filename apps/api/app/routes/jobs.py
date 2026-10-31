"""Suivi d'avancement en Server-Sent Events."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app import models
from app.db import SessionLocal
from app.errors import ApiError
from app.session import current_session

router = APIRouter(tags=["jobs"])
POLL_SECONDS = 0.25


def _state(job_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        analysis = db.get(models.Analysis, job_id)
        if analysis is not None:
            return {
                "session_id": analysis.session_id,
                "payload": {
                    "id": analysis.id,
                    "status": analysis.status,
                    "progress": round(analysis.progress, 4),
                    "message": analysis.message,
                    "error": analysis.error,
                },
            }
        registration = db.get(models.Registration, job_id)
        if registration is not None:
            return {
                "session_id": registration.session_id,
                "payload": {
                    "id": registration.id,
                    "status": registration.status,
                    "progress": round(registration.progress, 4),
                    "message": registration.message,
                    "error": registration.error,
                },
            }
    return None


def _format(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    state = await run_in_threadpool(_state, job_id)
    if state is None:
        raise ApiError("asset_not_found", "Tâche introuvable.", {"job_id": job_id})
    if state["session_id"] != current_session(request):
        raise ApiError("asset_not_found", "Tâche introuvable.", {"job_id": job_id})

    async def stream():
        previous: tuple | None = None
        while True:
            if await request.is_disconnected():
                return
            current = await run_in_threadpool(_state, job_id)
            if current is None:
                yield _format("error", {"id": job_id, "status": "error", "progress": 0, "error": "Tâche introuvable."})
                return
            payload = current["payload"]
            signature = (payload["status"], payload["progress"], payload["message"], payload["error"])
            if signature != previous:
                event = payload["status"] if payload["status"] in {"done", "error"} else "progress"
                yield _format(event, payload)
                previous = signature
            if payload["status"] in {"done", "error"}:
                return
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
