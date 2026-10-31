"""Exceptions du package, alignees sur les codes d'erreur du contrat."""

from __future__ import annotations

from pathlib import Path


class StepError(RuntimeError):
    """Une etape a echoue a l'execution (code step_failed)."""

    code = "step_failed"

    def __init__(self, kind: str, message: str) -> None:
        self.kind = kind
        self.message = message
        super().__init__(f"{kind} : {message}")


class ModelMissingError(StepError):
    """Modele ONNX absent du disque (code model_missing)."""

    code = "model_missing"

    def __init__(self, name: str, path: Path | None = None) -> None:
        self.name = name
        self.path = path
        detail = f" ({path})" if path is not None else ""
        super().__init__(f"dl.unet_{name}", f"modele ONNX absent{detail}")


class PipelineError(ValueError):
    """Pipeline invalide : etape inconnue ou parametres hors bornes (code pipeline_invalid)."""

    code = "pipeline_invalid"

    def __init__(self, message: str, steps: list[str] | None = None) -> None:
        self.message = message
        self.steps = list(steps or [])
        super().__init__(message)
