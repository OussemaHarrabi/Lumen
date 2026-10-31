# Contrat d'interface Lumen

Ce document fixe ce que chaque partie du dépôt expose et consomme. Il fait foi : si une implémentation
s'écarte du contrat, c'est le contrat qui gagne, ou on le modifie explicitement ici.

## 1. Structure

```
apps/api/          FastAPI, base SQLite en développement, PostgreSQL possible en production
apps/web/          Next.js 16 (App Router), TypeScript, Tailwind v4
packages/cv/       lumen_cv, traitement d'images pur (aucune dépendance web)
packages/contracts/ schéma OpenAPI exporté et types TypeScript générés
infra/             docker compose, Dockerfiles, Caddy
docs/              architecture, feuille de route, ce contrat
```

Règles d'import : `lumen_cv` ne connaît ni FastAPI ni SQLAlchemy. `apps/api` importe `lumen_cv` et rien
de Next.js. `apps/web` n'appelle que l'API HTTP, jamais Python.

## 2. Format d'un pipeline

Une analyse est une liste ordonnée d'étapes :

```json
{
  "steps": [
    {"kind": "preprocess.median", "params": {"ksize": 5}},
    {"kind": "preprocess.gray", "params": {}},
    {"kind": "segment.otsu", "params": {"invert": false}},
    {"kind": "postprocess.open", "params": {"ksize": 3}},
    {"kind": "postprocess.largest_component", "params": {}}
  ]
}
```

### Étapes et paramètres

| kind | paramètres | sortie principale |
|---|---|---|
| `preprocess.gray` | aucun | image 1 canal |
| `preprocess.median` | `ksize` (impair, 3 à 31, défaut 5) | image filtrée |
| `preprocess.gaussian` | `ksize`, `sigma` (0 = auto) | image filtrée |
| `preprocess.mean` | `ksize` | image filtrée |
| `preprocess.clahe` | `clip` (1 à 8, défaut 2), `grid` (2 à 16, défaut 8) | images rehaussée |
| `segment.threshold` | `threshold` (0 à 255), `invert` (bool) | masque binaire |
| `segment.otsu` | `invert` (bool) | masque binaire + seuil trouvé |
| `segment.kmeans` | `k` (2 à 8, défaut 3), `seed` (défaut 42) | masque de la classe la plus sombre |
| `segment.meanshift` | `subsample` (1 à 9, défaut 3), `fov_restrict` (bool) | masque de la classe la plus sombre |
| `segment.chan_vese` | `iterations` (10 à 200), `smoothing`, `crop` (bool) | masque |
| `segment.watershed` | `marker_ratio` (0,4 à 1,0, défaut 0,5 : pourcentage des pixels les plus sombres du champ de vision servant de marqueurs) | masque |
| `contours.sobel` | aucun | carte de magnitude |
| `contours.laplace` | aucun | carte de réponse |
| `contours.morph_gradient` | `ksize` | carte de gradient |
| `postprocess.open` | `ksize` | masque nettoyé |
| `postprocess.close` | `ksize` | masque nettoyé |
| `postprocess.largest_component` | aucun | masque réduit à sa plus grande composante |
| `postprocess.fill_holes` | aucun | masque avec trous bouchés |
| `dl.unet_endoscopie` | `threshold` (0,3 à 0,7, défaut 0,5) | masque prédit |
| `dl.unet_busi` | `threshold` | masque prédit |

`GET /api/schema/pipeline` renvoie ce catalogue en JSON Schema (une entrée par étape, avec types, bornes et
valeurs par défaut). Le front génère les formulaires depuis cette réponse, sans liste codée en dur.

Chaque étape exécutée renvoie : `kind`, `params` effectifs, `duration_ms`, et éventuellement
`diagnostics` (seuil trouvé, nombre de classes, nombre de pixels du masque).

## 3. API REST

Base : `/api`. Toutes les réponses sont en JSON, erreurs incluses.

| Méthode | Route | Corps | Réponse |
|---|---|---|---|
| GET | `/health` | | `{status: "ok", version, models: {endoscopie: bool, busi: bool}}` |
| POST | `/assets` | multipart `file`, `kind` (`image` ou `mask`) | `Asset` 201 |
| GET | `/assets` | | `Asset[]` |
| GET | `/assets/{id}` | | `Asset` |
| GET | `/assets/{id}/file` | | binaire, `Cache-Control: private, max-age=3600` |
| DELETE | `/assets/{id}` | | 204 |
| GET | `/demos` | | `Demo[]` (images d'exemple embarquées) |
| POST | `/demos/{slug}/asset` | | `Asset` (copie de l'exemple dans la session) |
| POST | `/analyses` | `{asset_id, reference_mask_id?, steps[]}` | `Analysis` 202 |
| GET | `/analyses` | | `Analysis[]` (50 dernières) |
| GET | `/analyses/{id}` | | `Analysis` |
| GET | `/analyses/{id}/result` | | `AnalysisResult` (404 tant que non terminée) |
| DELETE | `/analyses/{id}` | | 204 |
| GET | `/jobs/{id}/events` | | SSE `text/event-stream` |
| POST | `/registrations` | `{fixed_asset_id, moving_asset_id, method, params?}` | `Registration` 202 |
| GET | `/registrations/{id}` | | `Registration` avec métriques |
| POST | `/registrations/{id}/landmarks` | `{points: [[x1, y1, x2, y2], ...]}` | `Registration` |
| GET | `/schema/pipeline` | | JSON Schema du catalogue d'étapes |
| GET | `/presets` | | `Preset[]` : chaînes prêtes à l'emploi (otsu, kmeans, watershed, chan-vese, unet) avec les scores attendus |

### Presets

`GET /presets` renvoie les cinq chaînes calibrées sur les ateliers :

```ts
type Preset = {
  id: "otsu" | "kmeans" | "watershed" | "chan-vese" | "unet";
  label_fr: string; label_en: string;
  description_fr: string; description_en: string;
  asset_hint: string | null;      // exemple à charger d'abord, par exemple "endoscopie-cours"
  steps: Step[];
  expected: { dice: number; iou: number } | null;
};
```

### DTO

```ts
type Asset = {
  id: string; kind: "image" | "mask";
  filename: string; width: number; height: number;
  channels: number; bytes: number;
  created_at: string;
  meta?: { dtype?: string; mean?: number; min?: number; max?: number; mask_fraction?: number };
};

type Analysis = {
  id: string; asset_id: string; reference_mask_id: string | null;
  steps: Step[];
  status: "queued" | "running" | "done" | "error";
  progress: number;            // 0 à 1
  created_at: string; finished_at: string | null;
  error: string | null;
  summary: { dice?: number; iou?: number; recall?: number; precision?: number; total_ms?: number } | null;
};

type Step = { kind: string; params: Record<string, unknown> };

type AnalysisResult = {
  analysis_id: string;
  mask_url: string;
  overlay_url: string;
  diagnostics: Record<string, unknown>;
  metrics: { dice: number | null; iou: number | null; recall: number | null; precision: number | null } | null;
  steps: { kind: string; params: Record<string, unknown>; duration_ms: number; diagnostics?: Record<string, unknown> }[];
  total_ms: number;
};

type Registration = {
  id: string; fixed_asset_id: string; moving_asset_id: string;
  method: "translation" | "affine" | "homography" | "optical_flow";
  status: "queued" | "running" | "done" | "error";
  metrics: { mean_landmark_error?: number; success_rate?: number; ncc?: number; mse?: number; nmi?: number } | null;
  transform: number[][] | null;   // matrice appliquée à l'image mobile
  overlay_url: string | null;
  checkerboard_url: string | null;
};
```

### SSE

`GET /api/jobs/{id}/events` renvoie :

```
event: progress
data: {"id":"...","status":"running","progress":0.42,"message":"segment.otsu"}

event: done
data: {"id":"...","status":"done","progress":1}
```

La connexion se ferme à `done` ou `error`. Un client qui n'utilise pas SSE peut interroger
`GET /api/analyses/{id}` toutes les 800 ms.

## 4. Session et stockage

- Pas de comptes. Un cookie `lum_session` (UUID v4, `httpOnly`, `SameSite=Lax`, 180 jours) identifie la
  session. Toutes les ressources sont rattachées à cette session.
- Fichiers stockés hors du dossier public, un dossier par session. Servis par `GET /assets/{id}/file`.
- Taille maximale par fichier : 25 Mo. Types acceptés : PNG, JPEG, TIFF, BMP. Le type réel est vérifié
  par lecture de l'entête, pas par l'extension.
- Dossiers : `storage/{session}/{asset_id}{ext}`, `storage/{session}/results/{analysis_id}_mask.png`.

## 5. Front

- Client HTTP typé généré depuis `packages/contracts/openapi.json` (`pnpm --filter web types`).
- Un seul module d'accès réseau (`apps/web/lib/api/client.ts`), qui préfixe `NEXT_PUBLIC_API_URL`.
- Toutes les chaînes visibles passent par le dictionnaire i18n (`apps/web/lib/i18n/fr.ts`, `en.ts`).
  Aucun texte en dur dans les composants.
- Les couleurs viennent uniquement des variables CSS déclarées dans `DESIGN.md`. Aucune valeur hexadécimale
  en dur dans un composant.

## 6. Erreurs

Format unique :

```json
{"error": {"code": "asset_too_large", "message": "Le fichier dépasse 25 Mo.", "details": {"bytes": 33000000}}}
```

Codes : `asset_too_large`, `unsupported_type`, `asset_not_found`, `pipeline_invalid`, `step_failed`,
`model_missing`, `registration_failed`, `landmarks_invalid`.
