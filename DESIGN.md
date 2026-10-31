# Design

## Theme

**Atlas scientifique.** Une coquille de papier ivoire, de l'encre, des filets fins et des chiffres alignés :
la plateforme se lit comme une planche d'atlas anatomique. Les images médicales, elles, vivent sur une
**scène sombre** (graphite neutre) qui laisse les masques et les contours ressortir.

La scène physique : un bureau éclairé en journée, un écran large, un étudiant qui compare deux
segmentations ; puis le même écran projeté en soutenance, à trois mètres. Le papier tient la lecture,
la scène sombre tient l'image. Aucun mode sombre global : la scène sombre est un **lieu**, pas un thème.

## Color

Stratégie **committed** : un papier chaud porte la surface, une encre profonde porte le texte et les
actions, un vermillon signale. Les teintes neutres sont légèrement teintées vers le chaud (papier) et le
froid (encre), jamais neutres pures. Pas de noir ni de blanc absolus.

```css
:root {
  /* Surfaces */
  --paper:        oklch(97.8% 0.010 85);   /* fond principal, ivoire */
  --paper-sunk:   oklch(95.4% 0.012 82);   /* zones en retrait, champs */
  --paper-raised: oklch(99.2% 0.006 85);   /* rares surfaces surélevées */
  --rule:         oklch(87.5% 0.012 80);   /* filets 1px */
  --rule-strong:  oklch(78.0% 0.014 80);

  /* Encre */
  --ink:          oklch(23.0% 0.020 265);  /* texte principal */
  --ink-soft:     oklch(43.0% 0.016 265);  /* texte secondaire */
  --ink-faint:    oklch(60.0% 0.012 265);  /* légendes, unités */

  /* Scène image (le seul endroit sombre) */
  --stage:        oklch(17.5% 0.012 265);
  --stage-raised: oklch(24.0% 0.014 265);
  --stage-rule:   oklch(32.0% 0.014 265);
  --stage-ink:    oklch(92.0% 0.008 265);

  /* Signal */
  --signal:       oklch(55.0% 0.170 32);   /* vermillon, actions et mesures clés */
  --signal-ink:   oklch(38.0% 0.130 32);   /* texte sur fond clair */
  --signal-wash:  oklch(94.0% 0.030 40);   /* fonds d'alerte doux */

  /* Séries de masques et de courbes (daltonien-safe, ordre fixe) */
  --series-1: oklch(58% 0.150 32);   /* vermillon */
  --series-2: oklch(62% 0.110 250);  /* indigo */
  --series-3: oklch(66% 0.100 150);  /* mousse */
  --series-4: oklch(72% 0.120 85);   /* ocre */
  --series-5: oklch(58% 0.110 320);  /* prune */
  --series-6: oklch(55% 0.020 265);  /* ardoise */
}
```

Règles : un seul vermillon par écran, réservé à l'action principale ou à la mesure qui tranche. Les
séries suivent toujours le même ordre, dans les légendes comme dans les tracés.

## Typography

- **Titres et légendes de planche : Fraunces** (variable, axe optique 9 à 144). Serif éditorial, utilisé
  en `400` avec un axe optique élevé pour les grands titres, en `500` pour les sous-titres.
- **Interface : Instrument Sans.** Neutre, légèrement condensée, excellente en petites tailles.
- **Données : JetBrains Mono.** Chiffres tabulaires obligatoires, unités en `--ink-faint`.

```css
--font-display: "Fraunces", Georgia, serif;
--font-ui:      "Instrument Sans", system-ui, sans-serif;
--font-mono:    "JetBrains Mono", ui-monospace, monospace;
```

Échelle (ratio 1.28, corps 16 px) : `12 / 13 / 15 / 16 / 20 / 26 / 34 / 44 / 58`. Titres en Fraunces,
corps en Instrument Sans. Longueur de ligne plafonnée à 68 caractères pour les paragraphes explicatifs.

## Layout

- Grille de 12 colonnes, gouttière 24 px, marge extérieure 32 px en dessous de 1280 px, 64 px au-delà.
- La page d'accueil est **asymétrique** : colonne de texte de 5 colonnes, image de planche de 7 colonnes,
  jamais centrée.
- L'espace de travail est une coquille fixe : rail gauche (documents et analyses) 280 px, scène au centre,
  inspecteur droit 360 px, barre d'outils horizontale au-dessus de la scène.
- Les sections respirent : 96 px entre blocs majeurs sur l'accueil, 32 px dans l'application.
- Aucune carte par défaut. Les blocs sont séparés par des filets `1px var(--rule)` et des changements de
  fond, pas par des boîtes flottantes. Les seules surfaces élevées sont la scène image et les menus.

## Components

**Bouton principal.** Fond `--ink`, texte `--paper`, rayon 2 px, hauteur 40 px, padding 16 px, majuscules
non, poids 500. État survol : `--ink` éclairci de 6 %. Un seul par écran.

**Bouton secondaire.** Transparent, filet `1px --rule-strong`, texte `--ink`. Même hauteur.

**Action signal.** `--signal` en fond, texte `--paper`. Réservé à « Lancer l'analyse ».

**Champs.** Fond `--paper-sunk`, filet bas `1px --rule-strong`, pas de boîte complète, focus en
`2px --signal` décalé de 2 px. Étiquette en 13 px `--ink-soft` au-dessus.

**Onglets de méthode.** Texte seul, filet bas 2 px `--signal` sur l'actif, espacement 24 px.

**Tableau de mesures.** En-tête en 12 px mono majuscules `--ink-faint`, lignes séparées par `1px --rule`,
chiffres en mono tabulaire alignés à droite, meilleure valeur en `--signal-ink` et graisse 600. Aucune
alternance de fond.

**Légende d'image.** `Figure 3` en mono 12 px `--ink-faint`, puis la description en 13 px `--ink-soft`,
placée sous l'image, alignée à gauche, largeur de l'image.

**Scène image.** Fond `--stage`, image centrée, aucun cadre autour de l'image elle-même. La barre d'outils
de la scène est en `--stage-raised`, texte `--stage-ink`, séparée par `1px --stage-rule`. Les calques
portent une pastille de série et une légende en mono.

**Curseur de comparaison.** Poignée verticale de 2 px `--paper` avec ombre douce, jamais un rond.

**État vide.** Un titre court en Fraunces, une phrase, une action : jamais d'illustration décorative.

## Motion

- Durées : 120 ms pour les micro-états (survol, focus), 220 ms pour les transitions de panneau, 320 ms pour
  l'apparition d'un résultat.
- Courbes : `cubic-bezier(0.22, 1, 0.36, 1)` (ease-out-quint). Aucun rebond.
- Le balayage de comparaison suit le curseur sans inertie. Le clignotement (flicker) est une alternance
  franche de 600 ms, désactivée si `prefers-reduced-motion`.
- Aucune animation sur les propriétés de mise en page ; uniquement `transform` et `opacity`.

## Iconography

Trait de 1,5 px, extrémités plates, grille de 24 px, dessinés à la main pour les gestes clés (importer,
superposer, comparer, mesurer). Pas de bibliothèque d'icônes générique pour les actions principales ; les
icônes utilitaires secondaires peuvent venir d'un jeu sobre, toujours en `--ink-soft`.

## Copy

- Titres qui nomment l'objet, pas l'action : « Comparaison des segmentations », pas « Comparez vos résultats ».
- Les nombres portent leur unité et leur méthode : « Dice 0,88 · U-Net · 50 époques ».
- Aucun point d'exclamation, aucun emoji, aucun tiret cadratin.
