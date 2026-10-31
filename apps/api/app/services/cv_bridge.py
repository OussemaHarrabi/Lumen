"""Adaptateur unique vers lumen_cv, importe paresseusement.

Le package de traitement est developpe en parallele : l'API ne doit jamais echouer
a l'import si `lumen_cv` est absent ou incomplet, elle renvoie une erreur du contrat.
"""

from __future__ import annotations

import copy
import importlib
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import numpy as np

from app.config import REPO_ROOT, get_settings
from app.errors import ApiError
from app.services import imaging

settings = get_settings()
logger = logging.getLogger("lumen.cv")

_module: Any | None = None
_import_error: ApiError | None = None

_DL_MODELS = {
    "dl.unet_endoscopie": ("endoscopie", "unet_endoscopie.onnx"),
    "dl.unet_busi": ("busi", "unet_busi.onnx"),
}


@dataclass
class StepReport:
    kind: str
    params: dict[str, Any]
    duration_ms: float
    diagnostics: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind,
            "params": self.params,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.diagnostics:
            payload["diagnostics"] = self.diagnostics
        return payload


@dataclass
class PipelineOutcome:
    image: np.ndarray
    mask: np.ndarray | None
    diagnostics: dict[str, Any]
    steps: list[StepReport]
    total_ms: float = 0.0


@dataclass
class RegistrationOutcome:
    transform: list[list[float]]
    warped: np.ndarray
    metrics: dict[str, Any] = field(default_factory=dict)
    method: str = "translation"
    confidence: float | None = None


def _load() -> Any:
    global _module, _import_error
    if _module is not None:
        return _module
    if _import_error is not None:
        raise _import_error
    try:
        _module = importlib.import_module("lumen_cv")
    except ImportError:
        local = REPO_ROOT / "packages" / "cv"
        if local.is_dir() and str(local) not in sys.path:
            sys.path.insert(0, str(local))
        try:
            _module = importlib.import_module("lumen_cv")
        except Exception as exc:
            _import_error = ApiError(
                "step_failed",
                "Le moteur de traitement lumen_cv n'est pas disponible.",
                {"detail": str(exc)},
                503,
            )
            raise _import_error from exc
    return _module


def available() -> bool:
    try:
        _load()
    except ApiError:
        return False
    return True


def _attr(module: Any, name: str) -> Any:
    value = getattr(module, name, None)
    if value is None:
        raise ApiError("step_failed", f"lumen_cv.{name} est indisponible.", {"module": name}, 503)
    return value


def _translate(exc: Exception, kind: str | None = None) -> ApiError:
    if isinstance(exc, ApiError):
        return exc
    name = type(exc).__name__
    detail = {"detail": str(exc)}
    if kind:
        detail["kind"] = kind
    if name == "ModelMissingError":
        return ApiError("model_missing", str(exc) or "Modèle de segmentation introuvable.", detail, 503)
    if name == "PipelineError":
        return ApiError("pipeline_invalid", str(exc), detail, 422)
    if name == "StepError":
        return ApiError("step_failed", f"L'étape {kind} a échoué : {exc}", detail)
    return ApiError("step_failed", str(exc) or "Échec du traitement.", detail)


def models_available() -> dict[str, bool]:
    """Presence des modeles ONNX, sans dependre de lumen_cv."""
    result = {key: (settings.models_dir / filename).is_file() for key, filename in _DL_MODELS.values()}
    try:
        module = _load()
        dl = getattr(module, "dl", None)
        if dl is not None and hasattr(dl, "models_available"):
            reported = dl.models_available()
            if isinstance(reported, dict):
                for key in ("endoscopie", "busi"):
                    if key in reported:
                        result[key] = bool(reported[key])
    except ApiError:
        pass
    except Exception:
        logger.debug("Detection des modeles via lumen_cv impossible", exc_info=True)
    return result


_presets_cache: list[dict[str, Any]] | None = None


def presets() -> list[dict[str, Any]]:
    """Presets de pipeline de lumen_cv.registry.presets(), lus une seule fois.

    Une liste vide n'est pas mise en cache: si le package est mis a jour a chaud,
    la route suivante voit les presets sans redemarrer l'API.
    """
    global _presets_cache
    if _presets_cache is not None:
        return copy.deepcopy(_presets_cache)
    try:
        module = _load()
    except ApiError:
        return []
    reader = None
    registry = getattr(module, "registry", None)
    if registry is not None:
        reader = getattr(registry, "presets", None)
    if not callable(reader):
        reader = getattr(module, "presets", None)
    if not callable(reader):
        return []
    try:
        raw = reader()
    except Exception:
        logger.debug("Lecture des presets impossible", exc_info=True)
        return []
    if not isinstance(raw, (list, tuple)):
        return []
    cleaned = [dict(item) for item in raw if isinstance(item, dict)]
    if cleaned:
        _presets_cache = cleaned
    return copy.deepcopy(cleaned)


def pipeline_schema() -> dict[str, Any]:
    module = _load()
    pipeline = _attr(module, "pipeline")
    for name in ("pipeline_schema", "schema", "schema_dict"):
        fn = getattr(pipeline, name, None)
        if callable(fn):
            try:
                return fn()
            except Exception as exc:
                raise _translate(exc) from exc
    raise ApiError("step_failed", "Le schéma du pipeline est indisponible.", None, 503)


def _catalogue(schema: dict[str, Any]) -> dict[str, Any]:
    catalogue = schema.get("catalogue")
    if isinstance(catalogue, dict) and catalogue:
        return catalogue
    raise ApiError("pipeline_invalid", "Le schéma du pipeline ne décrit aucune étape.", None, 503)


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def _coerce(value: Any, spec: dict[str, Any]) -> Any:
    expected = str(spec.get("type", ""))
    if expected == "number" and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    return value


def validate_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Valide le pipeline contre le catalogue de lumen_cv et remplit les defauts."""
    if not steps:
        raise ApiError("pipeline_invalid", "Le pipeline doit contenir au moins une étape.")
    catalogue = _catalogue(pipeline_schema())
    normalized: list[dict[str, Any]] = []

    for position, step in enumerate(steps):
        kind = step.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ApiError(
                "pipeline_invalid",
                "Chaque étape doit avoir un champ kind.",
                {"index": position},
            )
        entry = catalogue.get(kind)
        if not isinstance(entry, dict):
            raise ApiError(
                "pipeline_invalid",
                f"Étape inconnue : {kind}.",
                {"index": position, "kind": kind, "available": sorted(catalogue)},
            )
        specs = entry.get("params") or {}
        provided = step.get("params") or {}
        if not isinstance(provided, dict):
            raise ApiError(
                "pipeline_invalid",
                f"Les paramètres de {kind} doivent être un objet.",
                {"index": position, "kind": kind},
            )
        unknown = sorted(set(provided) - set(specs))
        if unknown:
            raise ApiError(
                "pipeline_invalid",
                f"Paramètres inconnus pour {kind} : {', '.join(unknown)}.",
                {"index": position, "kind": kind, "params": unknown},
            )
        effective: dict[str, Any] = {}
        for name, spec in specs.items():
            spec = spec if isinstance(spec, dict) else {}
            if name in provided:
                value = _coerce(provided[name], spec)
            elif "default" in spec:
                value = spec["default"]
            elif spec.get("required"):
                raise ApiError(
                    "pipeline_invalid",
                    f"Paramètre requis manquant pour {kind} : {name}.",
                    {"index": position, "kind": kind, "param": name},
                )
            else:
                continue
            expected = str(spec.get("type", ""))
            if expected and not _type_ok(value, expected):
                raise ApiError(
                    "pipeline_invalid",
                    f"Paramètre {name} de {kind} : type attendu {expected}.",
                    {"index": position, "kind": kind, "param": name, "value": value},
                )
            minimum = spec.get("minimum")
            maximum = spec.get("maximum")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if minimum is not None and value < minimum:
                    raise ApiError(
                        "pipeline_invalid",
                        f"Paramètre {name} de {kind} : minimum {minimum}.",
                        {"index": position, "kind": kind, "param": name, "value": value},
                    )
                if maximum is not None and value > maximum:
                    raise ApiError(
                        "pipeline_invalid",
                        f"Paramètre {name} de {kind} : maximum {maximum}.",
                        {"index": position, "kind": kind, "param": name, "value": value},
                    )
            choices = spec.get("enum")
            if isinstance(choices, list) and value not in choices:
                raise ApiError(
                    "pipeline_invalid",
                    f"Paramètre {name} de {kind} : valeur non autorisée.",
                    {"index": position, "kind": kind, "param": name, "value": value},
                )
            effective[name] = value
        normalized.append({"kind": kind, "params": effective})
    return normalized


def _step_params(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    return dict(getattr(raw, "params", {}) or {})


def run_pipeline(
    image_rgb: np.ndarray,
    steps: list[dict[str, Any]],
    on_step: Callable[[int, int, str], None] | None = None,
) -> PipelineOutcome:
    """Execute les etapes une a une pour exposer la progression et les durees."""
    module = _load()
    pipeline = _attr(module, "pipeline")
    runner = getattr(pipeline, "run_pipeline", None)
    if not callable(runner):
        raise ApiError("step_failed", "lumen_cv.pipeline.run_pipeline est indisponible.", None, 503)

    models = models_available()
    current = image_rgb
    mask: np.ndarray | None = None
    diagnostics: dict[str, Any] = {}
    reports: list[StepReport] = []
    total = len(steps)
    started = perf_counter()

    for index, step in enumerate(steps):
        kind = step["kind"]
        model = _DL_MODELS.get(kind)
        if model is not None and not models.get(model[0], False):
            raise ApiError(
                "model_missing",
                f"Le modèle {model[1]} est introuvable.",
                {"kind": kind, "model": model[1]},
                503,
            )
        if on_step is not None:
            on_step(index, total, kind)
        step_started = perf_counter()
        try:
            result = runner(current, [step])
        except Exception as exc:
            raise _translate(exc, kind) from exc
        measured = (perf_counter() - step_started) * 1000.0

        produced = getattr(result, "image", None)
        if produced is not None:
            current = produced
        step_mask = getattr(result, "mask", None)
        if step_mask is not None:
            mask = imaging.normalize_mask(step_mask)

        global_diagnostics = getattr(result, "diagnostics", None)
        step_reports = getattr(result, "steps", None) or []
        reported = step_reports[0] if step_reports else None
        step_diag = getattr(reported, "diagnostics", None)
        for source in (global_diagnostics, step_diag):
            if isinstance(source, dict):
                diagnostics.update(source)

        duration = float(getattr(reported, "duration_ms", 0.0) or 0.0) or measured
        effective = _step_params(reported) or dict(step.get("params") or {})
        reports.append(
            StepReport(
                kind=kind,
                params=effective,
                duration_ms=duration,
                diagnostics=step_diag if isinstance(step_diag, dict) else None,
            )
        )

    total_ms = (perf_counter() - started) * 1000.0
    if mask is not None and mask.shape[:2] != current.shape[:2]:
        mask = imaging.resize_mask(mask, current.shape[:2])
    return PipelineOutcome(
        image=current,
        mask=mask,
        diagnostics=diagnostics,
        steps=reports,
        total_ms=total_ms,
    )


def evaluate(pred: np.ndarray, reference: np.ndarray) -> dict[str, float | None]:
    module = _load()
    metrics_module = getattr(module, "metrics", None)
    if metrics_module is None:
        raise ApiError("step_failed", "lumen_cv.metrics est indisponible.", None, 503)
    pred_binary = imaging.normalize_mask(pred)
    ref_binary = imaging.normalize_mask(reference)
    try:
        if hasattr(metrics_module, "evaluate"):
            raw = metrics_module.evaluate(pred_binary, ref_binary)
            if isinstance(raw, dict):
                return {key: _float(raw.get(key)) for key in ("dice", "iou", "recall", "precision")}
        return {
            key: _float(getattr(metrics_module, key)(pred_binary, ref_binary))
            for key in ("dice", "iou", "recall", "precision")
        }
    except Exception as exc:
        raise _translate(exc) from exc


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def register(
    fixed_rgb: np.ndarray,
    moving_rgb: np.ndarray,
    method: str,
    params: dict[str, Any] | None = None,
) -> RegistrationOutcome:
    module = _load()
    registration = getattr(module, "registration", None)
    if registration is None or not hasattr(registration, "register"):
        raise ApiError("registration_failed", "Le recalage n'est pas encore disponible.", None, 503)
    try:
        result = registration.register(fixed_rgb, moving_rgb, method=method, params=params or {})
    except Exception as exc:
        raise _translate(exc) from exc
    transform = getattr(result, "transform", None)
    warped = getattr(result, "warped", None)
    if transform is None or warped is None:
        raise ApiError("registration_failed", "Le recalage n'a produit aucun résultat.", None, 500)
    matrix = np.asarray(transform, dtype=np.float64)
    metrics = getattr(result, "metrics", None) or {}
    confidence = getattr(result, "confidence", None)
    return RegistrationOutcome(
        transform=[[float(value) for value in row] for row in matrix.tolist()],
        warped=np.asarray(warped),
        metrics={key: _float(metrics.get(key)) for key in ("ncc", "mse", "nmi") if key in metrics},
        method=str(getattr(result, "method", method)),
        confidence=_float(confidence) if confidence is not None else None,
    )


def landmark_error(transform: list[list[float]], points: list[list[float]]) -> dict[str, Any]:
    module = _load()
    registration = getattr(module, "registration", None)
    if registration is None or not hasattr(registration, "landmark_error"):
        raise ApiError("registration_failed", "Le calcul d'erreur n'est pas disponible.", None, 503)
    matrix = np.asarray(transform, dtype=np.float64)
    coordinates = np.asarray(points, dtype=np.float64)
    try:
        raw = registration.landmark_error(matrix, coordinates)
    except Exception as exc:
        raise _translate(exc) from exc
    if not isinstance(raw, dict):
        raise ApiError("registration_failed", "Erreur de landmarks illisible.", None, 500)
    per_point = [float(value) for value in raw.get("per_point", [])]
    success = sum(1 for value in per_point if value <= 10.0)
    return {
        "mean": _float(raw.get("mean")),
        "median": _float(raw.get("median")),
        "max": _float(raw.get("max")),
        "per_point": per_point,
        "success_rate": (success / len(per_point) * 100.0) if per_point else None,
    }
