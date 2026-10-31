# Mise en ligne

Deux chemins possibles, aucun ne demande de carte bancaire.

| Chemin | API | Interface | Comptes |
|---|---|---|---|
| A. Recommandé | Render (Docker, plan gratuit) | Vercel | Render + Vercel |
| B. Démonstration sans hébergeur | ta machine, exposée par un tunnel | ta machine | aucun |

Écartés après essai : Railway (inscriptions fermées) et Hugging Face Spaces (les Spaces Docker sur
matériel gratuit exigent désormais un abonnement PRO).

## A. API sur Render

1. render.com, compte gratuit (connexion GitHub), puis `New` et `Blueprint`.
2. Choisir le dépôt `OussemaHarrabi/Lumen`. Render lit `render.yaml` : service Docker construit depuis
   `apps/api/Dockerfile`, contexte à la racine du dépôt, santé sur `/api/health`, plan gratuit.
3. `Apply`. La première construction prend 5 à 8 minutes (OpenCV, ONNX Runtime, deux modèles).
4. Noter l'URL `https://lumen-api-xxxx.onrender.com` et vérifier `/api/health` : la réponse doit annoncer
   `status: ok` et `endoscopie` et `busi` à `true`.

Le plan gratuit dispose de 512 Mo de mémoire : l'API en utilise 180 Mo après une inférence U-Net, la marge
est suffisante. Le service s'endort après quinze minutes d'inactivité et se réveille au premier appel, en
30 à 60 secondes. Aucun disque : la base et les fichiers vivent dans `/tmp` et sont recréés au réveil, ce
qui est sans conséquence puisque les exemples sont embarqués dans l'image.

## Interface sur Vercel

1. vercel.com, compte gratuit (connexion GitHub), puis `Add New` et `Project`.
2. Importer `OussemaHarrabi/Lumen`.
3. **Root Directory : `apps/web`**. Sans ce réglage, la construction échoue : le dépôt n'est pas une
   application Next.js à la racine.
4. Framework détecté : Next.js. `apps/web/vercel.json` fixe l'installation hors espace de travail pnpm,
   ce qui évite que Vercel remonte à la racine du dépôt pour chercher un autre verrou.
5. Variable d'environnement `NEXT_PUBLIC_API_URL` = URL de l'API Render, sans barre oblique finale.
   Elle est lue à la construction parce que le proxy `/lum-api` est figé dans le build : si l'URL change,
   relancer un déploiement.
6. `Deploy`, puis ouvrir l'URL, charger un exemple et lancer une analyse.

L'interface passe par `https://<projet>.vercel.app/lum-api/...`, que Vercel relaie vers l'API : le cookie
de session reste same-origin, le canvas lit les pixels sans restriction, et aucun réglage CORS n'est
nécessaire.

## B. Démonstration sans hébergeur

Tout tourne sur la machine, le tunnel fournit une URL publique temporaire.

```bash
cd lumen
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --app-dir apps/api
cd apps/web && NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 pnpm dev
```

Puis, dans un troisième terminal, une fois `cloudflared` installé (`winget install Cloudflare.cloudflared`) :

```bash
cloudflared tunnel --url http://localhost:3000
```

L'URL `https://<mots>.trycloudflare.com` s'affiche. Elle change à chaque lancement et la machine doit
rester allumée, mais aucun compte n'est nécessaire. Si l'URL est figée dans un déploiement Vercel, il faut
rebâtir l'interface avec la nouvelle valeur de `NEXT_PUBLIC_API_URL`.

## C. Variante tout en Docker

`infra/docker-compose.yml` lance l'API et l'interface avec un volume pour la base et les fichiers. Sur une
machine ou un serveur personnel, ajouter Caddy devant les deux services pour un nom de domaine et HTTPS
automatique.

## Vérifications avant la soutenance

- `GET /api/health` annonce les deux modèles.
- Watershed sur l'exemple du cours : Dice 0,907 ; k-means : 0,461 ; U-Net sur son image d'entraînement :
  0,959.
- Recalage de la paire FIRE : 2,87 px d'erreur moyenne, 100 % de réussite à 10 px.
- Un fichier de 26 Mo est refusé avec un message clair.
- L'interface tient sur un écran de téléphone (390 px) sans débordement.
