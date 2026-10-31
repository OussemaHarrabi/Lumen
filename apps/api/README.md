# API Lumen

API FastAPI de la plateforme d'analyse d'images médicales. Elle expose les ressources de la session
anonyme (images, masques), lance les pipelines de `lumen_cv` en tâche de fond, calcule les métriques et
sert les masques, superpositions et vues de recalage en PNG.

Le contrat d'interface (routes, DTO, codes d'erreur) est décrit dans `docs/CONTRACT.md`. Ce document
n'ajoute que ce qui est propre au déploiement de l'API.

## Lancement local

Depuis la racine du dépôt, avec l'interpréteur du dépôt :

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --reload --app-dir apps/api
```

Depuis `apps/api` :

```bash
../../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --reload
```

`lumen_cv` est importé paresseusement. Si le paquet n'est pas installé, `app/services/cv_bridge.py`
ajoute `packages/cv` au `sys.path` (mode développement). Si l'import échoue malgré tout, l'API démarre
normalement, `GET /api/schema/pipeline` et `POST /api/analyses` renvoient une erreur `step_failed` (503)
au format du contrat, et les autres routes (assets, démos, santé) restent utilisables.

Documentation interactive : `http://localhost:8000/docs`.

## Variables d'environnement

Toutes les variables sont lues avec le préfixe `LUMEN_`, sauf `CORS_ORIGIN`.

| Variable | Défaut | Rôle |
|---|---|---|
| `LUMEN_DATABASE_URL` | `sqlite:///<racine>/lumen.db` | URL SQLAlchemy ; SQLite par défaut |
| `LUMEN_STORAGE_DIR` | `<racine>/storage` | Racine des fichiers, un dossier par session |
| `LUMEN_MODELS_DIR` | `<racine>/models` | Modèles ONNX `unet_endoscopie.onnx`, `unet_busi.onnx` |
| `LUMEN_DEMOS_DIR` | `apps/api/app/demos` | Catalogue des démonstrations embarquées |
| `LUMEN_MAX_UPLOAD_BYTES` | `26214400` (25 Mo) | Taille maximale d'un fichier |
| `LUMEN_MAX_IMAGE_DIMENSION` | `12000` | Côté maximal accepté à l'import |
| `LUMEN_WORKER_THREADS` | `2` | Threads du pool de traitement |
| `LUMEN_SESSION_COOKIE` | `lum_session` | Nom du cookie de session |
| `LUMEN_SESSION_MAX_AGE` | `15552000` (180 jours) | Durée de vie du cookie |
| `LUMEN_SESSION_COOKIE_SECURE` | `false` | À passer à `true` derrière HTTPS |
| `CORS_ORIGIN` | vide | Origine supplémentaire autorisée (liste séparée par des virgules) |
| `PORT` | `8000` | Port d'écoute dans le conteneur |

`http://localhost:3000` est toujours autorisé pour le front en développement.

## Routes

Toutes les routes sont préfixées par `/api`. Les erreurs suivent le format
`{"error": {"code", "message", "details"}}`.

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | État, version, disponibilité des deux modèles ONNX |
| POST | `/assets` | Multipart `file` + `kind` (`image` ou `mask`), type réel vérifié par entête |
| GET | `/assets` | Assets de la session |
| GET | `/assets/{id}` | Détail d'un asset |
| GET | `/assets/{id}/file` | Fichier d'origine, `Cache-Control: private, max-age=3600` |
| DELETE | `/assets/{id}` | Suppression du fichier et de la ligne |
| GET | `/demos` | Quatre démonstrations embarquées (libellés fr/en, parties, landmarks) |
| GET | `/demos/{slug}/file/{part}` | Fichier d'une démonstration (aperçu) |
| POST | `/demos/{slug}/asset` | Copie une partie de la démo dans la session (`?part=mask` par exemple) |
| GET | `/presets` | Presets de pipeline de `lumen_cv.registry.presets()`, liste vide si indisponible |
| POST | `/analyses` | Crée une analyse (`asset_id`, `reference_mask_id?`, `steps[]`), 202 |
| GET | `/analyses` | 50 dernières analyses de la session |
| GET | `/analyses/{id}` | Statut, progression, message d'étape, résumé |
| GET | `/analyses/{id}/result` | Masque, superposition, diagnostics, métriques, durées (404 avant la fin) |
| GET | `/analyses/{id}/mask.png` | Masque binaire du pipeline |
| GET | `/analyses/{id}/overlay.png` | Superposition du masque sur l'image d'origine |
| DELETE | `/analyses/{id}` | Suppression de l'analyse et de ses rendus |
| GET | `/jobs/{id}/events` | SSE `progress` / `done` / `error`, analyse ou recalage |
| POST | `/registrations` | Paire fixe/mobile et méthode, 202 |
| GET | `/registrations/{id}` | Statut, matrice, métriques, URLs des rendus |
| POST | `/registrations/{id}/landmarks` | Points `[[x1, y1, x2, y2], ...]`, erreur moyenne et taux de succès à 10 px |
| GET | `/registrations/{id}/overlay.png` | Mélange fixe/mobile recalée |
| GET | `/registrations/{id}/checkerboard.png` | Damier fixe/mobile recalée |
| GET | `/schema/pipeline` | JSON Schema du catalogue d'étapes, servi par `lumen_cv` |

### Détails utiles au front

- Le pipeline renvoyé par `GET /analyses/{id}` contient les paramètres effectifs (défauts remplis).
- `mask_url` et `overlay_url` valent `null` si le pipeline ne produit aucun masque.
- `success_rate` est un pourcentage (0 à 100) de points sous 10 pixels d'erreur.
- `registrations[].metrics.confidence` (0 à 1) vient de `lumen_cv` et mesure la qualité de l'appariement.
- Les URL de fichiers sont relatives (`/api/...`) : le client les préfixe par `NEXT_PUBLIC_API_URL`.

### Démonstrations embarquées

| slug | Contenu | Usage |
|---|---|---|
| `endoscopie-cours` | frame 442 + masque glotte | seuillage, k-means, morphologie, level-set |
| `endoscopie-unet` | image du jeu U-Net + masque | segmentation profonde (Dice proche de 0,95) |
| `mammaire-busi` | échographie BUSI + masque | modèle BUSI et comparaison |
| `retines-fire` | paire FIRE A01 (1024 px) + 10 points de contrôle | recalage |

Les fichiers sont stockés dans `app/demos/{slug}/` avec un manifeste `demo.json`.

Copie dans la session : `POST /api/demos/{slug}/asset?part=<nom>`, où `<nom>` est un des `parts` renvoyés
par `GET /api/demos` (`image`, `mask`, `fixed`, `moving`). Sans `part`, la première partie du manifeste est
copiée. Le `kind` de l'asset copié est celui de la partie : `POST /api/demos/endoscopie-cours/asset?part=mask`
crée un asset `mask`, utilisable comme `reference_mask_id`.

`GET /api/presets` relaie les presets de `lumen_cv.registry.presets()` (identifiant, libellés fr/en,
description, `asset_hint`, `steps` et `expected`). Les `steps` sont directement utilisables dans
`POST /api/analyses`, sur l'asset indiqué par `asset_hint`. La réponse est mise en cache au premier appel
non vide et vaut `[]` tant que le module de traitement n'expose pas `presets()`.

## Exécution des traitements

`POST /analyses` et `POST /registrations` écrivent une ligne `queued` puis rendent la main en moins de
500 ms. Un pool de threads interne (`JobRunner`) exécute le pipeline étape par étape : chaque étape met à
jour `progress` et `message` en base, ce qui alimente le SSE et l'interrogation périodique. Les erreurs
de `lumen_cv` sont traduites dans les codes du contrat : `ModelMissingError` en `model_missing`,
`StepError` en `step_failed`, `PipelineError` en `pipeline_invalid`.

## Base et stockage

- SQLite `lumen.db` à la racine (WAL activé), tables créées au démarrage (`assets`, `analyses`,
  `registrations`). Chaque ligne est rattachée à `session_id`, il n'y a pas de comptes.
- Fichiers : `storage/{session}/{asset_id}{ext}` et `storage/{session}/results/{job_id}_mask.png`,
  `_overlay.png`, `_checkerboard.png`. Rien n'est servi depuis un dossier public.

## Tests

```bash
.venv/Scripts/python.exe -m pytest apps/api/tests -q
```

Les tests couvrent la santé, le cookie de session, l'isolation entre deux clients, le téléversement et
les métadonnées, le refus de type et de taille, les démos, le pipeline complet sur l'image de
démonstration (avec métriques), le flux SSE, les erreurs de pipeline et le recalage. Les tests qui
exigent `lumen_cv` sont ignorés si le paquet n'est pas importable.

## Docker et Railway

```bash
docker build -f apps/api/Dockerfile -t lumen-api .
docker run --rm -p 8000:8000 -v lumen-data:/data lumen-api
```

Le contexte de build est la racine du dépôt : l'image installe `apps/api/requirements.txt` (versions
figées, dépendances de `lumen_cv` incluses), puis `packages/cv` sans dépendances, copie `apps/api` et les
deux modèles ONNX. `railway.json` (build Dockerfile `apps/api/Dockerfile`, healthcheck `/api/health`)
doit être référencé depuis la racine du dépôt dans Railway, ou le service doit pointer sur ce fichier de
configuration ; `RAILWAY_DOCKERFILE_PATH=apps/api/Dockerfile` suffit sinon.

Sur Railway, monter un volume sur `/data` pour conserver `lumen.db` et les fichiers entre déploiements.
