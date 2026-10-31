"""Assemble le contenu d'un Hugging Face Space (SDK Docker) pour l'API Lumen.

Usage : python infra/hf-space/assemble.py   (depuis la racine du dépôt)
Produit infra/hf-space/build/ prêt à être poussé sur le dépôt du Space.
"""
import shutil
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SORTIE = HERE / "build"

if SORTIE.exists():
    shutil.rmtree(SORTIE)
for dossier in ("apps", "packages", "models"):
    (SORTIE / dossier).mkdir(parents=True, exist_ok=True)

shutil.copy2(HERE / "Dockerfile", SORTIE / "Dockerfile")
shutil.copy2(HERE / "README.md", SORTIE / "README.md")
shutil.copy2(RACINE / "apps" / "api" / "requirements.txt", SORTIE / "requirements.txt")

shutil.copytree(RACINE / "packages" / "cv" / "lumen_cv", SORTIE / "packages" / "cv" / "lumen_cv")
shutil.copytree(RACINE / "apps" / "api" / "app", SORTIE / "apps" / "api" / "app")
for modele in ("unet_endoscopie.onnx", "unet_busi.onnx", "model_info.json"):
    shutil.copy2(RACINE / "models" / modele, SORTIE / "models" / modele)

taille = sum(f.stat().st_size for f in SORTIE.rglob("*") if f.is_file())
print("Space assemblé dans", SORTIE)
print("fichiers :", sum(1 for f in SORTIE.rglob("*") if f.is_file()), "| taille : %.1f Mo" % (taille / 1e6))
