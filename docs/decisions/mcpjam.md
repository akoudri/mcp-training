# Décision — client graphique MCPJam Inspector 3.12.0 (vérification V2)

Date de la vérification : 25 septembre 2026. Source examinée : dépôt `github.com/MCPJam/inspector`,
tag `v3.12.0` (commit `10ba7a7`), et paquet npm `@mcpjam/inspector@3.12.0`.

> **Arbitrage du formateur requis** (voir « Conséquences » en fin de document) : la clé OpenRouter
> ne peut **pas** être utilisée dans MCPJam 3.12.0 servi sur `http://localhost:7000`. Le client
> fonctionne en mode invité (serveur listé, trois outils, appels d'outils visibles dans
> l'observateur, prompt système), mais avec les modèles gratuits hébergés par MCPJam, pas avec
> `google/gemini-3.6-flash` via OpenRouter.

## Réponses aux cinq questions

### 1. Tag, Dockerfile, port d'écoute interne

- Tag : `v3.12.0` (existe aussi `v3.12.1`, non retenu : on épingle la version de la spec).
  Preuve : `git ls-remote --tags https://github.com/MCPJam/inspector | grep 3.12`.
- Le dépôt est un monorepo npm ; le Dockerfile de production est `mcpjam-inspector/Dockerfile`
  (contexte = racine du dépôt). Il fait `npm ci` sur les treize espaces de travail (applications
  Slack et Discord comprises), reconstruit le client Vite avec 4 Go de tas et installe Chromium
  par Playwright (`npx playwright install --with-deps chromium`).
- **Choix retenu** : ne pas reconstruire le monorepo. `images/mcpjam/Dockerfile` installe le
  paquet npm publié par l'amont, `@mcpjam/inspector@3.12.0`, qui contient déjà `dist/client` et
  `dist/server` (vérifié par `npm pack` + `tar tzf`) : c'est le binaire que lance
  `npx @mcpjam/inspector`. Construction en 27 s au lieu d'un build de plusieurs minutes et de
  plusieurs Go ; Chromium (sondes de widgets) n'est pas nécessaire au LAB 0. On reprend de l'amont
  la base `node:24.14.0-bookworm-slim` et `DOCKER_CONTAINER=true`, qui fait écouter le serveur sur
  `0.0.0.0` au lieu de `127.0.0.1` (`server/index.ts`, `const hostname = isDocker ? "0.0.0.0" : "127.0.0.1"`).
  Limite : les dépendances transitives du paquet ne sont pas verrouillées (intervalles `^`).
- Port interne : **6274**. Preuve : `mcpjam-inspector/bin/start.js`,
  `const requestedPortValue = envVars.PORT || "6274";` (« Fixed port policy ») ; `EXPOSE 6274`
  dans le Dockerfile amont ; `curl http://localhost:7000/health` renvoie
  `{"status":"ok",…,"version":"3.12.0"}` avec le mappage `7000:6274`.

### 2. Fichier de configuration des serveurs

- Option : `--config <fichier>` (`bin/start.js`, `arg === "--config"`), avec `--server <nom>`
  pour ne connecter automatiquement qu'un serveur. Le fichier est lu **au démarrage** et passé au
  serveur dans `MCP_CONFIG_DATA` : tout changement exige `make client-redemarrer`.
- Format : `{"mcpServers": {"<nom>": {"url": "http://…"}}}` ; une entrée avec `url` est de type
  `http` (Streamable HTTP), sans `url` de type `stdio` (`server/index.ts`, `getMCPConfigFromEnv`).
  Clés facultatives : `headers`, `useOAuth`, `type`. `labs/lab0/client.config.json` a le bon format
  (journal : `MCP config loaded with 1 server(s)`, `Servers: pharos-docs-demo`).
- **Mais** le navigateur n'applique ce fichier qu'à un utilisateur **connecté à un compte MCPJam**
  (WorkOS) disposant d'un projet dans le nuage MCPJam (Convex) :
  `client/src/hooks/use-server-state.ts`, `processCliConfig` → `if (!hasSignedInUser) { requestCliSignIn(); return; }`.
  En invité, un fichier non vide déclenche une redirection vers la connexion, qui échoue sur le
  port 7000 (voir question 3). Constaté : redirection vers
  `https://login.mcpjam.com/redirect-uri-invalid?invalid_redirect_uri=http://localhost:7000/callback`.
  Avec `{"mcpServers": {}}` (valeur créée par `make up` / `make client`), pas de redirection.

### 3. Injection de la clé OpenRouter

- **Aucune** variable d'environnement ni fichier de réglages côté serveur. Les clés sont gérées
  « au niveau de l'organisation » MCPJam et exigent une connexion :
  `client/src/hooks/use-byok-allowed.ts` (`return !!user;`), `use-ai-provider-keys.ts`
  (« BYOK is sign-in only: guests see empty tokens and no-op setters », et l'entrée `localStorage`
  `mcp-inspector-provider-tokens` est **effacée** pour un invité), `SettingsTab.tsx`
  (« Sign in to configure model providers »). Initialiser le `localStorage` est donc inopérant.
- La connexion est impossible sur `http://localhost:7000` : le client WorkOS de MCPJam
  (`client_01K4C1TVPBE7JTBFQJF9SDW9P9`) n'accepte que `http://localhost:6274/callback`.
  Preuve :
  ```bash
  curl -s -o /dev/null -w "%{redirect_url}\n" "https://api.workos.com/user_management/authorize?client_id=client_01K4C1TVPBE7JTBFQJF9SDW9P9&redirect_uri=http%3A%2F%2Flocalhost%3A7000%2Fcallback&response_type=code&provider=authkit"
  # → https://login.mcpjam.com/redirect-uri-invalid?...   (6274 → auth.mcpjam.com/..., accepté)
  ```
- En invité, le sélecteur de modèles propose deux onglets : « Free models » (modèles hébergés et
  payés par MCPJam, via `rt.mcpjam.com`) et « Your providers » (« No provider keys yet »). Parmi
  les gratuits, les modèles « standard » (ex. Claude Haiku 4.5, sélection par défaut) marchent sans
  compte ; les modèles « frontier » — dont **Gemini 3.6 Flash** — répondent « Sign in to use
  frontier models, or choose a standard model ».
- Procédure de saisie de la clé, **si** l'arbitrage retient l'option A ci-dessous (à vérifier par
  le formateur, non testée faute de clé et de compte) : ouvrir `http://localhost:6274`, « Sign in »
  (compte MCPJam), créer ou choisir une organisation, Settings → LLM Providers → OpenRouter, coller
  la clé et cocher `google/gemini-3.6-flash` ; puis, dans le terrain de jeu, sélecteur de modèle →
  « Your providers » → `google/gemini-3.6-flash`. La clé est alors stockée par MCPJam, dans son
  nuage, au niveau de l'organisation.

### 4. Prompt système du terrain de jeu

- Dans le terrain de jeu (Playground), bouton « Options » (le `+` à gauche de la zone de saisie) →
  « System Prompt & Temperature » → saisir le texte → « Save » → « Confirm & Reset » (changer le
  prompt efface la conversation en cours). Source : `client/src/components/chat-v2/chat-input.tsx`
  et `chat-input/system-prompt-selector.tsx`. Aucune option en ligne de commande.
- Vérifié : avec « Tu es l'assistant documentaire du port. Nous sommes le mardi 6 octobre 2026
  (fuseau Europe/Paris). Réponds en français. », la question « Quelle est la date du jour ? »
  obtient « La date du jour est le mardi 6 octobre 2026 (fuseau horaire Europe/Paris). »
- La barre du terrain de jeu affiche aussi un contexte d'hôte `en-US` / `Los Angeles` (contexte
  transmis aux applications MCP) : sans effet observé sur la date, à laisser tel quel.

### 5. Hôtes autorisés

- Variable : `MCPJAM_ALLOWED_HOSTS` (liste séparée par des virgules). Elle ouvre deux contrôles :
  le jeton de session (`server/utils/localhost-check.ts`, `isAllowedHost`, où `localhost` est
  toujours accepté) et la validation de l'en-tête `Origin` (`server/middleware/origin-validation.ts`).
  Sans elle, seules les origines `http://localhost:6274`, `:5173` et `:8080` passent : une page
  servie sur le port publié 7000 est refusée.
- Preuve : même image, même requête `GET /api/mcp-cli-config` avec `Origin: http://localhost:<port publié>` :
  **403** « Request origin not allowed » sans la variable, **401** (contrôle d'origine passé,
  jeton exigé) avec `MCPJAM_ALLOWED_HOSTS=localhost,127.0.0.1`.
  (Autre voie : `ALLOWED_ORIGINS=http://localhost:7000,http://127.0.0.1:7000`.)

## Vérification à la main (étape 4)

Commandes : `docker compose -f compose.yaml build mcpjam`, `make up && make lab0-up`,
`cp labs/lab0/client.config.json config/mcpjam/ && make client-redemarrer`, navigateur sans
interface (Playwright) sur `http://localhost:7000`.

- **(a) OK en invité, avec ajout manuel.** Le fichier de configuration est chargé par le serveur
  mais pas appliqué (compte requis, question 2). Dans la boîte « Connect to your MCP server »,
  saisir `http://observateur:8100/mcp` → « Connect » → « Connected to Observateur:8100 — 3 tools
  ready to use » ; onglet Tools : `lister_documents`, `lire_document`, `rechercher_clause`.
  Dans l'observateur : `server/discover` (protocole `2026-07-28`), `tools/list`, `prompts/list`.
  Le serveur reste enregistré après rechargement de la page (même navigateur).
- **(b) Partiel.** Clé OpenRouter + `google/gemini-3.6-flash` : impossible sur le port 7000
  (question 3). Question de référence posée avec le modèle gratuit standard **Claude Haiku 4.5**
  (hébergé par MCPJam, sans clé) : réponse complète en français, citant la pénalité de 1 850 € par
  heure au-delà de 6 heures de franchise.
- **(c) OK.** Dans `http://localhost:7001`, deux `tools/call` pour cette question :
  `lister_documents {"escale_id": "ESC-2026-0412"}` puis
  `lire_document {"document_id": "CM-0412", "page_debut": 1, "page_fin": 20}`.

## Conséquences — options pour l'arbitrage

- **A. Garder MCPJam avec OpenRouter** : publier sur `6274:6274` au lieu de `7000:6274` (modifier
  la contrainte « port 7000 »). Chaque participant crée un compte MCPJam et une organisation, et
  saisit la clé OpenRouter dans le nuage MCPJam. Le fichier `client.config.json` est alors appliqué
  à la connexion. Coût : comptes tiers pour les participants, clé stockée chez MCPJam, dépendance
  au service en ligne. À vérifier par le formateur (non testé).
- **B. Garder MCPJam en invité sur 7000** (état livré par cette tâche) : aucun compte, aucune clé ;
  ajout manuel de l'URL `http://observateur:8100/mcp` ; modèles gratuits standard de MCPJam
  (Claude Haiku 4.5 testé), pas `google/gemini-3.6-flash` ; les requêtes passent par le nuage
  MCPJam (quota gratuit, non maîtrisé). `config/mcpjam/client.config.json` doit rester
  `{"mcpServers": {}}`, sinon la page redirige vers une connexion en échec — le message de
  `make lab0-up` (« cp labs/lab0/client.config.json … ») est à revoir dans ce cas.
- **C. Repli de la spec** : VS Code + clé OpenRouter.

## Procédure pour le formateur (à vérifier par le formateur)

1. `make up && make lab0-up`, puis ouvrir `http://localhost:7000` (`make client`).
2. Option B : dans « Connect to your MCP server », coller `http://observateur:8100/mcp` →
   « Connect » → « Open Playground ». Option A : ouvrir `http://localhost:6274` après changement
   du port publié, « Sign in », puis configurer OpenRouter (question 3) ; le serveur
   `pharos-docs-demo` apparaît alors depuis `client.config.json`.
3. Choisir le modèle : sélecteur à droite de « MCPJam » sous la zone de saisie ; option A :
   « Your providers » → `google/gemini-3.6-flash` ; option B : « Free models » → Claude Haiku 4.5.
4. « Options » (`+`) → « System Prompt & Temperature » : « Tu es l'assistant documentaire du
   port. Nous sommes le mardi 6 octobre 2026 (fuseau Europe/Paris). Réponds en français. » →
   « Save » → « Confirm & Reset ».
5. Poser la question de référence, puis vérifier au moins un `tools/call` dans
   `http://localhost:7001` (mot de passe `pharos`).
