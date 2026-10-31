"""Execution d'un pipeline d'etapes et resultat associe.

Un pipeline enchaine des etapes du catalogue : les etapes d'image produisent une
image, les etapes de segmentation un masque, les etapes de post-traitement
consomment et produisent un masque. Chaque etape est chronometree et ses
diagnostics sont conserves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import numpy as np

from .errors import ModelMissingError, PipelineError, StepError
from .io import to_mask
from .registry import STEP_CATALOGUE, StepSpec, pipeline_schema

__all__ = [
    "ModelMissingError",
    "PipelineError",
    "PipelineResult",
    "StepError",
    "StepResult",
    "pipeline_schema",
    "run_pipeline",
    "schema",
    "validate_steps",
]


@dataclass
class StepResult:
    """Trace d'une etape executee."""

    kind: str
    params: dict[str, Any]
    duration_ms: float
    diagnostics: dict[str, Any] | None = None


@dataclass
class PipelineResult:
    """Resultat complet : masque final, image finale, traces et duree.

    mask vaut None tant qu'aucune etape de segmentation n'a tourne. Il contient
    toujours des valeurs 0/1.
    """

    mask: np.ndarray | None
    steps: list[StepResult] = field(default_factory=list)
    total_ms: float = 0.0
    image: np.ndarray | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _extract(step: Any) -> tuple[str, dict[str, Any]]:
    """Type et parametres d'une etape, dictee ou objet avec kind/params."""
    if isinstance(step, dict):
        kind = step.get("kind")
        params = step.get("params") or {}
    else:
        kind = getattr(step, "kind", None)
        params = getattr(step, "params", None) or {}
    if not isinstance(kind, str) or not kind:
        raise PipelineError("Chaque etape doit avoir un champ kind non vide")
    if not isinstance(params, dict):
        raise PipelineError(f"Les parametres de {kind} doivent etre un objet", [kind])
    return kind, params


def validate_steps(steps: list[Any]) -> list[tuple[StepSpec, dict[str, Any]]]:
    """Verifie toutes les etapes avant execution et renvoie les parametres effectifs."""
    if not isinstance(steps, (list, tuple)):
        raise PipelineError("steps doit etre une liste")
    prepared: list[tuple[StepSpec, dict[str, Any]]] = []
    errors: list[str] = []
    for index, step in enumerate(steps):
        try:
            kind, params = _extract(step)
        except PipelineError as error:
            errors.append(str(error))
            continue
        spec = STEP_CATALOGUE.get(kind)
        if spec is None:
            errors.append(f"etape {index} : type inconnu {kind}")
            continue
        try:
            prepared.append((spec, spec.coerce(params)))
        except ValueError as error:
            errors.append(f"etape {index} ({kind}) : {error}")
    if errors:
        raise PipelineError("Pipeline invalide : " + " ; ".join(errors), errors)
    return prepared


def _mask_stats(mask: np.ndarray) -> dict[str, Any]:
    pixels = int(mask.sum())
    fraction = float(pixels / mask.size) if mask.size else 0.0
    return {"mask_pixels": pixels, "mask_fraction": round(fraction, 6)}


def run_pipeline(
    image: np.ndarray,
    steps: list[Any],
    models: Any = None,
) -> PipelineResult:
    """Execute les etapes dans l'ordre et renvoie le resultat complet.

    models permet de fournir un registre ONNX deja configure (chemin des modeles,
    sessions ouvertes) pour les etapes dl.unet_* ; sinon le registre partage du
    package est utilise. Une etape en echec leve StepError avec son kind, un
    pipeline invalide leve PipelineError avant toute execution.
    """
    array = np.asarray(image)
    if array.ndim not in (2, 3):
        raise PipelineError(f"Image attendue en 2 ou 3 dimensions, recu {array.ndim}")
    prepared = validate_steps(steps)
    current: np.ndarray = array
    last_mask: np.ndarray | None = None
    results: list[StepResult] = []
    aggregate: dict[str, Any] = {}
    total_ms = 0.0

    for spec, params in prepared:
        start = perf_counter()
        try:
            if spec.apply_with_models is not None and models is not None:
                output, diagnostics = spec.apply_with_models(current, params, models)
            else:
                output, diagnostics = spec.apply(current, params)
        except ModelMissingError:
            raise
        except Exception as error:
            raise StepError(spec.kind, str(error)) from error
        duration_ms = (perf_counter() - start) * 1000.0
        total_ms += duration_ms
        output = np.asarray(output)
        step_diagnostics = dict(diagnostics) if diagnostics else None
        results.append(StepResult(spec.kind, params, round(duration_ms, 3), step_diagnostics))
        current = output
        if spec.output == "mask":
            last_mask = to_mask(output)
            aggregate.update(_mask_stats(last_mask))
        if step_diagnostics:
            aggregate.update(step_diagnostics)

    aggregate["by_step"] = [
        {"kind": result.kind, "index": index, "diagnostics": result.diagnostics}
        for index, result in enumerate(results)
    ]
    aggregate["step_count"] = len(results)
    return PipelineResult(
        mask=last_mask,
        steps=results,
        total_ms=round(total_ms, 3),
        image=current,
        diagnostics=aggregate,
    )


def schema() -> dict[str, Any]:
    """Alias de pipeline_schema(), pour les clients qui importent pipeline.schema."""
    return pipeline_schema()
