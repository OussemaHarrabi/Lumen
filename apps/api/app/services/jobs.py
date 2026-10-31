"""Pool de threads interne pour les traitements longs."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger("lumen.jobs")


class JobRunner:
    """Execute les taches hors de la boucle HTTP, l'etat vit en base."""

    def __init__(self, workers: int = 2) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="lumen-job")

    def submit(self, job: Callable[..., Any], *args: Any) -> None:
        self._pool.submit(self._guarded, job, *args)

    @staticmethod
    def _guarded(job: Callable[..., Any], *args: Any) -> None:
        try:
            job(*args)
        except Exception:  # la tache doit toujours laisser un etat en base
            logger.exception("Tache interrompue: %s", getattr(job, "__name__", job))

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
