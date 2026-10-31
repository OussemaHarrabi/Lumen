"""Inference des U-Net exportes en ONNX.

Deux modeles sont livres dans lumen/models :

- unet_endoscopie.onnx, entraine sur le jeu endoscopie du TP4 (images de
  larynx, cadrage serre) ;
- unet_busi.onnx, entraine sur BUSI (echographies mammaires).

Les deux ont la meme entree (None, 256, 256, 3), une sortie 1 canal sigmoide et
acceptent une image en niveaux de gris ou en couleur. Le pretraitement reproduit
celui du TP4 : niveaux de gris, redimensionnement 256 x 256, normalisation L2
le long des lignes (keras.utils.normalize(axis=1)), puis repetition sur trois
canaux. Toute autre normalisation (division par 255 par exemple) produit un
masque vide.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import cv2
import numpy as np

from .errors import ModelMissingError
from .io import to_gray
from .segment import largest_component, open_mask

MODEL_FILES = {
    "endoscopie": "unet_endoscopie.onnx",
    "busi": "unet_busi.onnx",
}

MODEL_DESCRIPTIONS = {
    "endoscopie": {
        "file": "unet_endoscopie.onnx",
        "trained_on": "Jeu endoscopie du TP4 (larynx, cadrage serre), images 256 x 256.",
        "input": "Image en niveaux de gris ou RGB, taille quelconque.",
        "note": "Hors distribution pour des images d'une autre video ou d'un autre cadrage.",
    },
    "busi": {
        "file": "unet_busi.onnx",
        "trained_on": "Jeu BUSI (echographies mammaires), images 256 x 256.",
        "input": "Image en niveaux de gris ou RGB, taille quelconque.",
        "note": "Concu pour les echographies : inutile sur des images d'endoscopie.",
    },
}

INPUT_SIZE = 256


def _candidate_dirs() -> list[Path]:
    """Dossiers candidats pour les modeles, du plus prioritaire au moins."""
    candidates: list[Path] = []
    configured = os.environ.get("LUMEN_MODELS_DIR")
    if configured:
        candidates.append(Path(configured))
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / "models")
    return candidates


def default_models_dir() -> Path:
    """Dossier des modeles : variable LUMEN_MODELS_DIR, sinon models/ du depot."""
    for candidate in _candidate_dirs():
        if any((candidate / filename).exists() for filename in MODEL_FILES.values()):
            return candidate
    return _candidate_dirs()[-1]


def preprocess_unet(image: np.ndarray) -> np.ndarray:
    """Entree du reseau : (1, 256, 256, 3) float32 normalisee par lignes.

    Etapes : niveaux de gris, redimensionnement 256 x 256, normalisation L2
    le long de l'axe des lignes (keras.utils.normalize(axis=1)) puis repetition
    sur trois canaux.
    """
    gray = to_gray(image)
    resized = cv2.resize(gray, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
    array = resized.astype(np.float32)[None, :, :, None]
    squared = np.sum(array ** 2, axis=1, keepdims=True)
    array = array / np.sqrt(np.maximum(squared, 1e-7))
    return np.repeat(array, 3, axis=-1).astype(np.float32)


def postprocess_mask(probability: np.ndarray, threshold: float) -> np.ndarray:
    """Seuillage, ouverture 3 x 3 puis plus grande composante connexe."""
    mask = (probability >= float(threshold)).astype(np.uint8)
    if mask.any():
        mask, _ = open_mask(mask, 3)
        mask = largest_component(mask)
    return mask


class ModelRegistry:
    """Charge et execute paresseusement les U-Net ONNX presents sur le disque.

    Une session ONNX Runtime par modele, en CPU, partagee entre les appels. Le
    chargement est protege par un verrou pour rester sur avec plusieurs threads.
    """

    def __init__(self, models_dir: str | Path | None = None) -> None:
        self.models_dir = Path(models_dir) if models_dir is not None else default_models_dir()
        self._sessions: dict[str, object] = {}
        self._lock = threading.Lock()

    def path(self, name: str) -> Path:
        """Chemin du fichier ONNX d'un modele."""
        if name not in MODEL_FILES:
            raise KeyError(f"Modele inconnu : {name}")
        return self.models_dir / MODEL_FILES[name]

    def available(self) -> dict[str, bool]:
        """Presence des deux modeles sur le disque."""
        return {name: self.path(name).exists() for name in MODEL_FILES}

    def load(self, name: str):
        """Session ONNX Runtime du modele, chargee au premier appel."""
        with self._lock:
            if name in self._sessions:
                return self._sessions[name]
            path = self.path(name)
            if not path.exists():
                raise ModelMissingError(name, path)
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
            session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
            self._sessions[name] = session
            return session

    def predict(
        self,
        name: str,
        image: np.ndarray,
        threshold: float = 0.5,
        postprocess: bool = True,
    ) -> tuple[np.ndarray, dict]:
        """Masque predit (uint8 0/1) et diagnostics."""
        if name not in MODEL_FILES:
            raise KeyError(f"Modele inconnu : {name}")
        session = self.load(name)
        gray = to_gray(image)
        height, width = gray.shape
        inputs = preprocess_unet(gray)
        input_name = session.get_inputs()[0].name
        output = session.run(None, {input_name: inputs})[0]
        probability = np.asarray(output).reshape(INPUT_SIZE, INPUT_SIZE)
        resized = cv2.resize(probability, (width, height), interpolation=cv2.INTER_LINEAR)
        if postprocess:
            mask = postprocess_mask(resized, threshold)
        else:
            mask = (resized >= float(threshold)).astype(np.uint8)
        diagnostics = {
            "model": name,
            "threshold": float(threshold),
            "probability_mean": round(float(resized.mean()), 4),
            "probability_max": round(float(resized.max()), 4),
            "mask_pixels": int(mask.sum()),
            "postprocess": bool(postprocess),
        }
        return mask, diagnostics


_default_registry: ModelRegistry | None = None
_default_lock = threading.Lock()


def default_registry() -> ModelRegistry:
    """Registre partage, cree au premier appel."""
    global _default_registry
    with _default_lock:
        if _default_registry is None:
            _default_registry = ModelRegistry()
        return _default_registry


def models_available() -> dict[str, bool]:
    """{"endoscopie": bool, "busi": bool} selon les fichiers presents."""
    return default_registry().available()


def predict(name: str, image: np.ndarray, threshold: float = 0.5) -> tuple[np.ndarray, dict]:
    """Inference sur le registre partage, avec post-traitement."""
    return default_registry().predict(name, image, threshold=threshold)
