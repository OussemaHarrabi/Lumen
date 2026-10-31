"""Segmentation : seuillage, k-means, MeanShift, contours actifs et watershed.

Les algorithmes reprennent les cellules de l'atelier 3 :

- k-means a 3 classes sur les pixels RGB, classe la plus sombre, apres
  restriction au champ de vision de l'endoscope (seuil 25, fermeture 9 x 9,
  plus grande composante, remplissage des trous) puis ouverture et plus grande
  composante connexe ;
- MeanShift sur un sous-echantillonnage spatial, chaque pixel etant ensuite
  affecte au centre de classe le plus proche ;
- Chan-Vese morphologique de scikit-image, initialise par un disque centre sur
  le barycentre de la region sombre, sur un recadrage de 240 x 240 pixels ;
- watershed sur les marqueurs du gradient morphologique.
"""

from __future__ import annotations

import cv2
import numpy as np
from skimage.segmentation import morphological_chan_vese

from .io import to_color, to_gray, to_mask


def field_of_view(image: np.ndarray, threshold: int = 25, close_ksize: int = 9) -> np.ndarray:
    """Champ de vision de l'endoscope : zone eclairee, trous internes bouches.

    Le fond noir de l'endoscope est tres sombre : on seuille a 25, on ferme les
    petits trous avec un noyau 9 x 9, on garde la plus grande composante et on
    remplit les trous internes pour que le glottis reste dans le champ.
    """
    gray = to_gray(image)
    binary = (gray > int(threshold)).astype(np.uint8) * 255
    closed = cv2.morphologyEx(
        binary, cv2.MORPH_CLOSE, np.ones((int(close_ksize), int(close_ksize)), np.uint8)
    )
    fov = largest_component(closed)
    return fill_holes(fov) > 0


def _kmeans_labels(image: np.ndarray, k: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Etiquettes k-means (HxW) et centres (k x 3) sur les pixels RGB."""
    from sklearn.cluster import KMeans

    rgb = to_color(image)
    pixels = rgb.reshape(-1, 3).astype(np.float64)
    model = KMeans(n_clusters=int(k), n_init=10, random_state=int(seed)).fit(pixels)
    labels = model.labels_.reshape(rgb.shape[:2])
    return labels, model.cluster_centers_


def _dark_class(labels: np.ndarray, gray: np.ndarray, zone: np.ndarray) -> tuple[int, np.ndarray]:
    """Indice de la classe la plus sombre et niveau de gris moyen par classe."""
    class_count = int(labels.max()) + 1
    levels = np.array(
        [float(gray[(labels == k) & zone].mean()) if np.any((labels == k) & zone) else np.inf
         for k in range(class_count)]
    )
    return int(np.argmin(levels)), levels


def darkest_mask(
    labels: np.ndarray,
    gray: np.ndarray,
    zone: np.ndarray | None = None,
    ksize: int = 3,
) -> tuple[np.ndarray, dict]:
    """Classe la plus sombre de la carte d'etiquettes, nettoyee.

    La classe la plus sombre est celle dont le niveau de gris moyen est le plus
    faible dans la zone d'analyse. Le masque est ensuite ouvert puis reduit a sa
    plus grande composante connexe, comme dans le notebook.
    """
    gray = to_gray(gray)
    if zone is None:
        zone = np.ones(gray.shape, bool)
    zone = np.asarray(zone, bool)
    if zone.shape != gray.shape:
        raise ValueError("La zone d'analyse doit avoir la forme de l'image")
    dark, levels = _dark_class(labels, gray, zone)
    class_count = int(labels.max()) + 1
    mask = ((labels == dark) & zone).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((int(ksize),) * 2, np.uint8))
    mask = largest_component(mask)
    diagnostics = {
        "classes": [int(k) for k in range(class_count)],
        "class_levels": [round(float(level), 2) if np.isfinite(level) else None for level in levels],
        "darkest_class": dark,
        "zone_pixels": int(zone.sum()),
        "mask_pixels": int(mask.sum()),
    }
    return to_mask(mask), diagnostics


def threshold(image: np.ndarray, threshold: int = 128, invert: bool = False) -> tuple[np.ndarray, dict]:
    """Seuillage manuel : pixels superieurs au seuil, ou inferieurs si invert."""
    gray = to_gray(image)
    mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    _, binary = cv2.threshold(gray, int(np.clip(threshold, 0, 255)), 255, mode)
    return to_mask(binary), {"threshold": int(threshold), "invert": bool(invert)}


def otsu(image: np.ndarray, invert: bool = False) -> tuple[np.ndarray, dict]:
    """Seuillage automatique d'Otsu, avec le seuil trouve en diagnostic."""
    gray = to_gray(image)
    mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    found, binary = cv2.threshold(gray, 0, 255, mode + cv2.THRESH_OTSU)
    return to_mask(binary), {"threshold": float(found), "invert": bool(invert),
                             "mask_pixels": int(np.count_nonzero(binary))}


def kmeans(image: np.ndarray, k: int = 3, seed: int = 42) -> tuple[np.ndarray, dict]:
    """Segmentation k-means, masque de la classe la plus sombre.

    L'analyse est restreinte au champ de vision de l'endoscope : sans cette
    restriction, la classe la plus sombre est le fond noir et le masque recouvre
    tout l'arriere-plan (Dice 0.09 contre 0.46 avec restriction sur frame442).
    """
    labels, centers = _kmeans_labels(image, k, seed)
    gray = to_gray(image)
    fov = field_of_view(image)
    mask, diagnostics = darkest_mask(labels, gray, fov)
    diagnostics.update({"k": int(k), "seed": int(seed), "centers": np.round(centers, 1).tolist()})
    return mask, diagnostics


def meanshift(image: np.ndarray, subsample: int = 3, fov_restrict: bool = True) -> tuple[np.ndarray, dict]:
    """Segmentation MeanShift sur un sous-echantillonnage spatial.

    Le MeanShift sur les 307 200 pixels de frame442 ne termine pas ; les classes
    sont donc apprises sur un pixel sur subsample dans chaque direction (1/9 pour
    la valeur par defaut 3), puis chaque pixel de l'image entiere est affecte au
    centre de classe le plus proche. L'image est d'abord filtree par un median
    5 x 5, comme dans le notebook.
    """
    from sklearn.cluster import MeanShift
    from sklearn.neighbors import NearestNeighbors

    step = int(np.clip(subsample, 1, 9))
    filtered = cv2.medianBlur(to_color(image), 5)
    pixels = filtered.reshape(-1, 3).astype(np.float64)
    sample = filtered[::step, ::step].reshape(-1, 3).astype(np.float64)
    model = MeanShift(bin_seeding=True, n_jobs=-1).fit(sample)
    centers = model.cluster_centers_
    nearest = NearestNeighbors(n_neighbors=1).fit(centers)
    labels = nearest.kneighbors(pixels, return_distance=False).ravel().reshape(filtered.shape[:2])
    gray = to_gray(image)
    zone = field_of_view(image) if fov_restrict else None
    mask, diagnostics = darkest_mask(labels, gray, zone)
    diagnostics.update({
        "regions": len(centers),
        "subsample": step,
        "sample_pixels": int(sample.shape[0]),
        "fov_restrict": bool(fov_restrict),
        "centers": np.round(centers, 1).tolist(),
    })
    return mask, diagnostics


def _disk(shape: tuple[int, int], center: tuple[int, int], radius: int) -> np.ndarray:
    rows, cols = np.ogrid[: shape[0], : shape[1]]
    return ((rows - center[0]) ** 2 + (cols - center[1]) ** 2) <= int(radius) ** 2


def chan_vese(
    image: np.ndarray,
    iterations: int = 50,
    smoothing: float = 3.0,
    crop: bool = True,
) -> tuple[np.ndarray, dict]:
    """Contours actifs de Chan-Vese (level-set morphologique).

    Le disque initial est centre sur le barycentre de la region la plus sombre
    trouvee par k-means dans le champ de vision. Avec crop, le level-set tourne
    sur une fenetre de 240 x 240 pixels autour de ce barycentre : le contraste
    local y est exploitable, alors que sur l'image entiere la methode separe le
    fond noir des tissus brillants.
    """
    gray = to_gray(image)
    height, width = gray.shape
    fov = field_of_view(image)
    labels, _ = _kmeans_labels(image, 3, 42)
    dark, _ = _dark_class(labels, gray, fov)
    rows, cols = np.where((labels == dark) & fov)
    if rows.size == 0:
        return np.zeros_like(gray, np.uint8), {"pixels": 0, "crop": bool(crop)}
    center = (int(rows.mean()), int(cols.mean()))

    if crop:
        half = min(120, height // 2, width // 2)
        row0, row1 = max(0, center[0] - half), min(height, center[0] + half)
        col0, col1 = max(0, center[1] - half), min(width, center[1] + half)
        view = gray[row0:row1, col0:col1]
        radius = min(40, view.shape[0] // 2, view.shape[1] // 2)
        initial = _disk(view.shape, (view.shape[0] // 2, view.shape[1] // 2), radius)
    else:
        row0, row1, col0, col1 = 0, height, 0, width
        view = gray
        radius = min(50, height // 2, width // 2)
        initial = _disk(gray.shape, center, radius)

    level_set = morphological_chan_vese(
        view.astype(np.float64) / 255.0,
        num_iter=int(iterations),
        init_level_set=initial,
        smoothing=round(smoothing),
    )
    mask = np.zeros_like(gray, np.uint8)
    mask[row0:row1, col0:col1] = (level_set > 0).astype(np.uint8)
    diagnostics = {
        "iterations": int(iterations),
        "smoothing": float(smoothing),
        "crop": bool(crop),
        "radius": int(radius),
        "center": [int(center[0]), int(center[1])],
        "window": [int(row0), int(row1), int(col0), int(col1)],
        "mask_pixels": int(mask.sum()),
    }
    return mask, diagnostics


def watershed(image: np.ndarray, marker_ratio: float = 0.5) -> tuple[np.ndarray, dict]:
    """Watershed controle par marqueurs sur la magnitude du gradient.

    La surface topographique est le gradient morphologique (dilatation moins
    erosion), identique que l'image soit en couleur ou en niveaux de gris : un
    appel avec une image convertie en gris donne exactement le meme masque.

    marker_ratio est le pourcentage de pixels du champ de vision, les plus
    sombres, utilises comme marqueurs d'objet : 0,5 designe les 0,5 % les plus
    sombres. Ce quantile est stable d'un prefiltrage a l.autre (median, gaussien)
    et entre 0,4 et 1,0 le Dice reste autour de 0,90 sur frame442 ; au-dela de
    1,25 le marqueur deborde sur le fond sombre et le masque s'effondre.
    """
    gray = to_gray(image)
    fov = field_of_view(image)
    otsu_level, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ratio = float(np.clip(marker_ratio, 0.01, 5.0))
    cut = float(np.percentile(gray[fov], ratio))
    foreground = (gray <= cut) & fov
    if not foreground.any():
        foreground = (gray == float(gray[fov].min())) & fov
    background = (~fov) | (gray > float(otsu_level))
    gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    surface = cv2.cvtColor(gradient, cv2.COLOR_GRAY2RGB)
    markers = np.zeros(gray.shape, np.int32)
    markers[background] = 1
    markers[foreground] = 2
    basin = cv2.watershed(surface, markers.copy())
    mask = (basin == 2).astype(np.uint8)
    diagnostics = {
        "marker_ratio": ratio,
        "marker_threshold": cut,
        "otsu_level": float(otsu_level),
        "foreground_pixels": int(foreground.sum()),
        "mask_pixels": int(mask.sum()),
    }
    return mask, diagnostics


def open_mask(mask: np.ndarray, ksize: int = 3) -> tuple[np.ndarray, dict]:
    """Ouverture morphologique : retire les petites regions du masque."""
    kernel = np.ones((int(ksize),) * 2, np.uint8)
    result = cv2.morphologyEx(to_mask(mask) * 255, cv2.MORPH_OPEN, kernel)
    return to_mask(result), {"ksize": int(ksize), "mask_pixels": int(np.count_nonzero(result))}


def close_mask(mask: np.ndarray, ksize: int = 3) -> tuple[np.ndarray, dict]:
    """Fermeture morphologique : bouche les petits trous du masque."""
    kernel = np.ones((int(ksize),) * 2, np.uint8)
    result = cv2.morphologyEx(to_mask(mask) * 255, cv2.MORPH_CLOSE, kernel)
    return to_mask(result), {"ksize": int(ksize), "mask_pixels": int(np.count_nonzero(result))}


def largest_component(mask: np.ndarray) -> np.ndarray:
    """Garde la plus grande composante connexe d'un masque binaire (0/255)."""
    binary = (np.asarray(mask) > 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return np.zeros_like(binary)
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == largest).astype(np.uint8)


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Bouche les trous internes d'un masque binaire.

    Methode du notebook : remplissage du fond connexe au coin (0, 0) par
    floodFill, puis union avec le complement. Contrairement a
    scipy.ndimage.binary_fill_holes, cette variante reproduit exactement le
    champ de vision de l'atelier 3 (202 022 pixels sur frame442).
    """
    binary = (np.asarray(mask) > 0).astype(np.uint8) * 255
    filled = binary.copy()
    canvas = np.zeros((binary.shape[0] + 2, binary.shape[1] + 2), np.uint8)
    cv2.floodFill(filled, canvas, (0, 0), 255)
    return binary | cv2.bitwise_not(filled)
