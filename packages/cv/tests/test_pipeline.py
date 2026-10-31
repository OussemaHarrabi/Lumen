"""Pipeline : enchainement, parametres effectifs, durees et erreurs typees."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from lumen_cv import dl, metrics, pipeline
from lumen_cv.registry import STEP_CATALOGUE, pipeline_schema

STEPS = [
    {"kind": "preprocess.gaussian", "params": {"ksize": 5, "sigma": 0}},
    {"kind": "preprocess.gray", "params": {}},
    {"kind": "segment.watershed", "params": {}},
    {"kind": "postprocess.open", "params": {"ksize": 3}},
    {"kind": "postprocess.largest_component", "params": {}},
]


def test_pipeline_chains_image_segment_postprocess(
    frame442: np.ndarray, glottis: np.ndarray
) -> None:
    result = pipeline.run_pipeline(frame442, STEPS)

    assert isinstance(result, pipeline.PipelineResult)
    assert result.mask is not None
    assert result.mask.dtype == np.uint8
    assert set(np.unique(result.mask)) <= {0, 1}
    assert result.mask.shape == frame442.shape[:2]
    assert result.image.shape == frame442.shape[:2]
    assert result.total_ms < 5000.0
    assert metrics.dice(result.mask, glottis) > 0.80

    assert [step.kind for step in result.steps] == [step["kind"] for step in STEPS]
    assert all(step.duration_ms >= 0.0 for step in result.steps)
    assert result.total_ms == pytest.approx(sum(step.duration_ms for step in result.steps), abs=0.05)
    assert result.diagnostics["mask_pixels"] == int(result.mask.sum())
    assert result.diagnostics["marker_ratio"] == pytest.approx(0.5)
    assert len(result.diagnostics["by_step"]) == len(STEPS)


def test_effective_parameters_are_reported(frame442: np.ndarray) -> None:
    result = pipeline.run_pipeline(
        frame442,
        [{"kind": "preprocess.median", "params": {}}, {"kind": "preprocess.gray"}],
    )
    assert result.steps[0].params == {"ksize": 5}
    assert result.steps[1].params == {}
    assert result.mask is None
    assert result.image.ndim == 2


def test_mask_is_kept_when_a_contour_step_follows(frame442: np.ndarray) -> None:
    result = pipeline.run_pipeline(
        frame442,
        [{"kind": "segment.otsu", "params": {}}, {"kind": "contours.sobel", "params": {}}],
    )
    assert result.mask is not None
    assert result.mask.dtype == np.uint8
    assert result.image.dtype == np.float32
    assert result.diagnostics["by_step"][1]["kind"] == "contours.sobel"


def test_unknown_step_and_bad_parameters_are_rejected(frame442: np.ndarray) -> None:
    with pytest.raises(pipeline.PipelineError) as unknown:
        pipeline.run_pipeline(frame442, [{"kind": "segment.magique"}])
    assert "type inconnu" in str(unknown.value)

    with pytest.raises(pipeline.PipelineError) as bounds:
        pipeline.run_pipeline(frame442, [{"kind": "preprocess.median", "params": {"ksize": 4}}])
    assert "impair" in str(bounds.value)

    with pytest.raises(pipeline.PipelineError):
        pipeline.run_pipeline(frame442, [{"kind": "segment.kmeans", "params": {"k": 12}}])

    with pytest.raises(pipeline.PipelineError):
        pipeline.run_pipeline(frame442, [{"kind": "preprocess.median", "params": {"flou": 3}}])


def test_missing_model_raises_typed_step_error(frame442: np.ndarray, tmp_path: Path) -> None:
    registry = dl.ModelRegistry(tmp_path)
    with pytest.raises(pipeline.ModelMissingError) as error:
        pipeline.run_pipeline(
            frame442, [{"kind": "dl.unet_busi", "params": {"threshold": 0.5}}], models=registry
        )
    assert isinstance(error.value, pipeline.StepError)
    assert error.value.kind == "dl.unet_busi"
    assert error.value.code == "model_missing"


def test_runtime_failure_is_wrapped_with_the_kind() -> None:
    """Une image 1 x 1 ne permet pas 3 classes : l'erreur porte le kind de l'etape."""
    tiny = np.zeros((1, 1, 3), np.uint8)
    with pytest.raises(pipeline.StepError) as error:
        pipeline.run_pipeline(tiny, [{"kind": "segment.kmeans", "params": {"k": 3}}])
    assert error.value.kind == "segment.kmeans"
    assert error.value.code == "step_failed"


def test_schema_covers_the_contract_catalogue() -> None:
    expected = {
        "preprocess.gray", "preprocess.median", "preprocess.gaussian", "preprocess.mean",
        "preprocess.clahe", "segment.threshold", "segment.otsu", "segment.kmeans",
        "segment.meanshift", "segment.chan_vese", "segment.watershed", "contours.sobel",
        "contours.laplace", "contours.morph_gradient", "postprocess.open", "postprocess.close",
        "postprocess.largest_component", "postprocess.fill_holes", "dl.unet_endoscopie",
        "dl.unet_busi",
    }
    assert set(STEP_CATALOGUE) == expected

    schema = pipeline_schema()
    assert schema["catalogue"].keys() == STEP_CATALOGUE.keys()
    assert len(schema["properties"]["steps"]["items"]["oneOf"]) == len(expected)
    assert json.loads(json.dumps(schema))["title"] == schema["title"]

    otsu = schema["catalogue"]["segment.otsu"]
    assert otsu["label"] == "Seuillage d'Otsu"
    assert otsu["input"] == "image" and otsu["output"] == "mask"
    assert otsu["params"]["invert"]["type"] == "boolean"
    assert otsu["params"]["invert"]["default"] is False

    clahe = schema["catalogue"]["preprocess.clahe"]["params"]
    assert clahe["clip"]["minimum"] == 1.0 and clahe["clip"]["maximum"] == 8.0
    assert clahe["grid"]["default"] == 8

    unet = schema["catalogue"]["dl.unet_endoscopie"]["params"]["threshold"]
    assert unet["minimum"] == 0.3 and unet["maximum"] == 0.7 and unet["default"] == 0.5

    assert pipeline.schema() == schema


def test_empty_pipeline_returns_the_input(frame442: np.ndarray) -> None:
    result = pipeline.run_pipeline(frame442, [])
    assert result.mask is None
    assert result.steps == []
    assert result.total_ms == 0.0
    assert result.image is frame442
