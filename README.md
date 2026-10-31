# Lumen

Plateforme web d'analyse et de traitement d'images médicales : prétraitement, segmentation conventionnelle,
segmentation par apprentissage profond, recalage, et comparaison chiffrée des résultats.

Elle rassemble en une seule application les six ateliers du module *Traitement d'images médicales*
(Sup'Com, INDP3) : lecture et description d'image, prétraitement, segmentation conventionnelle, U-Net,
recalage, et la plateforme elle-même.

## Modules

| Module | Méthodes | Atelier |
|---|---|---|
| Ingestion | import image, extraction de séquence, métadonnées | 1 |
| Prétraitement | médian, gaussien, moyenneur, CLAHE, niveaux de gris | 2 |
| Segmentation | seuil manuel, Otsu, k-means, MeanShift, watershed, level-set Chan-Vese, morphologie | 2 et 3 |
| Contours | Sobel, Laplacien, gradient morphologique, extraction et superposition | 2 |
| Profond | U-Net ONNX (endoscopie des cordes vocales, échographie mammaire BUSI) | 4 |
| Recalage | translation, affine, homographie, flot optique, NCC, MSE, NMI, erreur sur landmarks | 5 |
| Évaluation | Dice, IoU, rappel, précision, durées par étape | 3 et 4 |
| Comparaison | grille multi-résultats, curseur avant et après, tableau de mesures | 6 |

## Pile

- Web : Next.js 16 (App Router), TypeScript, Tailwind v4, rendu d'image sur canvas maison.
- API : FastAPI, SQLAlchemy, SQLite en développement (PostgreSQL possible), tâches de fond et SSE.
- Traitement : package Python `lumen_cv` (OpenCV, scikit-image, scikit-learn, ONNX Runtime), sans dépendance web.
- Modèles : deux U-Net convertis en ONNX, conversion vérifiée numériquement à 4e-6 près.
- Déploiement : web sur Vercel, API sur Render (ou en Docker), détail dans `docs/DEPLOY.md`.

## Démarrage rapide

```bash
# 1. dépendances Python (un venv avec accès aux paquets système suffit)
python -m venv .venv --system-site-packages
.venv/Scripts/python.exe -m pip install -r apps/api/requirements.txt

# 2. dépendances web
pnpm install

# 3. API sur http://localhost:8000
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000 --app-dir apps/api

# 4. interface sur http://localhost:3000
pnpm dev
```

Ou tout en Docker :

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

## Tests

```bash
.venv/Scripts/python.exe -m pytest packages/cv/tests -q      # cœur de traitement
.venv/Scripts/python.exe -m pytest apps/api/tests -q         # API
pnpm --filter web build && pnpm --filter web lint            # interface
```

## Structure

```
apps/web/           interface Next.js
apps/api/           API FastAPI, stockage local, tâches de fond
packages/cv/        lumen_cv : traitement d'images pur, testé
packages/contracts/ schéma OpenAPI exporté et types TypeScript générés
models/             modèles ONNX (unet_endoscopie, unet_busi) et leur fiche de conversion
infra/              docker compose, Dockerfiles
docs/               architecture, feuille de route, contrat d'interface
PRODUCT.md          utilisateurs, personnalité, principes
DESIGN.md           système visuel
```

## Déploiement

### API sur Render (plan gratuit, sans carte)

1. Compte GitHub, puis `New` et `Blueprint` sur render.com, choisir ce dépôt.
2. `render.yaml` décrit le service : Docker depuis `apps/api/Dockerfile`, santé sur `/api/health`.
3. Vérifier `/api/health` sur l'URL fournie. Disque éphémère, réveil au premier appel après une pause.

Railway (inscriptions fermées) et Hugging Face Spaces (Spaces Docker payants sur matériel gratuit) sont
écartés. Sans hébergeur, un tunnel local (`cloudflared`) donne une URL publique temporaire : voir
`docs/DEPLOY.md`.

### Web sur Vercel

1. Importer le dépôt, **dossier racine `apps/web`**.
2. Variable : `NEXT_PUBLIC_API_URL` = URL publique de l'API, lue à la construction (le proxy `/lum-api`
   est figé dans le build). L'interface passe par ce proxy same-origin, donc aucun réglage CORS.
3. Déployer, puis vérifier un exemple et une analyse depuis l'URL Vercel.

### Tout en Docker

`infra/docker-compose.yml` lance l'API et l'interface, avec un volume pour la base et les fichiers.
Pour un nom de domaine et HTTPS automatique, ajouter Caddy devant les deux services.

## Données

Les images d'exemple embarquées proviennent des ateliers : `frame442.png` et son masque du cours,
une image endoscopique et son masque du jeu du TP4, une image BUSI, et une paire rétinienne FIRE avec ses
landmarks. Aucune image n'est envoyée à un service externe : l'inférence tourne localement en ONNX Runtime.
