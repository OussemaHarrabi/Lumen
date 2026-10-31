"""Génère le rapport PDF de l'atelier 6 (Traitement d'images médicales, Sup'Com).

Le rapport présente la plateforme Lumen : objectif, architecture, chaîne de
traitement et API, interface, résultats mesurés, recalage, choix d'ingénierie et
limites. Les chiffres viennent d'exécutions réelles : les cinq chaînes sont
rejouées sur les démonstrations de l'API et les trois méthodes de recalage sur la
paire FIRE A01 avec ses dix points de contrôle.

Script autonome (bibliothèque standard, PIL et PyMuPDF pour les captures et le
contrôle du PDF). Il écrit build/report_at6.html, imprime Rapport_Atelier6.pdf
avec Chrome headless, puis vérifie le nombre de pages, l'absence de tiret
cadratin et demi-cadratin, et la présence des extraits de code recopiés.

Entrées : build/at6_measures.json et build/at6_recalage.json, produits par
build/measure_at6.py (API démarrée sur 127.0.0.1:8011), et le contrat OpenAPI
de l'API, relu à chaud quand elle répond.

Usage :  .venv/Scripts/python.exe build/make_report_at6.py
"""

from __future__ import annotations

import base64
import html
import io
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

# --- Constantes ---------------------------------------------------------------
ETUDIANT = "Oussema Harrabi"
GROUPE = "INDP3 - SIA 26-27"
MODULE = "Traitement d'images médicales"
ENSEIGNANTE = "Mme Wafa Rekik"
ETABLISSEMENT = "Sup'Com"
TITRE = "Atelier 6 : plateforme web d'analyse d'images médicales"
TITRE_HTML = "Atelier 6 : plateforme web<br>d'analyse d'images médicales"
DATE = "30 octobre 2026"

RACINE = Path(__file__).resolve().parent.parent
BUILD = RACINE / "build"
CAPTURES = RACINE / "apps" / "web" / "screenshots"
MESURES = BUILD / "at6_measures.json"
RECALAGE = BUILD / "at6_recalage.json"
OPENAPI = BUILD / "at6_openapi.json"
API = "http://127.0.0.1:8011"
HTML_SORTIE = BUILD / "report_at6.html"
PDF_SORTIE = RACINE / "Rapport_Atelier6.pdf"

PIPELINE_PY = RACINE / "packages" / "cv" / "lumen_cv" / "pipeline.py"
ANALYSES_PY = RACINE / "apps" / "api" / "app" / "routes" / "analyses.py"
CANVAS_TSX = RACINE / "apps" / "web" / "components" / "canvas" / "ImageCanvas.tsx"

NAVIGATEURS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

INTERDITS = {"\u2014": "tiret cadratin (U+2014)", "\u2013": "tiret demi-cadratin (U+2013)"}

# --- Style --------------------------------------------------------------------
CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; background: #faf7ef; color: #232830;
       font-family: "Instrument Sans", system-ui, -apple-system, sans-serif;
       font-size: 9.1pt; line-height: 1.4; }
p { margin: 0 0 3.6px 0; text-align: justify; }
strong { font-weight: 600; color: #1b1f26; }
code { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 8.2pt;
       background: #f1ece0; padding: 0 2px; border-radius: 2px; }

h2 { font-family: "Fraunces", Georgia, serif; font-weight: 500; font-size: 13.5pt;
     margin: 0 0 5px 0; padding: 0 0 3px 0; border-bottom: 1px solid #e0dcd2;
     color: #1b1f26; break-after: avoid; }
h2 .num { font-family: "JetBrains Mono", monospace; font-size: 10pt; color: #b23a2b;
          margin-right: 8px; font-weight: 500; }
h3 { font-family: "Fraunces", Georgia, serif; font-weight: 500; font-size: 10.4pt;
     margin: 8px 0 3px 0; color: #1b1f26; break-after: avoid; }
.section { break-before: page; padding: 12mm 14mm 10mm 14mm; }
.section.flow { break-before: auto; padding-top: 0; }

table { width: 100%; border-collapse: collapse; margin: 3px 0 5px 0; break-inside: avoid; }
caption { caption-side: top; text-align: left; font-family: "JetBrains Mono", monospace;
          font-size: 7.2pt; letter-spacing: 0.9px; text-transform: uppercase;
          color: #8a8f96; padding-bottom: 2px; }
thead th { text-align: left; font-family: "JetBrains Mono", monospace; font-weight: 500;
           font-size: 7.2pt; letter-spacing: 0.7px; text-transform: uppercase;
           color: #5a6068; padding: 1.8px 4px; border-bottom: 1px solid #232830; }
tbody td { padding: 2.1px 4px; font-size: 8.3pt; border-bottom: 1px solid #e4e0d6;
           vertical-align: top; }
tbody tr:last-child td { border-bottom: 1px solid #d6d1c4; }
td.num, th.num { text-align: right; font-family: "JetBrains Mono", monospace;
                 font-size: 8.1pt; font-variant-numeric: tabular-nums; }

figure { margin: 3px 0 4px 0; break-inside: avoid; }
figure img { display: block; width: 100%; border: 1px solid #dcd7ca; }
figure .pair { display: flex; gap: 6px; }
figure .pair > div { flex: 1 1 0; min-width: 0; }
figcaption { font-size: 7.8pt; color: #6b7079; margin-top: 2.5px; line-height: 1.32; }
figcaption .tag { font-family: "JetBrains Mono", monospace; font-size: 7.2pt;
                  letter-spacing: 0.8px; text-transform: uppercase; color: #b23a2b;
                  margin-right: 5px; }

.codebloc { background: #eef4f5; border-left: 3px solid #b23a2b;
            border-radius: 3px; padding: 5px 9px; margin: 3px 0 5px 0;
            break-inside: avoid; }
.codebloc.serre pre { font-size: 7.3pt; }
.codeleg { font-family: "JetBrains Mono", monospace; font-size: 7.2pt;
           letter-spacing: 0.9px; text-transform: uppercase; color: #7d8a90;
           margin-bottom: 4px; }
pre { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 8.3pt;
      line-height: 1.45; color: #1d3238; margin: 0; white-space: pre-wrap;
      font-variant-ligatures: none; font-feature-settings: "liga" 0, "calt" 0;
      overflow-wrap: break-word; }

.note { border-left: 3px solid #b23a2b; background: #f7efe9; padding: 5px 9px;
        margin: 5px 0; break-inside: avoid; }
.note .label { display: block; font-family: "JetBrains Mono", monospace; font-size: 7.2pt;
               letter-spacing: 0.9px; text-transform: uppercase; color: #b23a2b;
               margin-bottom: 3px; }
.note p { margin: 0 0 1.5px 0; font-size: 8.9pt; }
.note p:last-child { margin-bottom: 0; }

ul { margin: 2px 0 6px 0; padding-left: 15px; }
li { margin-bottom: 3px; text-align: justify; }
li strong { color: #1b1f26; }

.schema { margin: 4px 0 4px 0; break-inside: avoid; }
.split { display: flex; gap: 10px; align-items: flex-start; margin: 2px 0 4px 0;
         break-inside: avoid; }
.split .visuel { flex: 0 0 57%; }
.split .visuel img { display: block; width: 100%; border: 1px solid #dcd7ca; }
.split .texte { flex: 1 1 auto; font-size: 9pt; }
.split .texte p { text-align: left; margin: 0 0 4px 0; }
.schema svg { display: block; width: 100%; height: auto; }

.cover { min-height: 292mm; padding: 0 14mm; display: flex; flex-direction: column;
         justify-content: center; }
.cover .etab { font-family: "JetBrains Mono", monospace; font-size: 9.5pt;
               letter-spacing: 3.4px; text-transform: uppercase; color: #b23a2b; }
.cover .module { font-size: 10pt; color: #5a6068; margin-top: 2px; }
.cover hr { border: none; border-top: 2px solid #b23a2b; width: 62px;
            margin: 9px 0 11px 0; }
.cover .ens { font-size: 10pt; color: #3d434b; margin-bottom: 14px; }
.cover h1 { font-family: "Fraunces", Georgia, serif; font-weight: 400; font-size: 23pt;
            line-height: 1.16; margin: 0 0 12px 0; color: #1b1f26; letter-spacing: -0.3px; }
.cover .realise { font-size: 11.5pt; }
.cover .date { font-size: 9.5pt; color: #6b7079; margin-top: 2px; }
.cover .resume { border-top: 1px solid #e0dcd2; margin-top: 18px; padding-top: 9px;
                 font-size: 9.6pt; color: #3d434b; max-width: 162mm; }
.cover .resume p { margin: 0 0 3px 0; }
"""

# --- Extraits de code : lus dans les sources, jamais recopiés à la main --------
def lignes(chemin: Path, debut: int, fin: int) -> str:
    """Lignes debut..fin incluses d'un fichier, telles quelles."""
    contenu = chemin.read_text(encoding="utf-8").splitlines()
    return "\n".join(contenu[debut - 1 : fin])


EXTRAITS = [
    ("lumen_cv/pipeline.py, boucle d'exécution", lignes(PIPELINE_PY, 127, 138), PIPELINE_PY),
    ("analyses.py, fin de create_analysis", lignes(ANALYSES_PY, 72, 79), ANALYSES_PY),
    ("ImageCanvas.tsx, tampon au facteur DPR", lignes(CANVAS_TSX, 136, 145), CANVAS_TSX),
    ("ImageCanvas.tsx, pose du calque de masque", lignes(CANVAS_TSX, 178, 181), CANVAS_TSX),
]

PIPELINE_JSON = """{"steps": [
  {"kind": "preprocess.gray", "params": {}},
  {"kind": "segment.watershed", "params": {"marker_ratio": 0.5}},
  {"kind": "postprocess.open", "params": {"ksize": 3}},
  {"kind": "postprocess.largest_component", "params": {}}
]}"""


# --- Captures -----------------------------------------------------------------
def data_uri(chemin: Path, largeur: int, decoupe: tuple[int, int] | None = None) -> str:
    """Capture encodée en data URI, réduite à `largeur` px (éventuellement découpée)."""
    image = Image.open(chemin).convert("RGB")
    if decoupe is not None:
        image = image.crop((0, decoupe[0], image.width, decoupe[1]))
    if image.width > largeur:
        hauteur = round(image.height * largeur / image.width)
        image = image.resize((largeur, hauteur), Image.LANCZOS)
    tampon = io.BytesIO()
    image.save(tampon, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(tampon.getvalue()).decode("ascii")


# --- Schéma d'architecture ----------------------------------------------------
def boite(x, y, w, h, titre, detail, accent=False):
    bord = "#b23a2b" if accent else "#c9c4b6"
    epaisseur = "1.4" if accent else "1"
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" '
        f'fill="#fdfbf6" stroke="{bord}" stroke-width="{epaisseur}"/>'
        f'<text x="{x + 10}" y="{y + 17}" font-family="Instrument Sans, sans-serif" '
        f'font-size="10.5" font-weight="600" fill="#1b1f26">{titre}</text>'
        f'<text x="{x + 10}" y="{y + 31}" font-family="JetBrains Mono, monospace" '
        f'font-size="7.6" fill="#5a6068">{detail}</text>'
    )


def fleche(x1, y1, x2, y2, etiquette="", dx=0, dy=-4):
    texte = ""
    if etiquette:
        texte = (
            f'<text x="{(x1 + x2) / 2 + dx}" y="{(y1 + y2) / 2 + dy}" '
            f'font-family="JetBrains Mono, monospace" font-size="7.4" fill="#7d8a90" '
            f'text-anchor="middle">{etiquette}</text>'
        )
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#8a8f96" stroke-width="1" '
        f'marker-end="url(#pointe)"/>' + texte
    )


SCHEMA = f"""<svg viewBox="0 0 700 250" xmlns="http://www.w3.org/2000/svg" role="img">
<defs>
<marker id="pointe" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7"
        orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="#8a8f96"/></marker>
</defs>
<rect x="0" y="0" width="700" height="250" fill="#faf7ef"/>
{boite(6, 16, 164, 52, "Navigateur", "Next.js, canvas maison")}
{fleche(170, 42, 232, 42, "/lum-api", 0, -5)}
{boite(232, 16, 180, 52, "API FastAPI", "/api, SSE, OpenAPI", accent=True)}
{fleche(412, 42, 476, 42, "appel direct", 0, -5)}
{boite(476, 16, 218, 52, "lumen_cv", "étapes, métriques, entrées")}
{fleche(322, 68, 322, 98)}
<text x="330" y="88" font-family="JetBrains Mono, monospace" font-size="7.4"
      fill="#7d8a90">mise en file</text>
{boite(232, 98, 180, 46, "File de tâches", "threads internes, SSE")}
{fleche(586, 68, 586, 98)}
<text x="594" y="88" font-family="JetBrains Mono, monospace" font-size="7.4"
      fill="#7d8a90">sessions ONNX</text>
{boite(476, 98, 218, 46, "ONNX Runtime", "unet_endoscopie, unet_busi")}
{fleche(300, 144, 168, 182)}
{fleche(360, 144, 400, 182)}
{boite(6, 184, 210, 46, "SQLite", "lumen.db, sessions, analyses")}
{boite(230, 184, 210, 46, "Stockage local", "storage/, un dossier par session")}
{boite(462, 184, 232, 46, "Modèles ONNX", "models/, 2 fichiers de 7,8 Mo")}
</svg>"""


# --- Briques HTML -------------------------------------------------------------
def h2(numero: str, titre: str, flux: bool = False) -> str:
    classe = "section flow" if flux else "section"
    return f'<section class="{classe}"><h2><span class="num">{numero}</span>{titre}</h2>'


def fin() -> str:
    return "</section>"


def p(texte: str) -> str:
    return f"<p>{texte}</p>"


def tableau(
    legende: str,
    entetes: list[tuple[str, bool]],
    lignes_: list[list[str]],
    largeurs: list[str] | None = None,
) -> str:
    groupes = ""
    if largeurs:
        groupes = "<colgroup>" + "".join(
            f'<col style="width:{largeur}">' for largeur in largeurs
        ) + "</colgroup>"
    tete = "".join(
        f'<th class="num">{html.escape(t)}</th>' if droite else f"<th>{html.escape(t)}</th>"
        for t, droite in entetes
    )
    corps = ""
    for ligne in lignes_:
        classe = ' class="total"' if ligne[0] == "Total" else ""
        corps += f"<tr{classe}>" + "".join(
            f'<td class="num">{c}</td>' if entetes[i][1] else f"<td>{c}</td>"
            for i, c in enumerate(ligne)
        ) + "</tr>"
    return (
        f'<table><caption>{html.escape(legende)}</caption>{groupes}'
        f"<thead><tr>{tete}</tr></thead><tbody>{corps}</tbody></table>"
    )


def bloc_code(legende: str, code: str, serre: bool = False) -> str:
    classe = "codebloc serre" if serre else "codebloc"
    return (
        f'<div class="{classe}"><div class="codeleg">{html.escape(legende)}</div>'
        f"<pre>{html.escape(code)}</pre></div>"
    )


def figure(src: str, tag: str, legende: str) -> str:
    return f'<figure><img src="{src}" alt="{html.escape(legende)}">' + legende_fig(tag, legende) + "</figure>"


def legende_fig(tag: str, legende: str) -> str:
    return f'<figcaption><span class="tag">{html.escape(tag)}</span>{legende}</figcaption>'


def paire(src_a, src_b, legende_a, legende_b, tags=("A", "B")) -> str:
    return (
        '<figure><div class="pair">'
        f'<div><img src="{src_a}" alt="{html.escape(legende_a)}">'
        f"{legende_fig(tags[0], legende_a)}</div>"
        f'<div><img src="{src_b}" alt="{html.escape(legende_b)}">'
        f"{legende_fig(tags[1], legende_b)}</div>"
        "</div></figure>"
    )


def encadre(titre: str, paragraphes: list[str]) -> str:
    corps = "".join(f"<p>{t}</p>" for t in paragraphes)
    return f'<div class="note"><span class="label">{html.escape(titre)}</span>{corps}</div>'


# --- Table des routes ---------------------------------------------------------
FAMILLES = {
    "analyses": "Analyses",
    "registrations": "Recalage",
    "assets": "Ressources",
    "demos": "Démonstrations",
    "service": "Service",
}
SERVICES = {"health", "presets", "schema", "jobs"}


def contrat_openapi() -> dict:
    """Contrat OpenAPI de l'API, relu à chaud, sinon la copie enregistrée."""
    try:
        import urllib.request

        with urllib.request.urlopen(f"{API}/openapi.json", timeout=4) as reponse:
            return json.loads(reponse.read())
    except Exception:
        return json.loads(OPENAPI.read_text(encoding="utf-8"))


def tableau_routes() -> str:
    """Répartition des routes de l'API par famille, lue dans le contrat OpenAPI."""
    document = contrat_openapi()
    routes: dict[str, int] = {}
    operations: dict[str, int] = {}
    for chemin_route, methodes in document["paths"].items():
        segment = chemin_route.split("/")[2] if len(chemin_route.split("/")) > 2 else ""
        famille = "service" if segment in SERVICES else segment
        routes[famille] = routes.get(famille, 0) + 1
        operations[famille] = operations.get(famille, 0) + len(methodes)
    ordre = sorted(routes, key=lambda nom: (-operations[nom], nom))
    lignes_ = [
        [FAMILLES.get(nom, nom), str(routes[nom]), str(operations[nom])] for nom in ordre
    ]
    lignes_.append(["Total", str(sum(routes.values())), str(sum(operations.values()))])
    return tableau(
        "Tableau 3. Routes exposées, par famille",
        [("Famille", False), ("Routes", True), ("Opérations", True)],
        lignes_,
        largeurs=["56%", "22%", "22%"],
    )


def construire() -> str:
    mesures = json.loads(MESURES.read_text(encoding="utf-8"))
    recalage = json.loads(RECALAGE.read_text(encoding="utf-8"))
    presets = {ligne["id"]: ligne for ligne in mesures["presets"]}
    reg = {ligne["method"]: ligne for ligne in recalage["demo"]}
    paquet = {ligne["method"]: ligne for ligne in recalage["package"]}

    def etape(nom: str, kind: str) -> float:
        """Durée d'une étape nommée dans une chaîne mesurée."""
        for type_etape, duree in presets[nom]["steps"]:
            if type_etape == kind:
                return duree
        raise KeyError(f"étape {kind} absente de {nom}")

    def fr(valeur: float, decimales: int = 3) -> str:
        return f"{valeur:.{decimales}f}".replace(".", ",")

    accueil = data_uri(CAPTURES / "home-desktop.png", 1320, (0, 960))
    measures = data_uri(CAPTURES / "prod-measures.png", 900)
    watershed = data_uri(CAPTURES / "live-prod-watershed.png", 900)
    checker = data_uri(CAPTURES / "recalage-prod-checkerboard.png", 1180)

    routes = tableau_routes()
    matrice = reg["homography"]["transform"]
    rotation = abs(__import__("math").degrees(__import__("math").atan2(matrice[1][0], matrice[0][0])))
    translation_x = abs(matrice[0][2])
    translation_y = abs(matrice[1][2])

    otsu, kmeans, water = presets["otsu"], presets["kmeans"], presets["watershed"]
    chan, unet = presets["chan-vese"], presets["unet"]

    parties: list[str] = []

    # --- Page de garde ---
    parties.append(
        '<div class="cover">'
        f'<div class="etab">{ETABLISSEMENT}</div>'
        f'<div class="module">{MODULE}</div>'
        "<hr>"
        f'<div class="ens">Enseignante : {ENSEIGNANTE}</div>'
        f"<h1>{TITRE_HTML}</h1>"
        f'<div class="realise">Réalisé par : {ETUDIANT} - {GROUPE}</div>'
        f'<div class="date">{DATE}</div>'
        '<div class="resume">'
        + p("Lumen réunit les cinq ateliers du module dans une seule application web.")
        + p("Le navigateur affiche l'image au pixel, l'API FastAPI exécute des pipelines d'étapes.")
        + p("Cinq chaînes retrouvent les notes du cours, de 0,086 à 0,959, et le recalage tombe à 2,87 px.")
        + "</div></div>"
    )

    # --- 1. Objectif et périmètre ---
    parties.append(h2("1", "Objectif et périmètre"))
    parties.append(
        p(
            "L'énoncé demande une application web qui prenne une image médicale, la prétraite, la "
            "segmente par des méthodes conventionnelles puis par un réseau pré-entraîné, recale deux "
            "images, et permette de comparer les résultats chiffrés dans la même interface."
        )
    )
    parties.append(
        p(
            "Lumen répond à cette demande en rassemblant les cinq ateliers précédents dans un seul "
            "outil. Chaque brique du module devient un module de la plateforme, avec ses méthodes et "
            "son atelier d'origine."
        )
    )
    parties.append(
        tableau(
            "Tableau 1. Modules de la plateforme",
            [("Module", False), ("Méthodes", False), ("Atelier", True)],
            [
                ["Ingestion", "import image, extraction de séquence, métadonnées", "1"],
                ["Prétraitement", "médian, gaussien, moyenneur, CLAHE, niveaux de gris", "2"],
                [
                    "Segmentation conventionnelle",
                    "seuil manuel, Otsu, k-means, MeanShift, watershed, Chan-Vese, morphologie",
                    "2 et 3",
                ],
                ["Contours", "Sobel, Laplacien, gradient morphologique, superposition", "2"],
                ["Segmentation profonde", "U-Net ONNX, jeu endoscopie et jeu BUSI", "4"],
                [
                    "Recalage",
                    "translation, affine, homographie, flot optique, NCC, MSE, NMI, landmarks",
                    "5",
                ],
                ["Évaluation", "Dice, IoU, rappel, précision, durée par étape", "3 et 4"],
                ["Comparaison", "grille de résultats, curseur, tableau de mesures", "6"],
            ],
        )
    )
    parties.append(
        p(
            "Deux publics : l'étudiant qui prépare ses comptes rendus et veut rejouer un TP en "
            "retrouvant les scores du cours, et l'enseignante en soutenance, qui doit vérifier en "
            "trois clics que chaque méthode annoncée tourne vraiment."
        )
    )
    parties.append(fin())

    # --- 2. Architecture ---
    parties.append(h2("2", "Architecture", flux=True))
    parties.append(f'<div class="schema">{SCHEMA}</div>')
    parties.append(
        '<p style="font-size:8pt;color:#6b7079;margin:0 0 6px 0;text-align:left">'
        '<span class="tag" style="font-family:JetBrains Mono,monospace;font-size:7.2pt;'
        'letter-spacing:.8px;text-transform:uppercase;color:#b23a2b;margin-right:5px">Figure 1</span>'
        "Six blocs et un seul sens de dépendance : le navigateur appelle le proxy Next.js, qui appelle "
        "l'API, qui appelle lumen_cv ; le stockage et les modèles restent sur la machine.</p>"
    )
    parties.append(
        p(
            "Le navigateur ne connaît qu'une seule origine. Next.js renvoie tout ce qui commence par "
            "<code>/lum-api</code> vers FastAPI, ce qui garde le cookie de session et permet de relire "
            "les pixels du masque dans un canvas sans négociation CORS."
        )
    )
    parties.append(
        p(
            "L'API ne calcule rien elle-même : elle valide les étapes, écrit l'analyse en base, la met "
            "en file et appelle <code>lumen_cv</code>. Le paquet de traitement ignore FastAPI et "
            "SQLAlchemy, donc il se teste seul, sans serveur ni navigateur."
        )
    )
    parties.append(
        p(
            "Les deux modèles U-Net sont convertis une fois en ONNX et versionnés dans "
            "<code>models/</code>. L'inférence se fait sur le processeur, dans le même processus que "
            "les méthodes classiques."
        )
    )
    parties.append(
        tableau(
            "Tableau 2. Pile technique et raison du choix",
            [("Brique", False), ("Choix", False), ("Raison", False)],
            [
                [
                    "Interface",
                    "Next.js 16 (App Router), canvas maison",
                    "le masque se pose au pixel, le zoom et la lecture de valeur au curseur demandent "
                    "un contexte 2D, pas une balise img",
                ],
                [
                    "Contrat",
                    "OpenAPI généré par FastAPI",
                    "renommer un paramètre casse les types TypeScript au lieu de casser l'interface "
                    "en silence",
                ],
                [
                    "Traitement",
                    "lumen_cv (OpenCV, scikit-image, scikit-learn)",
                    "code pur, sans import web, 41 tests qui tournent sans lancer de serveur",
                ],
                [
                    "Inférence",
                    "ONNX Runtime, deux U-Net",
                    "8 Mo de modèles au lieu de 350 Mo de roue TensorFlow, pour la même sortie",
                ],
                [
                    "Tâches",
                    "file interne à threads, suivi SSE",
                    "le calcul survit à la fermeture de l'onglet et la progression arrive sans sondage",
                ],
            ],
        )
    )
    parties.append(fin())

    # --- 3. Chaîne de traitement et API ---
    parties.append(h2("3", "Chaîne de traitement et API"))
    parties.append(
        p(
            "Une analyse est une liste ordonnée d'étapes. Chaque étape a un type et des paramètres, "
            "et le catalogue publié par <code>GET /api/schema/pipeline</code> donne les bornes de "
            "chaque paramètre. La chaîne watershed tient en quatre étapes."
        )
    )
    parties.append(bloc_code("Pipeline de la chaîne watershed, corps JSON", PIPELINE_JSON))
    parties.append(
        p(
            "Le paquet exécute ces étapes dans l'ordre, chronomètre chacune et garde le dernier "
            "masque produit. Une étape en échec lève une erreur qui porte son nom, ce qui évite de "
            "chercher l'origine dans un message générique."
        )
    )
    parties.append(bloc_code(*EXTRAITS[0][:2]))
    parties.append(
        p(
            "Côté API, la création d'analyse valide les étapes avant d'écrire quoi que ce soit, puis "
            "rend la main tout de suite avec un code 202 et un identifiant de tâche."
        )
    )
    parties.append(bloc_code(*EXTRAITS[1][:2]))
    parties.append(
        p(
            "L'API expose vingt routes, vingt-quatre opérations avec les méthodes HTTP, toutes "
            "décrites par le contrat OpenAPI généré au démarrage. Le front en dérive ses types au "
            "lieu de recopier les noms de champs, et le schéma du pipeline alimente directement les "
            "formulaires de l'inspecteur."
        )
    )
    parties.append(routes)
    parties.append(fin())

    # --- 4. Interface ---
    parties.append(h2("4", "Interface"))
    parties.append(
        figure(
            accueil,
            "Figure 2",
            "Page d'accueil, 1440 px de large : la promesse en deux phrases, puis l'espace de travail "
            "montré avec une image du cours et son masque.",
        )
    )
    parties.append(
        p(
            "La direction visuelle tient en trois règles. Le papier ivoire porte la page, la scène "
            "sombre porte l'image, et un seul vermillon par écran signale l'action qui compte, ici le "
            "bouton qui lance l'analyse."
        )
    )
    parties.append(
        p(
            "Les titres sont en Fraunces, le texte en Instrument Sans, les chiffres en JetBrains Mono "
            "à chasse fixe : les colonnes de mesures s'alignent d'elles-mêmes et les unités restent "
            "lisibles."
        )
    )
    parties.append(
        p(
            "Le canvas est le cœur de l'espace de travail. Il dimensionne son tampon sur le facteur "
            "de densité de l'écran, puis dessine l'image et le masque dans le même repère."
        )
    )
    parties.append(bloc_code(*EXTRAITS[2][:2]))
    parties.append(
        p(
            "Le masque n'est pas une image bitmap posée par-dessus : il est teinté une fois dans un "
            "canvas hors écran, puis posé avec une opacité réglable, ce qui laisse voir l'image "
            "dessous."
        )
    )
    parties.append(bloc_code(*EXTRAITS[3][:2], serre=True))
    parties.append(fin())

    # --- 5. Résultats mesurés ---
    parties.append(h2("5", "Résultats mesurés"))
    parties.append(
        p(
            "Les cinq chaînes prêtes à l'emploi ont été rejouées sur les démonstrations de l'API, avec "
            "le masque de référence fourni. Les scores ci-dessous sortent de la réponse de "
            "<code>POST /api/analyses</code>, pas d'un calcul à part."
        )
    )
    parties.append(
        tableau(
            "Tableau 4. Cinq chaînes prêtes à l'emploi, image du cours sauf le U-Net",
            [("Chaîne", False), ("Dice", True), ("IoU", True), ("Durée", True)],
            [
                ["Seuillage d'Otsu inversé", fr(otsu["dice"]), fr(otsu["iou"]), f"{otsu['total_ms']:.0f} ms"],
                ["k-means 3 classes", fr(kmeans["dice"]), fr(kmeans["iou"]), f"{kmeans['total_ms']:.0f} ms"],
                ["Watershed sur le gradient", fr(water["dice"]), fr(water["iou"]), f"{water['total_ms']:.0f} ms"],
                ["Contours actifs Chan-Vese", fr(chan["dice"]), fr(chan["iou"]), f"{chan['total_ms']:.0f} ms"],
                ["U-Net endoscopie", fr(unet["dice"]), fr(unet["iou"]), f"{unet['total_ms']:.0f} ms"],
            ],
            largeurs=["55%", "15%", "15%", "15%"],
        )
    )
    parties.append(
        p(
            "Le U-Net est mesuré sur une image de son jeu d'entraînement, donc dans son domaine : "
            f"{etape('unet', 'dl.unet_endoscopie'):.0f} ms d'inférence pour 0,959 de Dice, chiffre "
            "optimiste puisque la page d'accueil annonce 0,88. Les quatre autres chaînes travaillent "
            "sur l'image du cours."
        )
    )
    parties.append(
        p(
            "Le temps part dans l'algorithme lui-même : "
            f"{etape('kmeans', 'segment.kmeans'):.0f} ms sur {kmeans['total_ms']:.0f} pour l'étape "
            f"k-means, {etape('chan-vese', 'segment.chan_vese'):.0f} ms sur {chan['total_ms']:.0f} "
            f"pour Chan-Vese, {etape('watershed', 'segment.watershed'):.0f} ms sur "
            f"{water['total_ms']:.0f} pour le watershed. Les post-traitements restent sous 5 ms."
        )
    )
    parties.append(
        tableau(
            "Tableau 5. Recalage de la paire FIRE A01, dix points de contrôle",
            [("Méthode", False), ("Erreur moyenne", True), ("Succès à 10 px", True), ("NCC", True)],
            [
                [
                    "Homographie SIFT et MAGSAC",
                    f"{fr(reg['homography']['mean'], 2)} px",
                    f"{fr(reg['homography']['success'] * 100, 0)} %",
                    fr(reg["homography"]["ncc"]),
                ],
                [
                    "Affine",
                    f"{fr(reg['affine']['mean'], 2)} px",
                    f"{fr(reg['affine']['success'] * 100, 0)} %",
                    fr(reg["affine"]["ncc"]),
                ],
                [
                    "Flot optique global",
                    f"{fr(reg['optical_flow']['mean'], 2)} px",
                    f"{fr(reg['optical_flow']['success'] * 100, 0)} %",
                    fr(reg["optical_flow"]["ncc"]),
                ],
            ],
            largeurs=["42%", "20%", "20%", "18%"],
        )
    )
    parties.append(
        p(
            "Sur cette paire, l'affine est la plus proche : l'écart entre les deux rétines est surtout "
            "une rotation et une translation. L'homographie reste la méthode par défaut, parce qu'elle "
            "couvre les déformations projectives du reste du jeu."
        )
    )
    parties.append(
        paire(
            measures,
            watershed,
            "k-means réglé à la main : 0,422 et 729 ms, dont 713 ms pour l'étape k-means.",
            "Chaîne watershed : 0,907, 61 ms au total, dont 31 ms pour le watershed.",
            ("Figure 3a", "Figure 3b"),
        )
    )
    parties.append(
        encadre(
            "Lecture des résultats",
            [
                "Le watershed et le U-Net dominent, à 0,907 et 0,959 de Dice : la forme de la glotte "
                "ressort des deux côtés.",
                "Otsu seul échoue à 0,086 : la classe sombre du fond occupe presque toute l'image, "
                "donc le masque attrape le contour du champ de vision au lieu de la glotte.",
                "Entre les deux, k-means et Chan-Vese restent autour de 0,46 et 0,48, utiles pour "
                "montrer ce que donne une méthode nue.",
                "D'où les chaînes prêtes à l'emploi : un prétraitement, un post-traitement et une "
                "règle de choix de composante font plus que l'algorithme seul.",
            ],
        )
    )
    parties.append(fin())

    # --- 6. Recalage ---
    parties.append(h2("6", "Recalage"))
    parties.append(
        '<div class="split"><div class="visuel">'
        f'<img src="{checker}" alt="Page de recalage, vue en damier">'
        + legende_fig(
            "Figure 4",
            "Page de recalage sur la paire FIRE A01 : vue en damier, tableau des métriques et "
            "matrice 3 x 3.",
        )
        + '</div><div class="texte">'
        + p(
            "Le damier montre que les vaisseaux se raccordent de part et d'autre des cases : "
            "l'homographie ramène l'image mobile dans le repère de la fixe avec 2,87 px d'erreur "
            "moyenne sur les dix points."
        )
        + p(
            "Les dix points tombent tous sous 10 px, soit 100 pour cent de succès, et le NCC monte "
            f"à 0,937 après recalage. Le package, mesuré sur sa propre paire de test à résolution "
            f"doublée, donne {fr(paquet['homography']['mean_full_res'], 1)} px pour la même méthode : "
            "les deux valeurs sont du même ordre."
        )
        + p(
            "La matrice s'affiche en clair sous le damier : rotation de "
            f"{fr(rotation, 1)} degrés, translation de {translation_x:.0f} px en x et "
            f"{translation_y:.0f} px en y. Sa dernière ligne vaut 0,0000 0,0000 1,0000 : la "
            "déformation projective reste négligeable sur cette paire."
        )
        + "</div></div>"
    )
    parties.append(fin())

    # --- 7. Choix d'ingénierie et limites ---
    parties.append(h2("7", "Choix d'ingénierie et limites", flux=True))
    parties.append("<h3>Quatre décisions qui ont compté</h3>")
    parties.append(
        "<ul>"
        "<li><strong>Proxy de même origine.</strong> Le cookie de session est httpOnly et le canvas "
        "relit les pixels du masque : les deux exigent une seule origine. Une réécriture Next.js vers "
        "<code>/lum-api</code> règle les deux cas sans ouvrir CORS.</li>"
        "<li><strong>ONNX sur processeur, pas de serveur GPU.</strong> Les deux U-Net pèsent 7,8 Mo "
        f"chacun et l'inférence 256 x 256 prend {etape('unet', 'dl.unet_endoscopie'):.0f} ms. Louer un "
        "GPU pour cela coûterait plus cher que le temps gagné.</li>"
        "<li><strong>File de tâches interne plutôt que Redis.</strong> Un pool de threads dans le "
        "processus suffit pour une soutenance. Il tient la progression en base et la pousse en SSE, "
        "sans service supplémentaire à démarrer.</li>"
        "<li><strong>Presets plutôt que paramètres nus.</strong> Les cinq chaînes portent leurs "
        "scores attendus, donc l'utilisateur compare des résultats reproductibles au lieu de régler "
        "un seuil à l'aveugle.</li>"
        "</ul>"
    )
    parties.append("<h3>Trois limites assumées</h3>")
    parties.append(
        "<ul>"
        "<li>Pas de comptes utilisateurs : la session est un cookie anonyme, suffisant pour un "
        "atelier, insuffisant pour un usage réel.</li>"
        "<li>SQLite et stockage local ne sont pas distribués : deux instances de l'API ne partagent "
        "ni la base ni les fichiers.</li>"
        "<li>Le U-Net endoscopie ne connaît que son domaine : sur un autre cadrage il rend un masque "
        "vide, ce qui se voit à l'écran et doit être dit avant de conclure à un bug.</li>"
        "</ul>"
    )
    parties.append(
        p(
            "La suite est écrite dans <code>docs/DEPLOY.md</code> : interface sur Vercel, API sur "
            "Railway avec un volume pour <code>storage/</code> et la base, variables "
            "<code>LUMEN_*</code> posées au démarrage, vérification sur <code>/api/health</code>."
        )
    )
    parties.append(fin())

    # --- 8. Conclusion ---
    parties.append(h2("8", "Conclusion", flux=True))
    parties.append(
        "<ul>"
        "<li>La plateforme couvre les six ateliers du module dans une seule interface, du "
        "prétraitement à la comparaison chiffrée.</li>"
        "<li>Les scores obtenus reproduisent ceux du cours : 0,086 pour Otsu, 0,461 pour k-means, "
        "0,907 pour watershed, 0,959 pour le U-Net.</li>"
        "<li>Le recalage de la paire FIRE tombe à 2,87 px d'erreur moyenne, avec 100 pour cent des "
        "points sous 10 px et un NCC de 0,937.</li>"
        "<li>Le code reste séparé en trois couches testables, ce qui permet de changer une méthode "
        "sans toucher ni à l'API ni à l'interface.</li>"
        "</ul>"
    )
    parties.append(fin())

    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
        f"<title>{TITRE}</title>"
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500'
        '&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" '
        'rel="stylesheet">'
        f"<style>{CSS}</style></head><body>"
        + "".join(parties)
        + "</body></html>"
    )


# --- Vérification ---------------------------------------------------------------
def verifier_html(contenu: str) -> list[str]:
    rapport = []
    for caractere, nom in INTERDITS.items():
        nombre = contenu.count(caractere)
        rapport.append(f"{nom} dans le HTML : {nombre}")
        assert nombre == 0, f"{nom} présent dans le HTML"
    captures = len(re.findall(r"<img ", contenu))
    rapport.append(f"captures dans le HTML : {captures}")
    assert captures <= 6, "plus de six captures"
    for legende, extrait, source in EXTRAITS:
        assert extrait in source.read_text(encoding="utf-8"), f"extrait absent de {source.name}"
    rapport.append(f"extraits de code vérifiés dans les sources : {len(EXTRAITS)}")
    json.loads(PIPELINE_JSON)
    rapport.append("pipeline JSON : valide")
    for nom in ("Mme Wafa Rekik", "Oussema Harrabi"):
        assert nom in contenu, f"{nom} absent"
        rapport.append(f"nom présent : {nom}")
    return rapport


def imprimer_pdf() -> None:
    for navigateur in NAVIGATEURS:
        if Path(navigateur).is_file():
            commande = [
                navigateur,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--virtual-time-budget=15000",
                f"--print-to-pdf={PDF_SORTIE}",
                HTML_SORTIE.as_uri(),
            ]
            subprocess.run(commande, check=True, capture_output=True, timeout=300)
            return
    raise SystemExit("Chrome introuvable")


def verifier_pdf() -> list[str]:
    import fitz

    rapport = []
    document = fitz.open(PDF_SORTIE)
    pages = document.page_count
    rapport.append(f"pages : {pages} / 6")
    assert pages <= 6, f"{pages} pages, plafond à 6"
    texte = "\n".join(page.get_text() for page in document)
    for caractere, nom in INTERDITS.items():
        nombre = texte.count(caractere)
        rapport.append(f"{nom} dans le texte extrait : {nombre}")
        assert nombre == 0, f"{nom} dans le PDF"
    premiere = document[0]
    assert "Objectif et périmètre" not in premiere.get_text(), "titre de section en page 1"
    assert not premiere.get_images(), "image en page 1"
    rapport.append("page 1 : ni titre de section, ni image")
    for nom in ("Mme Wafa Rekik", "Oussema Harrabi"):
        assert nom in texte, f"{nom} absent du PDF"
        rapport.append(f"nom présent dans le PDF : {nom}")
    rapport.append(f"taille du PDF : {PDF_SORTIE.stat().st_size / 1024:.0f} Ko")
    document.close()
    return rapport


def rendre_pages(dossier: Path) -> list[str]:
    import fitz

    dossier.mkdir(parents=True, exist_ok=True)
    document = fitz.open(PDF_SORTIE)
    sorties = []
    for index, page in enumerate(document):
        pixmap = page.get_pixmap(dpi=110)
        chemin = dossier / f"page{index + 1}.png"
        pixmap.save(chemin)
        sorties.append(chemin.name)
    document.close()
    return sorties


def main() -> int:
    BUILD.mkdir(exist_ok=True)
    contenu = construire()
    HTML_SORTIE.write_text(contenu, encoding="utf-8")
    rapport = verifier_html(contenu)
    imprimer_pdf()
    rapport += verifier_pdf()
    rapport.append("rendus : " + ", ".join(rendre_pages(BUILD / "pages_at6")))
    print("\n".join(rapport))
    return 0


if __name__ == "__main__":
    sys.exit(main())
