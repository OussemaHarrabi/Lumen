# Mise en ligne

Trois chemins possibles pour rendre la plateforme accessible. Aucun ne demande de carte bancaire.

| Chemin | API | Interface | Comptes nécessaires |
|---|---|---|---|
| A. Recommandé | Hugging Face Space (Docker) | Vercel | Hugging Face + Vercel |
| B. Alternative | Render (Blueprint) | Vercel | Render + Vercel |
| C. Démonstration locale | ta machine | ta machine | aucun |

## Ce qu'il faut me transmettre

| Élément | Pourquoi |
|---|---|
| Jeton GitHub en écriture sur `OussemaHarrabi/Lumen` | pousser le code (le dépôt est vide à ce jour) |
| Jeton Hugging Face en écriture | créer et alimenter le Space de l'API |
| Jeton Vercel, ou accès au tableau de bord | créer le projet web et poser l'URL de l'API |
| Domaine, facultatif | URL lisible ; sinon les URL fournies par Vercel et Hugging Face suffisent |

## A. API sur Hugging Face Spaces (recommandé)

Gratuit, sans carte, 16 Go de mémoire, URL publique immédiate. Le disque étant éphémère, la base et les
images sont recréées à chaque redémarrage : sans conséquence ici, les exemples sont embarqués et recopiés
dans la session à la demande.

1. Sur huggingface.co, `New Space`, nom `lumen-api`, **SDK Docker**, matériel CPU basic, visibilité publique.
2. Le contenu à pousser est déjà assemblé par `python infra/hf-space/assemble.py` dans
   `infra/hf-space/build/` (90 fichiers, 17 Mo : code de l'API, package `lumen_cv`, deux modèles ONNX).
3. Pousser ce dossier sur le dépôt du Space :

```bash
cd infra/hf-space/build
git init && git add . && git commit -m "API Lumen"
git remote add space https://huggingface.co/spaces/<compte>/lumen-api
git push space main
```

L'authentification se fait avec le jeton Hugging Face comme mot de passe.

4. Le Space construit l'image (3 à 6 minutes) puis expose
   `https://<compte>-lumen-api.hf.space`. Vérifier `https://<compte>-lumen-api.hf.space/api/health` :
   la réponse doit annoncer `status: ok` et les deux modèles.
5. Le premier appel après une période d'inactivité réveille le Space (quelques secondes). Pour une
   soutenance, ouvrir la page `…/docs` deux minutes avant pour le réveiller.

## B. API sur Render (alternative)

1. render.com, nouveau compte, puis `New` puis `Blueprint`, choisir le dépôt GitHub.
2. Render lit `render.yaml` : service Docker construit depuis `apps/api/Dockerfile`, santé sur
   `/api/health`, plan gratuit.
3. Le plan gratuit s'endort après quinze minutes d'inactivité et ne propose pas de disque : l'API utilise
   donc `/tmp` pour la base et les fichiers, ce qui suffit pour une démonstration.
4. Récupérer l'URL `https://lumen-api-xxxx.onrender.com` et la vérifier sur `/api/health`.

## Interface sur Vercel

Identique dans les deux cas.

1. vercel.com, `Add New` puis `Project`, importer le dépôt `OussemaHarrabi/Lumen`.
2. **Root Directory : `apps/web`** (le dépôt n'est pas une application à la racine ; sans ce réglage, la
   construction échoue).
3. Framework détecté : Next.js. Ne rien changer aux commandes de construction.
4. Variable d'environnement : `NEXT_PUBLIC_API_URL` = URL publique de l'API, sans barre oblique finale,
   par exemple `https://oussemaharrabi-lumen-api.hf.space`. Elle est lue au moment de la construction, car
   le proxy `/lum-api` est figé dans le build : si l'URL change, relancer un déploiement.
5. Déployer, ouvrir l'URL `https://<projet>.vercel.app`, vérifier `Espace de travail`, charger un exemple
   et lancer une analyse.

Le navigateur n'appelle jamais l'API directement : il passe par `https://<projet>.vercel.app/lum-api/...`,
que Vercel relaie vers l'API. Le cookie de session reste donc same-origin et le canvas peut lire les
pixels. Aucun réglage CORS n'est nécessaire.

## C. Démonstration locale

```bash
cd lumen
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --app-dir apps/api
cd apps/web && NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 pnpm dev
```

Tout reste sur la machine, aucune connexion nécessaire. Pour exposer ponctuellement, un tunnel
(`cloudflared tunnel --url http://localhost:3000`) donne une URL publique temporaire, à condition de
rebâtir l'interface avec cette URL comme `NEXT_PUBLIC_API_URL`.

## Vérifications avant la soutenance

- `GET /api/health` annonce les deux modèles.
- Une analyse sur l'exemple endoscopie donne Dice 0,907 avec le preset Watershed, 0,461 avec k-means,
  0,959 avec U-Net sur l'exemple du jeu U-Net.
- Le recalage de la paire FIRE donne 2,87 px d'erreur moyenne et 100 % de réussite à 10 px.
- Un fichier de 26 Mo est refusé avec un message clair.
- L'interface tient sur un écran de téléphone (390 px), sans débordement.

## Sauvegarde

En mode A et B, le disque est éphémère : rien à sauvegarder, les exemples sont dans l'image. En mode C, la
base `lumen.db` et le dossier `storage/` restent sur la machine.
