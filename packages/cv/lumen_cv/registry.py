"""Catalogue des etapes de pipeline.

Chaque etape declare son type d'entree et de sortie, son libelle francais, ses
parametres (type, bornes, valeur par defaut) et une fonction d'application
`apply(image, params) -> (sortie, diagnostics)`. Le catalogue sert a la fois a
l'execution et a la generation des formulaires du front via JSON Schema.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import contours, dl, preprocess, segment

Apply = Callable[[Any, dict[str, Any]], tuple[Any, dict[str, Any]]]
ApplyWithModels = Callable[[Any, dict[str, Any], Any], tuple[Any, dict[str, Any]]]


@dataclass(frozen=True)
class ParamSpec:
    """Parametre d'une etape : type, bornes et valeur par defaut."""

    name: str
    type: str
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    description: str = ""

    def schema(self) -> dict[str, Any]:
        entry: dict[str, Any] = {"type": self.type, "default": self.default}
        if self.minimum is not None:
            entry["minimum"] = self.minimum
        if self.maximum is not None:
            entry["maximum"] = self.maximum
        if self.description:
            entry["description"] = self.description
        return entry

    def coerce(self, value: Any) -> Any:
        """Convertit et verifie une valeur venue du client."""
        if self.type == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, int) and value in (0, 1):
                return bool(value)
            raise ValueError(f"Le parametre {self.name} doit etre un booleen")
        if self.type == "integer":
            if isinstance(value, bool):
                raise ValueError(f"Le parametre {self.name} doit etre un entier")
            number = int(value)
            if float(value) != float(number):
                raise ValueError(f"Le parametre {self.name} doit etre un entier")
        else:
            if isinstance(value, bool):
                raise ValueError(f"Le parametre {self.name} doit etre un nombre")
            number = float(value)
        if self.minimum is not None and number < self.minimum:
            raise ValueError(
                f"Le parametre {self.name} doit etre superieur ou egal a {self.minimum:g} (recu {number:g})"
            )
        if self.maximum is not None and number > self.maximum:
            raise ValueError(
                f"Le parametre {self.name} doit etre inferieur ou egal a {self.maximum:g} (recu {number:g})"
            )
        return number


def _kernel(size: int = 3, label: str = "ksize") -> ParamSpec:
    return ParamSpec(
        name=label, type="integer", default=size, minimum=3, maximum=31,
        description="Taille du noyau, impaire, en pixels.",
    )


@dataclass
class StepSpec:
    """Une etape du catalogue."""

    kind: str
    label: str
    category: str
    input: str
    output: str
    params: tuple[ParamSpec, ...]
    apply: Apply
    apply_with_models: ApplyWithModels | None = None
    description: str = ""
    _param_map: dict[str, ParamSpec] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._param_map = {param.name: param for param in self.params}

    @property
    def defaults(self) -> dict[str, Any]:
        return {param.name: param.default for param in self.params}

    def coerce(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Parametres effectifs : defauts completes, types verifies, bornes controlees."""
        raw = dict(params or {})
        unknown = sorted(set(raw) - set(self._param_map))
        if unknown:
            raise ValueError(f"Parametres inconnus pour {self.kind} : {', '.join(unknown)}")
        effective: dict[str, Any] = {}
        for param in self.params:
            value = raw.get(param.name, param.default)
            if param.name.endswith("ksize") and int(value) % 2 == 0:
                raise ValueError(f"Le parametre {param.name} de {self.kind} doit etre impair")
            effective[param.name] = param.coerce(value)
        return effective

    def schema(self) -> dict[str, Any]:
        properties = {param.name: param.schema() for param in self.params}
        return {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
            "required": [],
        }

    def catalogue_entry(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "category": self.category,
            "input": self.input,
            "output": self.output,
            "description": self.description,
            "defaults": self.defaults,
            "params": {param.name: param.schema() for param in self.params},
        }


def _dl_apply(name: str) -> Apply:
    def apply(image: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        return dl.predict(name, image, threshold=params["threshold"])

    return apply


def _dl_apply_with(name: str) -> ApplyWithModels:
    def apply(image: Any, params: dict[str, Any], models: Any) -> tuple[Any, dict[str, Any]]:
        return models.predict(name, image, threshold=params["threshold"])

    return apply


def _apply_largest(image: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    mask = segment.largest_component(image)
    return mask, {"mask_pixels": int(mask.sum())}


def _apply_fill_holes(image: Any, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    mask = segment.fill_holes(image)
    return mask, {"mask_pixels": int((mask > 0).sum())}


def _steps() -> list[StepSpec]:
    """Les etapes du contrat, dans l'ordre des categories."""
    return [
        StepSpec(
            kind="preprocess.gray", label="Niveaux de gris", category="preprocess",
            input="image", output="image", params=(),
            apply=lambda image, params: preprocess.gray(image),
            description="Convertit l'image en luminance.",
        ),
        StepSpec(
            kind="preprocess.median", label="Filtre median", category="preprocess",
            input="image", output="image", params=(_kernel(5),),
            apply=lambda image, params: preprocess.median(image, params["ksize"]),
            description="Remplace chaque pixel par la mediane de son voisinage.",
        ),
        StepSpec(
            kind="preprocess.gaussian", label="Filtre gaussien", category="preprocess",
            input="image", output="image",
            params=(
                _kernel(5),
                ParamSpec(name="sigma", type="number", default=0.0, minimum=0.0, maximum=10.0,
                          description="Ecart type, 0 pour le deduire du noyau."),
            ),
            apply=lambda image, params: preprocess.gaussian(image, params["ksize"], params["sigma"]),
            description="Lissage gaussien.",
        ),
        StepSpec(
            kind="preprocess.mean", label="Filtre moyenneur", category="preprocess",
            input="image", output="image", params=(_kernel(5),),
            apply=lambda image, params: preprocess.mean(image, params["ksize"]),
            description="Moyenne glissante sur un voisinage carre.",
        ),
        StepSpec(
            kind="preprocess.clahe", label="CLAHE", category="preprocess",
            input="image", output="image",
            params=(
                ParamSpec(name="clip", type="number", default=2.0, minimum=1.0, maximum=8.0,
                          description="Limite de contraste."),
                ParamSpec(name="grid", type="integer", default=8, minimum=2, maximum=16,
                          description="Nombre de tuiles par cote."),
            ),
            apply=lambda image, params: preprocess.clahe(image, params["clip"], params["grid"]),
            description="Egalisation adaptative du contraste.",
        ),
        StepSpec(
            kind="segment.threshold", label="Seuillage manuel", category="segment",
            input="image", output="mask",
            params=(
                ParamSpec(name="threshold", type="integer", default=128, minimum=0, maximum=255,
                          description="Niveau de gris de coupure."),
                ParamSpec(name="invert", type="boolean", default=False,
                          description="Inverse le masque (pixels sombres)."),
            ),
            apply=lambda image, params: segment.threshold(image, params["threshold"], params["invert"]),
            description="Masque des pixels au-dessus (ou au-dessous) d'un seuil fixe.",
        ),
        StepSpec(
            kind="segment.otsu", label="Seuillage d'Otsu", category="segment",
            input="image", output="mask",
            params=(ParamSpec(name="invert", type="boolean", default=False,
                              description="Inverse le masque (pixels sombres)."),),
            apply=lambda image, params: segment.otsu(image, params["invert"]),
            description="Seuil automatique maximisant la variance inter-classes.",
        ),
        StepSpec(
            kind="segment.kmeans", label="k-means", category="segment",
            input="image", output="mask",
            params=(
                ParamSpec(name="k", type="integer", default=3, minimum=2, maximum=8,
                          description="Nombre de classes de couleur."),
                ParamSpec(name="seed", type="integer", default=42, minimum=0, maximum=2147483647,
                          description="Graine du tirage des centres initiaux."),
            ),
            apply=lambda image, params: segment.kmeans(image, params["k"], params["seed"]),
            description="Classe les pixels par couleur et garde la classe la plus sombre du champ de vision.",
        ),
        StepSpec(
            kind="segment.meanshift", label="MeanShift", category="segment",
            input="image", output="mask",
            params=(
                ParamSpec(name="subsample", type="integer", default=3, minimum=1, maximum=9,
                          description="Pas du sous-echantillonnage spatial pour apprendre les classes."),
                ParamSpec(name="fov_restrict", type="boolean", default=True,
                          description="Restreint l'analyse au champ de vision de l'endoscope."),
            ),
            apply=lambda image, params: segment.meanshift(image, params["subsample"], params["fov_restrict"]),
            description="Regroupe les pixels par densite, masque de la classe la plus sombre.",
        ),
        StepSpec(
            kind="segment.chan_vese", label="Contours actifs (Chan-Vese)", category="segment",
            input="image", output="mask",
            params=(
                ParamSpec(name="iterations", type="integer", default=50, minimum=10, maximum=200,
                          description="Nombre d'iterations du level-set."),
                ParamSpec(name="smoothing", type="number", default=3.0, minimum=0.0, maximum=10.0,
                          description="Regularisation du contour."),
                ParamSpec(name="crop", type="boolean", default=True,
                          description="Travaille sur une fenetre de 240 x 240 autour de la zone sombre."),
            ),
            apply=lambda image, params: segment.chan_vese(
                image, params["iterations"], params["smoothing"], params["crop"]
            ),
            description="Level-set morphologique initialise sur la zone sombre.",
        ),
        StepSpec(
            kind="segment.watershed", label="Watershed", category="segment",
            input="image", output="mask",
            params=(ParamSpec(name="marker_ratio", type="number", default=0.5, minimum=0.4, maximum=1.0,
                              description="Pourcentage des pixels du champ de vision les plus sombres "
                                          "utilises comme marqueurs (0,5 = les 0,5 % les plus sombres). "
                                          "Stable entre 0,4 et 1,0, Dice 0,90 sur frame442."),),
            apply=lambda image, params: segment.watershed(image, params["marker_ratio"]),
            description="Ligne de partage des eaux sur les marqueurs du gradient.",
        ),
        StepSpec(
            kind="contours.sobel", label="Sobel", category="contours",
            input="image", output="map", params=(),
            apply=lambda image, params: contours.sobel(image),
            description="Magnitude du gradient, utile pour visualiser les frontieres.",
        ),
        StepSpec(
            kind="contours.laplace", label="Laplacien", category="contours",
            input="image", output="map", params=(),
            apply=lambda image, params: contours.laplace(image),
            description="Reponse du Laplacien, sensible au bruit.",
        ),
        StepSpec(
            kind="contours.morph_gradient", label="Gradient morphologique", category="contours",
            input="image", output="map", params=(_kernel(3),),
            apply=lambda image, params: contours.morph_gradient(image, params["ksize"]),
            description="Dilatation moins erosion.",
        ),
        StepSpec(
            kind="postprocess.open", label="Ouverture", category="postprocess",
            input="mask", output="mask", params=(_kernel(3),),
            apply=lambda image, params: segment.open_mask(image, params["ksize"]),
            description="Retire les petites regions du masque.",
        ),
        StepSpec(
            kind="postprocess.close", label="Fermeture", category="postprocess",
            input="mask", output="mask", params=(_kernel(3),),
            apply=lambda image, params: segment.close_mask(image, params["ksize"]),
            description="Bouche les petits trous du masque.",
        ),
        StepSpec(
            kind="postprocess.largest_component", label="Plus grande composante", category="postprocess",
            input="mask", output="mask", params=(),
            apply=_apply_largest,
            description="Ne garde que la plus grande region connexe.",
        ),
        StepSpec(
            kind="postprocess.fill_holes", label="Remplissage des trous", category="postprocess",
            input="mask", output="mask", params=(),
            apply=_apply_fill_holes,
            description="Bouche les trous internes du masque.",
        ),
        StepSpec(
            kind="dl.unet_endoscopie", label="U-Net endoscopie", category="dl",
            input="image", output="mask",
            params=(ParamSpec(name="threshold", type="number", default=0.5, minimum=0.3, maximum=0.7,
                              description="Seuil sur la probabilite de la sigmoide."),),
            apply=_dl_apply("endoscopie"),
            apply_with_models=_dl_apply_with("endoscopie"),
            description="U-Net entraine sur le jeu endoscopie du TP4, images de larynx.",
        ),
        StepSpec(
            kind="dl.unet_busi", label="U-Net BUSI", category="dl",
            input="image", output="mask",
            params=(ParamSpec(name="threshold", type="number", default=0.5, minimum=0.3, maximum=0.7,
                              description="Seuil sur la probabilite de la sigmoide."),),
            apply=_dl_apply("busi"),
            apply_with_models=_dl_apply_with("busi"),
            description="U-Net entraine sur les echographies mammaires BUSI.",
        ),
    ]


STEP_CATALOGUE: dict[str, StepSpec] = {spec.kind: spec for spec in _steps()}


def get_step(kind: str) -> StepSpec:
    """Etape du catalogue, erreur explicite si le type est inconnu."""
    try:
        return STEP_CATALOGUE[kind]
    except KeyError:
        known = ", ".join(STEP_CATALOGUE)
        raise KeyError(f"Etape inconnue : {kind}. Etapes disponibles : {known}") from None


PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "otsu",
        "label_fr": "Seuillage d'Otsu inverse",
        "label_en": "Inverted Otsu threshold",
        "description_fr": "Seuil automatique d'Otsu inverse sur les niveaux de gris, puis ouverture et "
                          "plus grande composante. Retient le fond sombre, Dice de reference 0,09.",
        "description_en": "Inverted Otsu threshold on grayscale, then opening and largest component. "
                          "Keeps the dark background, reference Dice 0.09.",
        "asset_hint": "endoscopie-cours",
        "steps": [
            {"kind": "preprocess.gray", "params": {}},
            {"kind": "segment.otsu", "params": {"invert": True}},
            {"kind": "postprocess.open", "params": {"ksize": 3}},
            {"kind": "postprocess.largest_component", "params": {}},
        ],
        "expected": {"dice": 0.086, "iou": 0.045},
    },
    {
        "id": "kmeans",
        "label_fr": "k-means 3 classes",
        "label_en": "3-class k-means",
        "description_fr": "k-means a 3 classes sur les pixels couleur, classe la plus sombre du champ de "
                          "vision, ouverture et plus grande composante. Dice de reference 0,46.",
        "description_en": "3-class k-means on colour pixels, darkest class inside the field of view, "
                          "opening and largest component. Reference Dice 0.46.",
        "asset_hint": "endoscopie-cours",
        "steps": [
            {"kind": "segment.kmeans", "params": {"k": 3, "seed": 42}},
            {"kind": "postprocess.open", "params": {"ksize": 3}},
            {"kind": "postprocess.largest_component", "params": {}},
        ],
        "expected": {"dice": 0.461, "iou": 0.300},
    },
    {
        "id": "watershed",
        "label_fr": "Watershed sur le gradient",
        "label_en": "Gradient watershed",
        "description_fr": "Watershed controle par marqueurs sur la magnitude du gradient, ouverture et plus "
                          "grande composante. Dice de reference 0,91.",
        "description_en": "Marker-controlled watershed on gradient magnitude, opening and largest component. "
                          "Reference Dice 0.91.",
        "asset_hint": "endoscopie-cours",
        "steps": [
            {"kind": "preprocess.gray", "params": {}},
            {"kind": "segment.watershed", "params": {"marker_ratio": 0.5}},
            {"kind": "postprocess.open", "params": {"ksize": 3}},
            {"kind": "postprocess.largest_component", "params": {}},
        ],
        "expected": {"dice": 0.907, "iou": 0.829},
    },
    {
        "id": "chan-vese",
        "label_fr": "Contours actifs Chan-Vese",
        "label_en": "Chan-Vese active contours",
        "description_fr": "Level-set de Chan-Vese recadre sur 240 x 240 autour de la zone sombre trouvee par "
                          "k-means. Dice de reference 0,48.",
        "description_en": "Chan-Vese level set on a 240 x 240 crop around the dark region found by k-means. "
                          "Reference Dice 0.48.",
        "asset_hint": "endoscopie-cours",
        "steps": [
            {"kind": "segment.chan_vese", "params": {"crop": True}},
        ],
        "expected": {"dice": 0.484, "iou": 0.319},
    },
    {
        "id": "unet",
        "label_fr": "U-Net endoscopie",
        "label_en": "Endoscopy U-Net",
        "description_fr": "U-Net entraine sur le jeu endoscopie du TP4, seuil 0,5, puis plus grande "
                          "composante. Dice de reference 0,96 sur une image d'entrainement.",
        "description_en": "U-Net trained on the TP4 endoscopy set, threshold 0.5, then largest component. "
                          "Reference Dice 0.96 on a training image.",
        "asset_hint": "endoscopie-unet",
        "steps": [
            {"kind": "dl.unet_endoscopie", "params": {"threshold": 0.5}},
            {"kind": "postprocess.largest_component", "params": {}},
        ],
        "expected": {"dice": 0.959, "iou": 0.921},
    },
)


def presets() -> list[dict[str, Any]]:
    """Chaines pretes a l'emploi qui reproduisent les resultats des TP.

    Chaque preset porte son identifiant, ses libelles francais et anglais, sa
    description, l'image d'exemple attendue (asset_hint), les etapes a executer
    et les scores mesures sur l'image de reference (dice, iou). Les etapes de
    k-means et de Chan-Vese ne contiennent pas preprocess.gray : ces methodes
    travaillent sur la couleur, une conversion prealable change leur partition
    (Dice 0,38 au lieu de 0,46 pour k-means).
    """
    return copy.deepcopy(list(PRESETS))


def pipeline_schema() -> dict[str, Any]:
    """JSON Schema complet du catalogue, une entree par etape.

    La cle catalogue contient, pour chaque type d'etape, son libelle, sa
    categorie, son type d'entree et de sortie et le schema de ses parametres.
    Les etapes du tableau steps sont decrites en oneOf pour la validation.
    """
    variants = []
    for spec in STEP_CATALOGUE.values():
        variants.append({
            "title": spec.label,
            "type": "object",
            "properties": {
                "kind": {"const": spec.kind},
                "params": spec.schema(),
            },
            "required": ["kind"],
            "additionalProperties": False,
        })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Catalogue des etapes Lumen",
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "title": "Etapes du pipeline",
                "items": {"oneOf": variants},
            },
        },
        "required": ["steps"],
        "$defs": {"step": {"oneOf": variants}},
        "catalogue": {spec.kind: spec.catalogue_entry() for spec in STEP_CATALOGUE.values()},
    }
