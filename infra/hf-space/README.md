---
title: Lumen API
emoji: 🩺
colorFrom: teal
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# API Lumen

Service FastAPI de la plateforme **Lumen** (analyse d'images médicales : prétraitement, segmentation
conventionnelle, segmentation profonde U-Net, recalage).

- Santé : `GET /api/health` renvoie la version et la présence des deux modèles ONNX.
- Contrat complet : `/openapi.json`, `/docs`.
- Traitement : package `lumen_cv` (OpenCV, scikit-image, scikit-learn, ONNX Runtime), sans dépendance web.
- Stockage : disque éphémère du Space (`/tmp/lumen`), aucune donnée conservée entre deux redémarrages.
  Les images d'exemple sont copiées à la demande dans la session, donc rien ne manque au démarrage.

## Variables d'environnement

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `LUMEN_CORS_ORIGIN` | vide | origine supplémentaire autorisée (l'interface passe par un proxy same-origin) |
| `LUMEN_MAX_UPLOAD_BYTES` | 25 Mo | taille maximale d'un téléversement |
| `LUMEN_STORAGE_DIR` | `/tmp/lumen/storage` | dossier des images et des résultats |
| `LUMEN_DATABASE_URL` | `sqlite:////tmp/lumen/lumen.db` | base SQLite |

## Notes d'exploitation

Le Space gratuit s'endort après une période d'inactivité : le premier appel après réveil prend quelques
secondes et l'état de session précédent est perdu, ce qui est acceptable pour une démonstration.
