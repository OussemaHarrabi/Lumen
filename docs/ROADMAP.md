# Lumen : feuille de route

Chaque phase se termine par une vérification observable. Rien n'est déclaré terminé sans avoir été
exécuté et regardé.

## Phase 0 : fondations

- Monorepo : `apps/web`, `apps/api`, `apps/worker`, `packages/cv`, `packages/contracts`, `infra/`, `docs/`.
- `docker compose` : postgres 16, redis 7, minio, api, worker, web, caddy.
- Outillage : ruff + mypy côté Python, eslint + prettier + tsc côté TypeScript, pytest, Playwright.
- CI : tests Python, tests API, build web.
- Export OpenAPI et génération des types TypeScript.

Vérification : `docker compose up` démarre la pile, `/api/health` répond, `pnpm build` passe, `pytest` passe.

## Phase 1 : cœur de traitement (`packages/cv`)

Portage fidèle des ateliers, avec les mêmes algorithmes et les mêmes paramètres par défaut :

1. `io` : lecture, conversions BGR/RGB, vidéo vers séquence, redimensionnement, binarisation.
2. `preprocess` : moyenneur, médian, gaussien, CLAHE, égalisation, conversion en gris.
3. `segment` : seuil manuel, Otsu, k-means, MeanShift (avec sous-échantillonnage), watershed, Chan-Vese,
   morphologie (érosion, dilatation, ouverture, fermeture, gradient), extraction de contours.
4. `metrics` : Dice, IoU, rappel, précision, matrice de confusion, temps de calcul.
5. `registration` : translation par corrélation de phase, affine et homographie par points, flot optique
   de Farnebäck, NCC, MSE, NMI, erreur sur landmarks.
6. `dl` : inférence ONNX des deux U-Net, post-traitement (seuil, ouverture, plus grande composante).
7. `pipeline` : exécution ordonnée avec traçage.

Vérification : tests unitaires avec les valeurs de référence des ateliers (Dice attendu, indices de cycle,
erreur médiane des landmarks) à 1 % près, et une image de bout en bout traitée en moins d'une seconde hors
inférence.

## Phase 2 : API

- Authentification (inscription, connexion, jeton, rôles), limitation de débit.
- Assets : téléversement avec contrôle du type réel, métadonnées calculées à l'import, URL présignées.
- Analyses : création avec pipeline JSON, exécution en tâche de fond, SSE d'avancement, récupération des
  résultats et des métriques.
- Recalage : création d'une paire, exécution, landmarks, métriques.
- Démonstration : images d'exemple préchargées (frame442 et son masque, paire BAGLS, image BUSI, paire FIRE,
  séquence endoscopique).
- Schéma de pipeline exposé en JSON Schema (une entrée par étape et par paramètre).

Vérification : tests API (httpx) sur les parcours complets, temps de réponse sous 200 ms hors calcul,
contrat OpenAPI valide, tâche longue visible en SSE.

## Phase 3 : socle d'interface

- Système de design : tokens OKLCH, typographie, espacements, composants de base, mode clair.
- Page d'accueil : récit du produit, démonstration immédiate, modules, méthodologie, appel à l'action.
- Coquille applicative : navigation, sélecteur d'image, panneau d'inspector, zone de travail.
- `ImageCanvas` : zoom, déplacement, calques masque et contour, opacité, lecture de pixel, histogramme.

Vérification : parcours accueil vers espace de travail, image affichée au pixel, zoom à la molette,
masque superposé, aucun décalage de rendu en DPR 2.

## Phase 4 : modules d'analyse

- Prétraitement et segmentation conventionnelle : formulaires générés depuis le schéma, exécution, calques.
- Segmentation profonde : choix du modèle, seuil, nettoyage, comparaison avec le conventionnel.
- Comparaison : grille 2 x 2, curseur avant/après, damier, clignotement, tableau de métriques.
- Recalage : paire d'images, transformation, points de contrôle, erreur, vues fusionnées.

Vérification : chaque module exécuté sur une image réelle depuis l'interface, métriques cohérentes avec
celles des ateliers, comparaison lisible sur capture.

## Phase 5 : traçabilité et sorties

- Historique des analyses, réouverture, duplication des paramètres.
- Export PNG (masque, superposition), JSON (métriques, paramètres), ZIP d'une analyse.
- Rapport PDF d'une analyse (même mise en page que les rapports d'atelier).

Vérification : export ouvert et relu, rapport généré contenant les figures et les métriques réelles.

## Phase 6 : finition et mise en ligne

- Accessibilité : navigation clavier, contrastes AA, libellés de formulaires, annonces de chargement.
- Performance : budget de première peinture, images servies à la bonne taille, mémoïsation du rendu canvas.
- Tests de bout en bout Playwright sur trois parcours : import et segmentation, comparaison, recalage.
- Déploiement Docker sur le serveur retenu, TLS, sauvegarde de la base, journalisation.
- Documentation : README d'installation, guide utilisateur d'une page, captures d'écran.

Vérification : URL publique en HTTPS, parcours complet rejoué par Playwright sur l'environnement déployé.
