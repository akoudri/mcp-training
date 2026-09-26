# Recette du socle et du LAB 0

**Date** : 26 septembre 2026 · **Exécutant** : agent d'implémentation (tâche 17) · **Dépôt** :
`pharos-labs` (`~/Training/pharos-labs`, branche `main`).

**Contexte** : l'amendement du contrôleur à la tâche 17 (aucune clé OpenRouter ni VM disponible pour
l'agent) prime sur le brief d'origine. Ce document couvre :

1. les six critères d'acceptation §19 de la spec, avec leur preuve ou, à défaut, la procédure à
   dérouler par le formateur ;
2. trois procédures pas à pas à exécuter par le formateur (chat réel V4, LAB 0 en participant,
   machines vierges) ;
3. les écarts constatés pendant la construction du kit.

---

## 1. Critères d'acceptation (spec §19)

| # | Critère | Statut | Preuve / procédure |
|---|---|---|---|
| 1 | Sur un Ubuntu 24.04 vierge **et** un Windows 11 + WSL2, en suivant `PREPARATION.md` sans autre intervention, `make doctor` affiche trois `OK`. | ⏳ à vérifier par le formateur | Aucune VM vierge disponible pour l'agent. La mécanique de `make doctor` est vérifiée par ailleurs sur ce poste : `make doctor SANS_MODELE=1` → `socle OK` / `serveur OK` (2 lignes) ; `make doctor` sans `.env` → `modèle ÉCHEC clé absente : renseigner OPENROUTER_API_KEY dans .env…` (comportement voulu, cf. constraints.md §5). Procédure complète : § « Machines vierges » ci-dessous. |
| 2 | Le socle du LAB 0 se déroule de bout en bout avec le modèle par défaut : les trois outils apparaissent dans VS Code, la question de référence produit une réponse, et l'observateur montre au moins un `tools/call` correspondant. | ✅ vérifié côté serveur / ⏳ partie VS Code + modèle réel à vérifier par le formateur | Côté serveur, sans modèle, depuis l'hôte (`fastmcp.Client("http://localhost:8100/mcp")`) : 3 outils exposés (`lire_document`, `lister_documents`, `rechercher_clause`) ; `lister_documents("ESC-2026-0412")` → 4 documents ; `rechercher_clause("ESC-2026-0412", "penalites")` renvoie l'article 7 contenant « 1 850 € ». Les deux appels apparaissent dans l'observateur (`GET /flows` de l'API mitmweb, `Authorization: Bearer pharos`) : 12 flux `POST /mcp`, dont un `tools/call rechercher_clause` et un `tools/call lister_documents` sur `ESC-2026-0412`, contenus vérifiés octet par octet. Partie VS Code + modèle OpenRouter réel : aucune clé disponible pour l'agent → procédure « V4 + chat réel » ci-dessous. |
| 3 | Les extensions A, B et C fonctionnent comme décrites dans le brief. | ✅ mécanique vérifiée / ⏳ instabilité du choix (extension B) à vérifier par le formateur | **A** : `make tokens-catalogue` → `rechercher_clause 499`, `lire_document 263`, `lister_documents 185`, total `947 tokens pour 3 outils` (après allongement de la description de `rechercher_clause` à la relecture finale : un outil hors de la fourchette 150-400 de FA1, les deux autres dedans). **B (mécanique)** ✅ : `make lab0-outil-jumeau` → 4 outils listés (`chercher_clause_contrat`, `lire_document`, `lister_documents`, `rechercher_clause`) ; `make lab0-up` → retour à 3 outils. **B (observation attendue)** ⏳ : l'extension demande de reposer la question de référence trois fois, en conversation vierge, avec un vrai modèle, pour constater que **le choix entre `rechercher_clause` et son jumeau devient instable** — cela nécessite un LLM réel (aucune clé disponible pour l'agent) et n'a pas été observé ici ; à faire par le formateur, procédure 2 ci-dessous. **C** ✅ : `make lab0-up VERBEUX=1` + un appel `lister_documents` → `logs/pharos-docs-demo.jsonl` contient des lignes `"sens": "recu"` et `"sens": "emis"` (requête et réponse JSON-RPC complètes) ; `make lab0-up` puis suppression de `logs/` effectuées. |
| 4 | `make test` passe ; la CI de `pharos-labs` est verte. | ✅ vérifié | `uv run pytest -q` → `63 passed`. `make test` (dans le conteneur `atelier`) → `63 passed`. `gh run list -L 3` → deux dernières exécutions `ci` à l'état `ok` (runs `36205862747`, `36205750504`). |
| 5 | Deux générations du corpus produisent des PDF identiques. | ✅ vérifié | `uv run pytest tests/test_generer.py -q` → `6 passed`, dont `test_generation_deterministe` (comparaison SHA-256 octet par octet entre deux générations dans des répertoires distincts) et `test_documents_versionnes_a_jour` (le corpus versionné dans `donnees/documents/` correspond à une génération fraîche). |
| 6 | Les retouches du §18 sont faites dans le dépôt de la formation. | ✅ vérifié | Dépôt `mcp-training`, tâche 16, commits `7d29755` (« docs: aligne le LAB 0, le deck et la spec sur le socle construit ») et `76ffe86` (« docs: retire les mentions résiduelles de MCPJam de la spec ») : ligne « Fourni » du LAB 0 mise à jour (client VS Code au lieu de « client graphique préconfiguré ») et piège « cache des outils » complété avec la manipulation VS Code (`labs/LAB00_premier_contact.md`, vérifié ligne 33 et section Pièges & indices). Deck (`Formation Agent MCP.pptx`) retouché aux slides **3 (PRÉ-TRAVAIL, P2)** et **484 (BLOC 25.1, piège FastMCP)**, cf. `task-16-report.md` — **`*.pptx` est volontairement dans `.gitignore` du dépôt de la formation : ces retouches sont sur disque, pas dans un commit**, donc non vérifiables par `git log` (seules `labs/LAB00_premier_contact.md` et la spec le sont). Une mention résiduelle de « MCPJam » subsiste au deck, slide 400 (BLOC 20.3, liste générale d'hôtes MCP Apps) : **hors périmètre du §18** (ce n'est pas la désignation du client des labs), reportée au formateur — voir « Écarts constatés » ci-dessous. |

---

## 2. Procédures à faire par le formateur

### Procédure 1 — V4 + chat réel (VS Code + OpenRouter)

**Prérequis** : `OPENROUTER_CLE_GESTION` (clé de gestion OpenRouter) disponible sur le poste du
formateur.

1. Créer une clé de test à usage unique :
   ```bash
   OPENROUTER_CLE_GESTION=… uv run python -m outils.cles_openrouter creer \
     --binomes 1 --plafond 1 --expiration <demain, ex. $(date -d demain +%F)>
   ```
   → produit `sortie/binome-1.env`.
2. `cp sortie/binome-1.env .env`
3. `make up && make lab0-up && make doctor` → **résultat attendu : trois lignes `OK`** (`socle`,
   `modèle`, `serveur`).
4. Ouvrir VS Code sur le dépôt (`make client` sous Linux, ou Remote-WSL sous Windows) et suivre
   `docs/decisions/client-graphique.md` (faire confiance au dossier, saisir la clé OpenRouter dans
   **Manage Language Models → Add Models → OpenRouter**, choisir `google/gemini-3.6-flash`, copier
   `labs/lab0/client.config.json` en `.vscode/mcp.json`, démarrer le serveur MCP via la palette).
5. En conversation vierge, mode **PHAROS** (sélecteur de mode du chat ; pas *Agent*, qui peut lire
   la réponse dans les fichiers du dépôt), poser **trois fois** mot pour mot :
   > Résume les obligations de l'opérateur portuaire dans le contrat de manutention de l'escale
   > ESC-2026-0412.

   Après chaque essai, relever dans l'Inspector (`http://localhost:7001`, mot de passe `pharos`)
   les `tools/call` effectués.
6. **Critère** : au moins **deux essais sur trois** doivent appeler `rechercher_clause` ou
   `lire_document` sur le document `CM-0412`.
   - Si le critère est atteint : consigner les trois traces d'appels ici.
   - Si le critère **n'est pas atteint** : reprendre les étapes 3 à 6 avec le modèle
     `openai/gpt-5.4-mini`, puis, si ce modèle satisfait le critère, mettre à jour
     `PHAROS_MODELE` par défaut dans `.env.example` **et** dans `outils/cles_openrouter.py`
     (seul cas où ces deux fichiers peuvent être modifiés — l'agent de la tâche 17 ne les a pas
     touchés, conformément à l'amendement).
7. Vérifier, si le temps le permet, les 6 points « À vérifier par le formateur » listés en fin de
   `docs/decisions/client-graphique.md` (fichier `chatLanguageModels.json`, présélection du modèle,
   absence de mur d'inscription, chat Copilot sous Remote-WSL, fiabilité de l'appel d'outils).
8. Fin de session :
   ```bash
   OPENROUTER_CLE_GESTION=… uv run python -m outils.cles_openrouter revoquer
   ```
   **Résultat attendu** : la clé `pharos-binome-1` n'apparaît plus dans `etat` ; `.env` retiré ou
   remplacé si le poste doit resservir.

### Procédure 2 — Dérouler le LAB 0 comme un participant

Suivre `labs/LAB00_premier_contact.md` à la lettre (module FA2, 45 minutes), en consignant pour
chaque étape **OK** ou l'écart constaté et sa correction :

| Étape | Attendu | OK / Écart |
|---|---|---|
| 1 — Brancher le serveur sur le client | `pharos-docs-demo` listé, 3 outils visibles | |
| 2 — Question de référence | Une réponse est produite | |
| 3 — Ouvrir l'Inspector, remplir la fiche de trace | Au moins un appel d'outil visible ; `labs/lab0/trace.md` rempli (ordre, outil, arguments, taille du résultat, utile ?) | |
| 4 — Question plus vague, seconde fiche de trace | Écart du nombre d'appels entre les deux questions constaté | |
| Extension A — coût du catalogue | `make tokens-catalogue` exécuté, écart avec 150-400 tokens/outil expliqué | |
| Extension B — outil jumeau | `make lab0-outil-jumeau`, 3 essais depuis une conversation vierge, choix instable constaté | |
| Extension C — trafic brut | `make lab0-up VERBEUX=1`, `logs/pharos-docs-demo.jsonl` lu, mêmes informations que l'Inspector retrouvées | |
| Critère décisif | Capable de citer, sans relire la réponse, les outils appelés, l'ordre, les arguments | |

Livrable attendu : `labs/lab0/trace.md` avec les deux fiches remplies, commité sur la branche du
binôme (`git add labs/lab0/trace.md && git commit -m "LAB 0 — fiches de trace"`).

### Procédure 3 — Machines vierges

Sur une VM **Ubuntu 24.04 vierge** et une VM **Windows 11**, dérouler `PREPARATION.md` sans autre
intervention :

1. Chronométrer chaque section (Windows uniquement / Linux ou WSL / client graphique / vérification
   finale).
2. Consigner toute étape manuelle **non prévue** par `PREPARATION.md` et l'ajouter au document.
3. **Résultat attendu** : `make doctor` affiche trois `OK` en fin de procédure, sans intervention
   hors `PREPARATION.md`.
4. **VM Windows (Remote-WSL)** : les ports sont liés à `127.0.0.1` **dans WSL** ; vérifier
   explicitement que le transfert de ports de WSL les rend joignables depuis Windows :
   - le navigateur **Windows** ouvre http://localhost:7001 (Inspector — observateur de trafic, mot
     de passe `pharos`) ;
   - VS Code (fenêtre Remote-WSL) joint http://localhost:8100/mcp : palette > « MCP: List Servers »
     > `pharos-docs-demo` > *Start* → 3 outils listés.
   En cas d'échec, consigner la version de WSL (`wsl --version`) et le mode réseau
   (`networkingMode` dans `%UserProfile%\.wslconfig`).
5. **Rappel** : le dépôt `pharos-labs` est **privé**. Prévoir avant la session soit une clé de
   déploiement SSH (lecture seule) provisionnée sur chaque poste, soit un accès en lecture pour le
   centre de formation — `outils/preparer-pc.sh` suppose déjà l'un des deux (voir sa case à cocher
   dans `PREPARATION.md`).

---

## 3. Écarts constatés pendant la construction

- **`docs/decisions/client-graphique.md` — points « à vérifier par le formateur »** : cinq points
  établis par lecture de code lors du spike VS Code, jamais vérifiés par une exécution réelle
  (fichier `chatLanguageModels.json` avec clé pré-provisionnée, présélection de
  `chat.defaultModel`, absence de mur d'inscription en mode déconnecté, exécution du chat Copilot
  côté serveur sous Remote-WSL, fiabilité de l'appel d'outils par Gemini 3.6 Flash à travers
  l'observateur). Reportés à la procédure 1 ci-dessus.
- **Identifiant `ghcr.io` expiré dans la configuration Docker du poste formateur** : constaté à la
  tâche 8 (`docker build` échouait sur `COPY --from=ghcr.io/astral-sh/uv:0.6.12 ...` avec
  `failed to authorize: denied: denied`, `~/.docker/config.json` contenant un jeton GitHub expiré
  pour `ghcr.io` que Docker préfère à un accès anonyme). Contournement : préfixer les commandes
  `docker`/`make` avec `DOCKER_CONFIG=<répertoire vide>` pour forcer un accès anonyme, sans modifier
  le fichier réel de l'utilisateur. Sur ce poste, à la tâche 17, l'image `pharos/python:1` et
  l'image intermédiaire `ghcr.io/astral-sh/uv:0.6.12` étaient déjà en cache local : `make construire`
  a réussi sans avoir besoin du contournement. Le risque reste latent pour quiconque reconstruit
  l'image à partir de rien sur un poste avec la même configuration Docker expirée (la CI GitHub
  Actions n'est pas concernée : runner neuf, accès anonyme à `ghcr.io`).
- **Mention résiduelle de « MCPJam » dans le deck de formation** : slide 400, BLOC 20.3
  (« Le support, et ce qu'on en fait »), dans une liste générale d'hôtes MCP Apps (« Les clients
  Claude en ligne et sur poste, VS Code avec Copilot, Goose, Postman, MCPJam »). Ce n'est pas la
  désignation du client des labs (déjà retouchée à la tâche 16), donc hors périmètre du §18 — mais
  la liste elle-même est signalée comme à revérifier avant toute décision. Laissée en l'état,
  décision à trancher par le formateur.

---

## 4. Commandes exécutées par l'agent (tâche 17), avec extraits de sortie

```
$ uv run pytest -q
63 passed in 4.44s

$ make construire
[...] toutes les couches CACHED, naming to docker.io/pharos/python:1 done

$ make up && make lab0-up
[...] Observateur : http://localhost:7001 (mot de passe : pharos)
[...] pharos-docs-demo : http://observateur:8100/mcp (depuis le client), http://localhost:8100/mcp (depuis le poste)

$ tests/integration/test_observateur.sh
OK ['lire_document', 'lister_documents', 'rechercher_clause']
--- ordre inverse : serveur d'abord, observateur ensuite
OK ['lire_document', 'lister_documents', 'rechercher_clause']
UI observateur : 403

$ make doctor SANS_MODELE=1
  socle     OK     observateur joignable
  serveur   OK     pharos-docs-demo expose 3 outils via l'observateur

$ make doctor        # sans .env
  socle     OK     observateur joignable
  modèle    ÉCHEC  clé OpenRouter absente : renseigner OPENROUTER_API_KEY dans .env (remise par le formateur).
  serveur   OK     pharos-docs-demo expose 3 outils via l'observateur

$ make tokens-catalogue
  rechercher_clause             499          292         108     18
  lire_document                 263           75          79      0
  lister_documents              185           78          51      0
  Total : 947 tokens pour 3 outils, payés à chaque tour de la boucle.

$ make lab0-outil-jumeau   # puis vérification côté client fastmcp
outils (jumeau actif): ['chercher_clause_contrat', 'lire_document', 'lister_documents', 'rechercher_clause'] -> 4
$ make lab0-up
outils (retour à la normale): ['lire_document', 'lister_documents', 'rechercher_clause'] -> 3

$ make lab0-up VERBEUX=1   # puis un appel lister_documents
$ cat logs/pharos-docs-demo.jsonl | tail -1
{"horodatage": "...", "sens": "emis", "message": {"jsonrpc": "2.0", "id": 2, "result": {...}}}
$ make lab0-up && rm -r logs/

$ uv run pytest tests/test_generer.py -q
6 passed in 2.18s

$ gh run list -L 3
[ok] ci [36205862747]
[ok] ci [36205750504]

$ make test
63 passed in 8.51s

$ make down
[...] Container pharos-observateur-1 Removed
[...] Container pharos-pharos-docs-demo-1 Removed
[...] Network pharos_pharos Removed
```

`docker ps -a` en fin de tâche : seul `backend-postgres` (conteneur sans rapport avec ce projet)
reste en cours d'exécution ; aucun conteneur `pharos-*` restant ; aucun `docker system prune`
exécuté.
