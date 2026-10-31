"""Demonstration : pipeline complet sur frame442.png et metriques.

Lancement depuis packages/cv :

    ../../.venv/Scripts/python.exe examples/demo_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lumen_cv import io, metrics, pipeline

DATA = ROOT / "tests" / "data"

STEPS = [
    {"kind": "preprocess.median", "params": {"ksize": 5}},
    {"kind": "preprocess.gray", "params": {}},
    {"kind": "segment.watershed", "params": {}},
    {"kind": "postprocess.open", "params": {"ksize": 3}},
    {"kind": "postprocess.largest_component", "params": {}},
]


def main() -> None:
    image = io.read_image(DATA / "frame442.png")
    reference = io.to_gray(io.read_image(DATA / "frame442_glottis.png")) > 127

    start = perf_counter()
    result = pipeline.run_pipeline(image, STEPS)
    elapsed = perf_counter() - start

    scores = metrics.evaluate(result.mask, reference)
    print(f"Image : {image.shape[1]} x {image.shape[0]}, {len(STEPS)} etapes")
    for step in result.steps:
        print(f"  {step.kind:<34} {step.duration_ms:7.2f} ms")
    print(f"Total des etapes : {result.total_ms:.2f} ms, horloge : {elapsed * 1000:.2f} ms")
    print(f"Pixels du masque : {int(result.mask.sum())} ({result.mask.mean() * 100:.2f} %)")
    print(
        "Dice {dice:.3f} | IoU {iou:.3f} | rappel {recall:.3f} | precision {precision:.3f}".format(
            **scores
        )
    )
    print(f"Seuil d'Otsu utilise : {result.diagnostics['otsu_level']:.0f}")
    if elapsed >= 5.0:
        raise SystemExit("Le pipeline a depasse 5 secondes")


if __name__ == "__main__":
    main()
