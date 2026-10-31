# Lumen : architecture technique

Plateforme web d'analyse d'images médicales (prétraitement, segmentation conventionnelle, segmentation
profonde, recalage) qui capitalise sur les six ateliers du module *Traitement d'images médicales*.

## 1. Périmètre fonctionnel

| Module | Ce que fait la plateforme | Atelier source |
|---|---|---|
| Ingestion | import image / vidéo, extraction de séquence, métadonnées (taille, canaux, dtype, histogramme) | 1 |
| Prétraitement | filtres moyenneur, médian, gaussien, égalisation et CLAHE, réduction de bruit, conversion en niveaux de gris | 2 |
| Segmentation conventionnelle | seuillage manuel et Otsu, k-means, MeanShift, morphologie (ouverture, fermeture, gradient), contours (Sobel, Laplacien, gradient morphologique), watershed, level-set Chan-Vese | 2 et 3 |
| Segmentation profonde | inférence U-Net ONNX (modèle endoscopie et modèle BUSI), seuil de probabilité, morphologie de nettoyage | 4 |
| Recalage | paire d'images, translation, affine, homographie, flot optique, mesures de similarité (NCC, MSE, NMI), erreur sur landmarks | 5 |
| Évaluation | Dice, IoU, rappel, précision, temps de calcul contre un masque de référence | 3 et 4 |
| Comparaison | grille multi-résultats, curseur avant/après, superposition, flicker, tableau de métriques | 6 |
| Traçabilité | historique des analyses, paramètres utilisés, export PNG / JSON / ZIP, rapport PDF | 6 |

## 2. Pile technique

### Web (`apps/web`)

- Next.js 15 (App Router, React 19, TypeScript strict), Tailwind CSS v4 avec tokens OKLCH, primitives
  Radix UI pour l'accessibilité, composants maison pour tout ce qui est visuel (pas de thème générique).
- État : TanStack Query pour l'état serveur, Zustand pour l'état d'interface (outils actifs, calques).
- Rendu d'images : composant `ImageCanvas` maison sur `<canvas>` (rendu DPR-aware, pan/zoom, calques
  masque et contour, opacité, lecture de pixel au curseur, fenêtrage). Aucune bibliothèque de viewer
  externe pour garder le contrôle du rendu et des performances.
- Formulaires de paramètres générés depuis un schéma de pipeline décrit par l'API (JSON Schema par étape),
  donc ajouter une méthode de segmentation ne demande aucune modification du front.
- Types TS générés depuis `openapi.json` (openapi-typescript + openapi-fetch) : une seule source de vérité.

### API (`apps/api`)

- FastAPI (Python 3.13), Pydantic v2, SQLAlchemy 2 + Alembic, uvicorn.
- Authentification : JWT en cookie httpOnly, rafraîchissement, hachage Argon2, rôles `user` et `admin`.
- API REST versionnée, contrat OpenAPI exposé et testé (Schemathesis en complément des tests manuels).
- Les traitements lourds ne bloquent jamais la requête : `POST /analyses` crée une tâche, renvoie un
  `job_id`, et le client suit l'avancement par SSE (`GET /jobs/{id}/events`) ou par interrogation.

### Traitement d'images (`packages/cv`)

Package Python autonome, sans dépendance web, testé unitairement :

```
lumen_cv/
  io/            lecture, écriture, conversions BGR/RGB, vidéo vers séquence
  preprocess/    filtres, CLAHE, débruitage
  segment/       seuillage, otsu, kmeans, meanshift, watershed, chan_vese, morphologie
  contours/      sobel, laplace, gradient morphologique, extraction de contours
  metrics/       dice, iou, rappel, precision, matrice de confusion
  registration/  translation, affine, homographie, flot optique, ncc, mse, nmi, erreur landmarks
  dl/            inférence ONNX U-Net (endoscopie, BUSI), post-traitement
  pipeline/      exécution ordonnée d'étapes + traçage des durées
```

Chaque étape est une fonction pure `(image, params) -> (image_resultat, meta)` avec métadonnées
(durée, taille de sortie, paramètres effectifs). Les résultats lourds sont stockés, pas recalculés.

### File d'attente et stockage

- Redis 7 + RQ pour les tâches longues (watershed, MeanShift, level-set, inférence, recalage par lot).
- MinIO en développement, compatible S3 en production : images sources, masques, overlays, exports,
  servis au navigateur par URL présignée (le front ne télécharge pas les fichiers via l'API).

### Base de données (PostgreSQL 16)

```
users            (id, email, password_hash, display_name, role, created_at)
assets           (id, user_id, kind, storage_key, filename, width, height, channels, dtype, bytes, meta jsonb)
analyses         (id, user_id, asset_id, reference_mask_id, pipeline jsonb, status, started_at, finished_at, error, summary jsonb)
steps            (id, analysis_id, position, kind, params jsonb, duration_ms, output jsonb)
results          (id, analysis_id, mask_key, overlay_key, metrics jsonb)
registrations    (id, user_id, fixed_asset_id, moving_asset_id, method, params jsonb, transform jsonb, metrics jsonb)
landmarks        (id, registration_id, points jsonb)
demo_assets      (id, slug, label, description, storage_key, kind)
```

### Déploiement

- `infra/docker-compose.yml` : web, api, worker, postgres, redis, minio, caddy (TLS automatique).
- `infra/Caddyfile` : reverse proxy `/api` vers l'API, tout le reste vers Next.js.
- CI GitHub Actions : tests du package `lumen_cv`, tests API, build du front, Playwright sur les
  parcours critiques.

## 3. Parcours utilisateur

1. **Accueil** : présentation, démonstration immédiate sur une image d'exemple (traitement côté client
   pour les filtres simples, côté API pour la segmentation), accès à l'atelier.
2. **Espace de travail** : chargement d'une image (ou d'un exemple), choix du pipeline, réglage des
   paramètres, exécution, résultats superposés, métriques, comparaison avec une autre exécution.
3. **Comparaison** : grille de résultats (conventionnel contre profond), curseur de superposition,
   tableau Dice / IoU / temps.
4. **Recalage** : deux images, choix de la transformation, points de contrôle, erreur moyenne, vues
   fusionnées (mélange, damier, clignotement).
5. **Historique** : liste des analyses, réouverture, réutilisation des paramètres, export.

## 4. Choix techniques justifiés

- **Canvas plutôt que `<img>` + CSS** : le rendu des masques et contours à l'échelle du pixel, le zoom
  lissé et la lecture de valeur au curseur sont impossibles à tenir proprement en CSS.
- **ONNX Runtime plutôt que TensorFlow dans l'API** : 350 Mo de roue TensorFlow pour 8 Mo d'ONNX, un
  conteneur 10 fois plus léger, et l'inférence U-Net 256 x 256 prend quelques dizaines de millisecondes.
  Les modèles Keras du TP4 sont convertis une fois sur Kaggle (tf2onnx) et versionnés dans `models/`.
- **File d'attente RQ** : MeanShift et le level-set prennent de quelques secondes à une minute ; le
  traitement doit survivre à la fermeture de l'onglet et être réutilisable par plusieurs utilisateurs.
- **Contrat OpenAPI** : le front est généré depuis l'API, donc renommer un paramètre casse la
  compilation TypeScript au lieu de casser silencieusement l'interface.

## 5. Modèles embarqués

| Modèle | Entrée | Sortie | Fichier |
|---|---|---|---|
| U-Net endoscopie | 256 x 256 x 3, normalisé | probabilité glottis | `models/unet_endoscopie.onnx` |
| U-Net BUSI | 256 x 256 x 3, normalisé | probabilité lésion | `models/unet_busi.onnx` |

Conversion vérifiée numériquement (écart maximal Keras / ONNX consigné dans `models/model_info.json`).

## 6. Sécurité et vie privée

- Téléversements limités (taille, type MIME réel vérifié, dimensions maximales), noms de fichiers
  neutralisés, stockage hors du dossier web.
- Images considérées comme données de santé : accès authentifié, URL présignées à durée courte, aucun
  service tiers, suppression immédiate possible par l'utilisateur.
- Aucune donnée envoyée à un modèle externe : l'inférence est locale (ONNX Runtime).
