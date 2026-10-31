"""Convertit les deux modeles U-Net Keras (.h5) en ONNX pour la plateforme Lumen."""
import glob
import json
import os
import pathlib
import subprocess
import sys

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tf2onnx", "onnxruntime", "onnx"], check=True)

import numpy as np
import onnxruntime as ort
import tensorflow as tf
import tf2onnx

SORTIE = pathlib.Path("/kaggle/working")
SORTIE.mkdir(parents=True, exist_ok=True)

print("Contenu de /kaggle/input :", os.listdir("/kaggle/input"))
trouves = sorted(glob.glob("/kaggle/input/**/*.h5", recursive=True))
print("Modeles trouves :", trouves)

MODELES = {}
for chemin in trouves:
    nom = os.path.basename(chemin)
    if "endoscopie" in nom and "ep50" in nom:
        MODELES["endoscopie"] = pathlib.Path(chemin)
    if "busi" in nom and "ep50" in nom:
        MODELES["busi"] = pathlib.Path(chemin)
print("Modeles retenus :", {k: str(v) for k, v in MODELES.items()})

infos = {}
for nom, chemin in MODELES.items():
    print("=== conversion :", nom, "|", chemin.stat().st_size, "octets")
    modele = tf.keras.models.load_model(str(chemin), compile=False)
    print("  entree :", modele.input_shape, "| parametres :", modele.count_params())

    specification = (tf.TensorSpec((None, 256, 256, 3), tf.float32, name="input"),)
    fichier = SORTIE / ("unet_%s.onnx" % nom)
    onnx_modele, _ = tf2onnx.convert.from_keras(modele, input_signature=specification, opset=17)
    with open(fichier, "wb") as f:
        f.write(onnx_modele.SerializeToString())
    print("  ONNX ecrit :", fichier.name, fichier.stat().st_size, "octets")

    rng = np.random.default_rng(0)
    entree = rng.random((1, 256, 256, 3), dtype=np.float32)
    sortie_keras = modele.predict(entree, verbose=0)
    session = ort.InferenceSession(str(fichier), providers=["CPUExecutionProvider"])
    nom_entree = session.get_inputs()[0].name
    sortie_onnx = session.run(None, {nom_entree: entree})[0]
    ecart = float(np.abs(sortie_keras - sortie_onnx).max())
    print("  ecart max Keras/ONNX : %.3e" % ecart)

    infos[nom] = {
        "fichier": fichier.name,
        "octets": fichier.stat().st_size,
        "entree_keras": str(modele.input_shape),
        "entree_onnx": nom_entree,
        "sortie_onnx": session.get_outputs()[0].name,
        "parametres": int(modele.count_params()),
        "ecart_max_keras_onnx": ecart,
    }

(SORTIE / "model_info.json").write_text(json.dumps(infos, indent=2, ensure_ascii=False), encoding="utf-8")
print("=== FIN ===")
print(json.dumps(infos, indent=2))
