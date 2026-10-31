# lumen_cv

Coeur de traitement d'images de Lumen : pretraitement, segmentation classique,
contours, recalage, mesures et inference U-Net ONNX. Le package ne depend
d'aucun framework web (ni FastAPI ni SQLAlchemy) et expose des fonctions pures
sur des tableaux numpy.

## Installation et tests

Depuis `packages/cv`, avec le Python du depot :

```bash
cd packages/cv
../../.venv/Scripts/python.exe -m pytest -q
```

Les donnees de test sont dans `tests/data/` (frame442 et son masque, 100 images
de sequence en 128 x 128, une paire FIRE reduite de moitie, une image
d'endoscopie et son masque). La suite dure environ une minute : le test du
MeanShift tourne sur l'image entiere.

## Utilisation

```python
from lumen_cv import io, metrics, pipeline

image = io.read_image("tests/data/frame442.png")   # RGB uint8, HxWx3
steps = [
    {"kind": "preprocess.median", "params": {"ksize": 5}},
    {"kind": "preprocess.gray", "params": {}},
    {"kind": "segment.watershed", "params": {}},
    {"kind": "postprocess.open", "params": {"ksize": 3}},
    {"kind": "postprocess.largest_component", "params": {}},
]
result = pipeline.run_pipeline(image, steps)
result.mask          # uint8 HxW, valeurs 0/1, None si aucune segmentation
result.steps         # kind, params effectifs, duration_ms, diagnostics
result.total_ms
result.diagnostics   # seuil Otsu, classes, pixels du masque, trace par etape
```

`pipeline.pipeline_schema()` renvoie le catalogue complet en JSON Schema :
libelle francais, categorie, entree, sortie, type, bornes et valeur par defaut
de chaque parametre. `lumen_cv.registry.STEP_CATALOGUE` donne le meme contenu
sous forme d'objets Python.

`lumen_cv.registry.presets()` (aussi `lumen_cv.presets()`) renvoie les cinq
chaines pretes a l'emploi de la plateforme, avec libelles francais et anglais,
description, image attendue (`asset_hint`), etapes et scores de reference :

| id | etapes | Dice / IoU attendus |
|---|---|---|
| `otsu` | gray, otsu inverse, ouverture, plus grande composante | 0,086 / 0,045 |
| `kmeans` | kmeans k=3, ouverture, plus grande composante | 0,461 / 0,300 |
| `watershed` | gray, watershed, ouverture, plus grande composante | 0,907 / 0,829 |
| `chan-vese` | chan_vese recadre | 0,484 / 0,319 |
| `unet` | unet_endoscopie, plus grande composante | 0,959 / 0,921 |

`kmeans` et `chan-vese` n'incluent pas `preprocess.gray` : ces methodes
travaillent sur la couleur, une conversion prealable change leur partition
(Dice 0,38 au lieu de 0,46 pour k-means).

Etapes disponibles : `preprocess.gray`, `preprocess.median`,
`preprocess.gaussian`, `preprocess.mean`, `preprocess.clahe`,
`segment.threshold`, `segment.otsu`, `segment.kmeans`, `segment.meanshift`,
`segment.chan_vese`, `segment.watershed`, `contours.sobel`,
`contours.laplace`, `contours.morph_gradient`, `postprocess.open`,
`postprocess.close`, `postprocess.largest_component`,
`postprocess.fill_holes`, `dl.unet_endoscopie`, `dl.unet_busi`.

## Conventions

- Images couleur en **RGB** uint8, images en niveaux de gris en HxW. Les
  fonctions acceptent les deux et convertissent au besoin.
- Masques en uint8 HxW valant **0 ou 1** ; les fonctions acceptent aussi les
  masques booleens et 0/255.
- Erreurs : `PipelineError` (pipeline invalide, code `pipeline_invalid`),
  `StepError` (echec d'une etape, code `step_failed`, attribut `kind`),
  `ModelMissingError` (sous-classe de `StepError`, code `model_missing`).

## Mesures et recalage

```python
from lumen_cv import metrics, registration

metrics.evaluate(mask, reference)   # dice, iou, recall, precision
metrics.dice(a, b)                  # IoU = Dice / (2 - Dice)

result = registration.register(fixed, moving, method="homography")
result.transform                    # 3 x 3, appliquee a l'image mobile
result.warped
result.metrics                      # ncc, mse, nmi (histogramme joint 64 x 64)
result.confidence                   # 0 a 1 : score NCC ou part d'inliers
registration.landmark_error(result.transform, points)  # points [x1, y1, x2, y2]
```

Methodes : `translation` (correlation de phase), `affine` et `homography`
(SIFT reciprocite 0.9, RANSAC ou USAC_MAGSAC), `optical_flow` (Farneback sur
l'image de travail au quart, points textures, affine robuste, ramenee en pleine
resolution). La transformation amene toujours l'image mobile dans le repere de
la fixe. Le champ dense est dans `result.flow`, a l'echelle de l'image de
travail (hauteur / 4, largeur / 4, 2).

## Modeles ONNX

`dl.ModelRegistry()` charge `models/unet_endoscopie.onnx` et
`models/unet_busi.onnx` (recherche dans `models/` a la racine du depot, ou dans
`LUMEN_MODELS_DIR`). `dl.models_available()` renvoie
`{"endoscopie": bool, "busi": bool}`.

Le pretraitement est celui du TP4 et n'est pas negociable : niveaux de gris,
redimensionnement 256 x 256, normalisation L2 le long des lignes
(`keras.utils.normalize(axis=1)`), repetition sur trois canaux. Une division par
255 donne un masque vide. Le modele endoscopie est entraine sur des images de
larynx a cadrage serre : `frame442.png` est hors distribution pour lui, utiliser
les methodes classiques sur cette image.

## Valeurs de reference des tests

| Mesure | Valeur | Test |
|---|---|---|
| k-means sur frame442, Dice | 0.461 | `test_kmeans_dice_reference` |
| Chan-Vese recadre, Dice | 0.484 | `test_chan_vese_cropped_dice_reference` |
| Watershed par defaut + post-traitement, Dice | 0.907 | `test_watershed_pipeline_default_locks_dice_above_080` |
| MeanShift, duree | 52 s | `test_meanshift_runs_under_two_minutes` |
| Seuil d'Otsu | 116 | `test_otsu_threshold_is_plausible` |
| Sequence de 100 images, reprise du cycle | image 14 | `test_sequence_detects_the_cycle_restart` |
| FIRE S01, erreur moyenne des landmarks (homographie) | 3.5 px | `test_fire_homography_landmark_error` |
| FIRE S01, erreur moyenne des landmarks (flot optique) | 5.8 px | `test_optical_flow_landmark_error_stays_under_ten_pixels` |
| U-Net endoscopie sur 00001, Dice | 0.959 | `test_endoscopie_model_reaches_training_dice` |
