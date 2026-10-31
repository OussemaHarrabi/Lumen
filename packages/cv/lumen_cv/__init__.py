"""Traitement d'images medicales conventionnel et profond pour Lumen.

Le package ne depend d'aucun framework web : il expose des fonctions pures sur
des tableaux numpy, un catalogue d'etapes serialisable en JSON Schema et un
executeur de pipeline.
"""

from . import contours, dl, metrics, preprocess, registration, segment
from .io import read_image, write_image
from .pipeline import (
    PipelineError,
    PipelineResult,
    StepError,
    pipeline_schema,
    run_pipeline,
    schema,
)
from .registry import presets

__version__ = "0.1.0"

__all__ = [
    "PipelineError",
    "PipelineResult",
    "StepError",
    "contours",
    "dl",
    "metrics",
    "pipeline_schema",
    "preprocess",
    "presets",
    "read_image",
    "registration",
    "run_pipeline",
    "schema",
    "segment",
    "write_image",
]
