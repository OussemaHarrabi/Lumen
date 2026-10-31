"""Recalage d'images : translation, affine, homographie et flot optique.

Portage de l'atelier 5. Convention de direction : la transformation estimee est
appliquee a l'image mobile pour l'amener dans le repere de l'image fixe, comme
le demande le contrat de l'API. Les matrices sont des matrices 3 x 3 en
coordonnees (x, y) homogenes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .io import to_gray

METHODS = ("translation", "affine", "homography", "optical_flow")


@dataclass
class RegistrationResult:
    """Resultat d'un recalage : matrice, image recalee et mesures.

    transform est la matrice 3 x 3 appliquee a l'image mobile pour l'amener dans
    le repere de la fixe. confidence est un indicateur entre 0 et 1 : score NCC
    pour la translation, proportion d'inliers pour les methodes a points, part
    des points du champ de flot retenus par l'estimation affine.
    """

    method: str
    transform: np.ndarray
    warped: np.ndarray
    metrics: dict[str, float]
    success: bool
    confidence: float = 1.0
    matches: int = 0
    inliers: int = 0
    flow: np.ndarray | None = field(default=None, repr=False)


def ncc(image_a: np.ndarray, image_b: np.ndarray) -> float:
    """Correlation croisee normalisee (coefficient de Pearson)."""
    a = to_gray(image_a).astype(np.float64).ravel()
    b = to_gray(image_b).astype(np.float64).ravel()
    a = a - a.mean()
    b = b - b.mean()
    denominator = float(np.sqrt((a * a).sum() * (b * b).sum()))
    if denominator == 0.0:
        return 0.0
    return float((a * b).sum() / denominator)


def mse(image_a: np.ndarray, image_b: np.ndarray) -> float:
    """Erreur quadratique moyenne entre deux images de meme taille."""
    a = to_gray(image_a).astype(np.float64)
    b = to_gray(image_b).astype(np.float64)
    if a.shape != b.shape:
        raise ValueError(f"Formes incompatibles : {a.shape} et {b.shape}")
    return float(np.mean((a - b) ** 2))


def nmi(image_a: np.ndarray, image_b: np.ndarray, bins: int = 64) -> float:
    """Information mutuelle normalisee : NMI = 2 I / (H1 + H2).

    Histogramme joint de bins x bins entre 0 et 255, comme dans l'atelier 5
    (64 x 64).
    """
    a = to_gray(image_a).ravel()
    b = to_gray(image_b).ravel()
    joint, _, _ = np.histogram2d(a, b, bins=int(bins), range=[[0, 256], [0, 256]])
    total = joint.sum()
    if total == 0:
        return 0.0
    p = joint / total
    p_x = p.sum(axis=1)
    p_y = p.sum(axis=0)

    def entropy(q: np.ndarray) -> float:
        q = q[q > 0]
        return float(-(q * np.log2(q)).sum())

    outer = np.outer(p_x, p_y)
    positive = p > 0
    mutual = float((p[positive] * np.log2(p[positive] / outer[positive])).sum())
    denominator = entropy(p_x) + entropy(p_y)
    if denominator == 0.0:
        return 0.0
    return 2.0 * mutual / denominator


def similarity_metrics(fixed: np.ndarray, moving: np.ndarray) -> dict[str, float]:
    """Les trois mesures de similarite entre deux images de meme taille."""
    return {"ncc": ncc(fixed, moving), "mse": mse(fixed, moving), "nmi": nmi(fixed, moving)}


def translation_transform(tx: float, ty: float) -> np.ndarray:
    """Matrice 3 x 3 d'une translation."""
    return np.array([[1.0, 0.0, float(tx)], [0.0, 1.0, float(ty)], [0.0, 0.0, 1.0]])


def _to_homography(matrix: np.ndarray) -> np.ndarray:
    """Matrice 2 x 3 ou 3 x 3 vers matrice 3 x 3."""
    array = np.asarray(matrix, dtype=np.float64)
    if array.shape == (3, 3):
        return array
    if array.shape == (2, 3):
        return np.vstack([array, [0.0, 0.0, 1.0]])
    raise ValueError(f"Transformation de forme inattendue : {array.shape}")


def apply_transform(image: np.ndarray, transform: np.ndarray, shape: tuple[int, int] | None = None) -> np.ndarray:
    """Applique une transformation 3 x 3 a une image.

    Le resultat a la forme demandee (hauteur, largeur) ou celle de l'entree. Les
    pixels hors du domaine source valent 0.
    """
    matrix = _to_homography(transform)
    source = np.asarray(image)
    target = (int(shape[0]), int(shape[1])) if shape is not None else source.shape[:2]
    if np.allclose(matrix[2], [0.0, 0.0, 1.0]):
        warped = cv2.warpAffine(
            source, matrix[:2], (target[1], target[0]), flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        )
    else:
        warped = cv2.warpPerspective(
            source, matrix, (target[1], target[0]), flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        )
    return warped


def warp_points(transform: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Applique une transformation 3 x 3 a des points Nx2."""
    matrix = _to_homography(transform)
    array = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    homogeneous = np.hstack([array, np.ones((array.shape[0], 1))])
    projected = (matrix @ homogeneous.T).T
    scale = projected[:, 2:3]
    scale[scale == 0.0] = 1.0
    return projected[:, :2] / scale


def landmark_error(transform: np.ndarray, points: np.ndarray) -> dict[str, object]:
    """Erreur des points de controle apres application de la transformation.

    points contient des lignes [x1, y1, x2, y2] : le point de l'image fixe puis
    son correspondant sur l'image mobile. La transformation estimee amene la
    mobile dans le repere de la fixe : on transforme donc (x2, y2) et on le
    compare a (x1, y1).
    """
    array = np.asarray(points, dtype=np.float64).reshape(-1, 4)
    moved = warp_points(transform, array[:, 2:4])
    errors = np.linalg.norm(moved - array[:, :2], axis=1)
    if errors.size == 0:
        return {"mean": 0.0, "median": 0.0, "max": 0.0, "success_rate": 0.0, "per_point": []}
    return {
        "mean": float(errors.mean()),
        "median": float(np.median(errors)),
        "max": float(errors.max()),
        "success_rate": float((errors < 10.0).mean()),
        "per_point": [float(value) for value in errors],
    }


def prepare_retina(image: np.ndarray) -> np.ndarray:
    """Image de travail du recalage retinien : quart de taille, canal vert, CLAHE."""
    small = cv2.resize(image, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    if small.ndim == 3:
        green = small[:, :, 1]
    else:
        green = small
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(green)


def _match_features(fixed: np.ndarray, moving: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Points SIFT apparies de facon reciproque entre les deux images."""
    fixed_small = prepare_retina(fixed)
    moving_small = prepare_retina(moving)
    sift = cv2.SIFT_create(nfeatures=8000, contrastThreshold=0.005)
    keypoints_fixed, descriptors_fixed = sift.detectAndCompute(fixed_small, None)
    keypoints_moving, descriptors_moving = sift.detectAndCompute(moving_small, None)
    if descriptors_fixed is None or descriptors_moving is None:
        return np.empty((0, 2)), np.empty((0, 2))
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    forward = matcher.knnMatch(descriptors_fixed, descriptors_moving, k=2)
    backward = matcher.knnMatch(descriptors_moving, descriptors_fixed, k=2)
    reciprocal = {m.queryIdx: m.trainIdx for m, n in backward if m.distance < 0.9 * n.distance}
    good = [m for m, n in forward if m.distance < 0.9 * n.distance and reciprocal.get(m.trainIdx) == m.queryIdx]
    if len(good) < 4:
        return np.empty((0, 2)), np.empty((0, 2))
    points_fixed = np.float32([keypoints_fixed[m.queryIdx].pt for m in good])
    points_moving = np.float32([keypoints_moving[m.trainIdx].pt for m in good])
    return points_fixed, points_moving


def _quarter_to_full(matrix: np.ndarray) -> np.ndarray:
    """Remet une transformation estimee au quart de la taille en pleine resolution."""
    scale = np.diag([0.25, 0.25, 1.0])
    return np.linalg.inv(scale) @ _to_homography(matrix) @ scale


def estimate_translation(fixed: np.ndarray, moving: np.ndarray) -> tuple[np.ndarray, float]:
    """Translation globale par correlation de phase.

    cv2.phaseCorrelate renvoie le decalage entre les deux images sans garantir
    son signe pour notre convention : on evalue les deux candidats et on garde
    celui qui maximise la correlation apres recalage.
    """
    fixed_gray = np.float32(to_gray(fixed))
    moving_gray = np.float32(to_gray(moving))
    (tx, ty), _ = cv2.phaseCorrelate(fixed_gray, moving_gray)
    candidates = [translation_transform(tx, ty), translation_transform(-tx, -ty)]
    scores = [ncc(fixed, apply_transform(moving, matrix, fixed.shape[:2])) for matrix in candidates]
    best = int(np.argmax(scores))
    return candidates[best], float(scores[best])


def estimate_affine(fixed: np.ndarray, moving: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Transformation affine estimee par SIFT et RANSAC."""
    points_fixed, points_moving = _match_features(fixed, moving)
    if len(points_fixed) < 4:
        raise ValueError("Pas assez de points apparies pour estimer une transformation affine")
    matrix, inliers = cv2.estimateAffine2D(
        points_moving.reshape(-1, 1, 2), points_fixed.reshape(-1, 1, 2),
        method=cv2.RANSAC, ransacReprojThreshold=2.0,
    )
    if matrix is None:
        raise ValueError("Estimation affine impossible")
    count = int(inliers.sum()) if inliers is not None else 0
    return _quarter_to_full(matrix), len(points_fixed), count


def estimate_homography(fixed: np.ndarray, moving: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Homographie estimee par SIFT et USAC_MAGSAC, comme pour les retines FIRE."""
    points_fixed, points_moving = _match_features(fixed, moving)
    if len(points_fixed) < 4:
        raise ValueError("Pas assez de points apparies pour estimer une homographie")
    matrix, inliers = cv2.findHomography(
        points_moving.reshape(-1, 1, 2), points_fixed.reshape(-1, 1, 2), cv2.USAC_MAGSAC, 2.0
    )
    if matrix is None:
        raise ValueError("Estimation d'homographie impossible")
    count = int(inliers.sum()) if inliers is not None else 0
    return _quarter_to_full(matrix), len(points_fixed), count


def optical_flow(fixed: np.ndarray, moving: np.ndarray) -> np.ndarray:
    """Flot optique dense de Farneback, calcule sur l'image de travail.

    L'image de travail est celle de prepare_retina : quart de la taille, canal
    vert, contraste local augmente. Le champ renvoye a donc la forme
    (hauteur / 4, largeur / 4, 2) ; les composantes sont les deplacements en
    pixels de l'image de travail.
    """
    fixed_small = prepare_retina(fixed)
    moving_small = prepare_retina(moving)
    return cv2.calcOpticalFlowFarneback(fixed_small, moving_small, None, 0.5, 3, 15, 3, 5, 1.2, 0)


def estimate_optical_flow(
    fixed: np.ndarray, moving: np.ndarray
) -> tuple[np.ndarray, np.ndarray, int, int, float]:
    """Transformation globale deduite du champ de flot optique.

    Le champ de Farneback donne, pour chaque point p de l'image fixe, sa
    correspondance p + flot dans l'image mobile. On echantillonne une grille,
    on ne garde que les points textures (gradient au-dessus du 70e centile,
    seuls endroits ou le flot est fiable), puis une affine robuste (RANSAC) est
    ajustee des correspondances mobiles vers la fixe. Le resultat est ramene a
    la pleine resolution.

    Renvoie la matrice 3 x 3, le champ dense, le nombre de points echantillonnes,
    le nombre d'inliers et la confiance (inliers / points).
    """
    flow = optical_flow(fixed, moving)
    fixed_small = prepare_retina(fixed)
    height, width = fixed_small.shape
    rows, cols = np.mgrid[0:height:2, 0:width:2]
    gradient_x = cv2.Sobel(fixed_small, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(fixed_small, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(gradient_x, gradient_y)
    textured = gradient[rows, cols] > float(np.percentile(gradient, 70))
    rows = rows[textured].astype(np.float32)
    cols = cols[textured].astype(np.float32)
    if rows.size < 20:
        raise ValueError("Pas assez de points textures pour le flot optique")
    flow_x = flow[rows.astype(int), cols.astype(int), 0]
    flow_y = flow[rows.astype(int), cols.astype(int), 1]
    moving_points = np.stack([cols + flow_x, rows + flow_y], axis=1)
    fixed_points = np.stack([cols, rows], axis=1)
    matrix, inliers = cv2.estimateAffine2D(
        moving_points, fixed_points, method=cv2.RANSAC, ransacReprojThreshold=1.0, maxIters=5000
    )
    count = int(inliers.sum()) if inliers is not None else 0
    if matrix is None or count < 20:
        dx = float(np.median(flow_x))
        dy = float(np.median(flow_y))
        transform = translation_transform(4.0 * dx, 4.0 * dy)
        return transform, flow, int(rows.size), 0, 0.0
    transform = _quarter_to_full(matrix)
    confidence = count / max(1, int(rows.size))
    return transform, flow, int(rows.size), count, float(confidence)


def register(
    fixed: np.ndarray,
    moving: np.ndarray,
    method: str = "translation",
    params: dict | None = None,
) -> RegistrationResult:
    """Recale l'image mobile sur l'image fixe et mesure la similarite.

    method vaut translation, affine, homography ou optical_flow. Pour le flot
    optique, une transformation affine globale est ajustee sur le champ dense
    de Farneback (points textures, RANSAC) et ramenee en pleine resolution ; le
    champ de travail est disponible dans result.flow. La confidence vaut le
    score NCC pour la translation et la proportion d'inliers pour les autres
    methodes.
    """
    if method not in METHODS:
        raise ValueError(f"Methode de recalage inconnue : {method}")
    params = dict(params or {})
    flow = None
    matches = inliers = 0
    confidence = 0.0
    if method == "translation":
        transform, confidence = estimate_translation(fixed, moving)
        success = True
    elif method == "affine":
        transform, matches, inliers = estimate_affine(fixed, moving)
        confidence = inliers / matches if matches else 0.0
        success = inliers >= int(params.get("min_inliers", 10))
    elif method == "homography":
        transform, matches, inliers = estimate_homography(fixed, moving)
        confidence = inliers / matches if matches else 0.0
        success = inliers >= int(params.get("min_inliers", 10))
    else:
        transform, flow, matches, inliers, confidence = estimate_optical_flow(fixed, moving)
        success = confidence >= float(params.get("min_confidence", 0.2))
    warped = apply_transform(moving, transform, fixed.shape[:2])
    metrics = similarity_metrics(fixed, warped)
    return RegistrationResult(
        method=method,
        transform=transform,
        warped=warped,
        metrics=metrics,
        success=success,
        confidence=float(confidence),
        matches=matches,
        inliers=inliers,
        flow=flow,
    )
