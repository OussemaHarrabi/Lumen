"""Mesures du rapport atelier 6, lues sur l'API en marche.

Écrit deux fichiers lus par make_report_at6.py :
  build/at6_measures.json   cinq chaînes prêtes à l'emploi (Dice, IoU, durées)
  build/at6_recalage.json   trois méthodes de recalage sur la paire FIRE A01

Les scores viennent des réponses de l'API (POST /api/analyses et
POST /api/registrations), pas d'un calcul parallèle : le rapport cite donc ce que
l'application affiche. L'erreur de landmarks est calculée avec les dix points de
contrôle de la démonstration retines-fire, via lumen_cv.

Usage :  .venv/Scripts/python.exe build/measure_at6.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parent.parent
BUILD = RACINE / "build"
API = "http://127.0.0.1:8011/api"
FIRE = RACINE / "apps" / "api" / "app" / "demos" / "retines-fire"

sys.path.insert(0, str(RACINE / "packages" / "cv"))
from lumen_cv import registration  # noqa: E402

jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(methode: str, chemin: str, charge: dict | None = None):
    donnees = None if charge is None else json.dumps(charge).encode()
    requete = urllib.request.Request(API + chemin, data=donnees, method=methode)
    if donnees:
        requete.add_header("Content-Type", "application/json")
    try:
        with opener.open(requete, timeout=180) as reponse:
            brut = reponse.read()
            return json.loads(brut) if brut else None
    except urllib.error.HTTPError as erreur:
        print("HTTP", erreur.code, erreur.read().decode()[:400])
        raise


def attendre(chemin: str) -> dict:
    while True:
        courant = call("GET", chemin)
        if courant["status"] in ("done", "failed"):
            return courant
        time.sleep(0.02)


def mesurer_chaines() -> list[dict]:
    call("GET", "/health")
    presets = call("GET", "/presets")
    cours = call("POST", "/demos/endoscopie-cours/asset?part=image")
    cours_masque = call("POST", "/demos/endoscopie-cours/asset?part=mask")
    unet = call("POST", "/demos/endoscopie-unet/asset?part=image")
    unet_masque = call("POST", "/demos/endoscopie-unet/asset?part=mask")

    lignes = []
    for preset in presets:
        domaine = preset["id"] == "unet"
        corps = {
            "asset_id": unet["id"] if domaine else cours["id"],
            "reference_mask_id": unet_masque["id"] if domaine else cours_masque["id"],
            "steps": [{"kind": s["kind"], "params": s.get("params") or {}} for s in preset["steps"]],
        }
        debut = time.perf_counter()
        analyse = call("POST", "/analyses", corps)
        courant = attendre(f"/analyses/{analyse['id']}")
        mur = (time.perf_counter() - debut) * 1000.0
        if courant["status"] != "done":
            lignes.append({"id": preset["id"], "status": courant["status"]})
            continue
        resultat = call("GET", f"/analyses/{analyse['id']}/result")
        lignes.append(
            {
                "id": preset["id"],
                "label_fr": preset["label_fr"],
                "dice": round(resultat["metrics"]["dice"], 3),
                "iou": round(resultat["metrics"]["iou"], 3),
                "recall": round(resultat["metrics"]["recall"], 3),
                "precision": round(resultat["metrics"]["precision"], 3),
                "total_ms": round(resultat["total_ms"], 1),
                "wall_ms": round(mur, 1),
                "steps": [(s["kind"], round(s["duration_ms"], 1)) for s in resultat["steps"]],
                "image": "endoscopie-unet" if domaine else "endoscopie-cours",
            }
        )
    return lignes


def mesurer_recalage() -> list[dict]:
    fixe = call("POST", "/demos/retines-fire/asset?part=fixed")
    mobile = call("POST", "/demos/retines-fire/asset?part=moving")
    manifeste = json.loads((FIRE / "demo.json").read_text(encoding="utf-8"))
    points = np.asarray(manifeste["landmarks"], dtype=float)

    lignes = []
    for methode in ("homography", "affine", "optical_flow"):
        debut = time.perf_counter()
        travail = call(
            "POST",
            "/registrations",
            {"fixed_asset_id": fixe["id"], "moving_asset_id": mobile["id"], "method": methode},
        )
        courant = attendre(f"/registrations/{travail['id']}")
        mur = (time.perf_counter() - debut) * 1000.0
        mesure = call("POST", f"/registrations/{travail['id']}/landmarks", {"points": points.tolist()})
        metriques = mesure["metrics"]
        lignes.append(
            {
                "method": methode,
                "mean": round(metriques["mean_landmark_error"], 2),
                "success": round(metriques["success_rate"] / 100.0, 4),
                "ncc": round(metriques["ncc"], 3),
                "mse": round(metriques["mse"], 1),
                "nmi": round(metriques["nmi"], 3),
                "confidence": round(metriques["confidence"], 3),
                "wall_ms": round(mur, 1),
                "points": int(points.shape[0]),
                "transform": np.round(np.asarray(courant["transform"], dtype=float), 4).tolist(),
            }
        )
    return lignes


def mesurer_paquet() -> list[dict]:
    """Mêmes méthodes sur la paire de test du paquet, erreur ramenée à la pleine résolution."""
    import cv2

    dossier = RACINE / "packages" / "cv" / "tests" / "data" / "fire"
    fixe = cv2.imread(str(dossier / "S01_1.jpg"), cv2.IMREAD_GRAYSCALE)
    mobile = cv2.imread(str(dossier / "S01_2.jpg"), cv2.IMREAD_GRAYSCALE)
    points = np.loadtxt(dossier / "S01_points.txt").reshape(-1, 4)

    lignes = []
    for methode in ("homography", "affine", "optical_flow"):
        resultat = registration.register(fixe, mobile, methode)
        erreurs = registration.landmark_error(resultat.transform, points)
        lignes.append(
            {
                "method": methode,
                "mean_full_res": round(float(erreurs["mean"]) * 2.0, 2),
                "success": round(float(erreurs["success_rate"]), 4),
                "ncc": round(resultat.metrics["ncc"], 3),
            }
        )
    return lignes


def main() -> int:
    chaines = mesurer_chaines()
    recalage = {"demo": mesurer_recalage(), "package": mesurer_paquet()}
    BUILD.mkdir(exist_ok=True)
    (BUILD / "at6_measures.json").write_text(
        json.dumps({"presets": chaines}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (BUILD / "at6_recalage.json").write_text(
        json.dumps(recalage, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({"presets": chaines, "recalage": recalage}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
