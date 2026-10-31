# Product

## Register

product

## Users

Deux publics, un seul produit.

**Étudiants en traitement d'images médicales.** Ils préparent un TP, importent des images endoscopiques,
mammaires ou rétiniennes, appliquent un prétraitement puis plusieurs segmentations, et doivent comparer
objectivement les résultats (Dice, IoU, temps). Ils connaissent les algorithmes mais pas forcément l'outil :
l'interface doit rendre chaque paramètre évident et chaque résultat vérifiable.

**Enseignante et jury de soutenance.** Ils découvrent la plateforme en démonstration, à distance, sur un
projecteur. Ils regardent d'abord si le propos est clair, puis si les chiffres affichés correspondent à
ce que les algorithmes font réellement.

Le contexte d'usage est double : un travail attentif au bureau, sur écran large, et une démonstration
publique où tout doit rester lisible à trois mètres.

## Product Purpose

Réunir dans une seule application la chaîne complète du cours : lecture et description d'image,
prétraitement, segmentation conventionnelle (seuillage, k-means, MeanShift, morphology, watershed,
level-set), segmentation profonde (U-Net), recalage, et évaluation chiffrée des résultats.

Le produit existe pour remplacer la juxtaposition de notebooks par un poste de travail cohérent, où une
analyse est reproductible, comparable et exportable.

La réussite se mesure à trois choses : une analyse complète se fait sans lire de code, la comparaison
entre méthodes tient dans un écran, et chaque chiffre affiché est traçable jusqu'aux paramètres qui l'ont
produit.

## Brand Personality

Précis, calme, éditorial.

La voix est celle d'un atlas scientifique : des titres qui nomment, des légendes qui datent et mesurent,
des chiffres alignés. Pas de superlatifs, pas de promesse marketing, pas d'enthousiasme artificiel.
L'émotion visée est la confiance : on doit sentir que l'outil dit la vérité sur ce qu'il calcule.

## Anti-references

- Les tableaux de bord SaaS génériques : grille de cartes identiques, grand chiffre suivi d'une étiquette,
  dégradés d'accent, ombres portées partout.
- L'esthétique « santé » attendue : blanc pur, bleu ciel et turquoise, coins très arrondis, illustrations
  plates de médecins.
- Les interfaces de logiciels médicaux anciens : gris Windows, bordures biseautées, densité sans hiérarchie.
- Le style « laboratoire sombre » utilisé comme décor : noir partout, néons, glassmorphism.

## Design Principles

1. **L'image est le sujet.** Le reste de l'interface s'efface : marges larges, chrome discret, aucun
   élément décoratif qui concurrence la scène d'image.
2. **Montrer, puis expliquer.** Chaque résultat arrive avec sa mesure et son temps, à côté du visuel,
   jamais dans un onglet séparé.
3. **Un instrument, pas un gadget.** Un réglage qui ne change rien visiblement ne mérite pas d'être affiché ;
   à l'inverse, tout réglage affiché doit agir de façon perceptible et immédiate.
4. **Traçable par construction.** Chaque analyse conserve son pipeline, ses paramètres et ses durées ;
   l'interface peut les remontrer à tout moment.
5. **Lisible en soutenance.** Contrastes francs, tailles généreuses, chiffres tabulaires : ce qui compte
   doit se lire à distance sans effort.

## Accessibility & Inclusion

- Cible WCAG 2.2 niveau AA : contrastes vérifiés, navigation clavier complète, focus visible, libellés
  explicites, messages d'erreur qui disent quoi faire.
- Les calques de masque ne reposent jamais sur la seule teinte : chaque masque porte aussi un motif de
  contour et une légende, pour rester distinguable en cas de daltonisme.
- Respect de `prefers-reduced-motion` : les animations de comparaison (clignotement, balayage) sont
  désactivées ou remplacées par un état statique.
- Interface bilingue français et anglais, avec des libellés courts qui ne cassent pas la mise en page.
