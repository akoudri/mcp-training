# Décision — client graphique : VS Code + OpenRouter à la place de MCPJam

Date de la décision : 26 septembre 2026 (rework de la tâche 9, tranché par le formateur).

## Pourquoi MCPJam Inspector est écarté

MCPJam Inspector 3.12.0 avait été packagé et vérifié à la tâche 9 (commit `5a050d3`,
détails dans `docs/decisions/mcpjam.md` de l'historique git). Le mode invité fonctionne
(serveur `pharos-docs-demo` ajoutable à la main, trois outils visibles, appels d'outils
observables dans `http://localhost:7001`), mais avec deux limites bloquantes pour le
LAB 0 :

- La clé OpenRouter ne peut être configurée que via un compte MCPJam (WorkOS) et une
  organisation dans leur nuage (Convex) ; en invité, aucune clé ne peut être saisie, et
  les modèles « frontier » (dont `google/gemini-3.6-flash`) sont réservés aux comptes
  connectés — seuls des modèles gratuits imposés par MCPJam (ex. Claude Haiku 4.5) sont
  utilisables, et les conversations transitent par les serveurs de MCPJam
  (`rt.mcpjam.com`).
- La connexion à un compte MCPJam est elle-même cassée sur le port publié du kit
  (`7000`) : leur client WorkOS n'accepte que la redirection `http://localhost:6274/callback`,
  et redirige donc vers une page d'erreur sur `7000`.
- Le fichier de configuration des serveurs (`--config`, lu au démarrage) ne s'applique
  dans le navigateur qu'à un utilisateur connecté ; en invité, un fichier non vide
  provoque la même redirection de connexion cassée.

Le formateur a tranché : MCPJam est abandonné pour le kit. Le client graphique devient
**VS Code (desktop)**, avec le chat intégré (Copilot Chat, extension livrée avec
VS Code, sans compte GitHub requis) et un modèle OpenRouter en « bring your own key ».
Voir `vscode-spike.md` (dossier de spécification) pour le détail des vérifications.

## Procédure participant (VS Code)

1. **Ouvrir le dépôt.**
   - Linux : `code ~/pharos-labs`.
   - Windows : installer l'extension Remote-WSL si besoin, puis VS Code → Remote-WSL →
     *Open Folder in WSL...* et choisir le dépôt cloné côté WSL. Ne jamais ouvrir le
     dépôt via `\\wsl$` depuis l'explorateur Windows.
2. **Faire confiance au dossier** : à l'ouverture, cliquer « Yes, I trust the authors »
   (sans quoi les serveurs MCP restent bloqués et le sélecteur de modèle n'affiche que
   « Auto »).
3. **Saisir la clé OpenRouter** : ouvrir le chat (Ctrl+Alt+I) → sélecteur de modèle →
   **Manage Language Models** (ou palette de commandes → *Chat: Manage Language
   Models*) → **Add Models** → **OpenRouter** → coller la clé API.
4. **Choisir le modèle** `google/gemini-3.6-flash` dans le sélecteur de modèle du chat.
5. **Copier la configuration MCP** : la commande exacte est affichée par
   `make lab0-up` (`mkdir -p .vscode && cp labs/lab0/client.config.json .vscode/mcp.json`).
6. **Démarrer le serveur MCP** : palette de commandes → **MCP: List Servers** →
   `pharos-docs-demo` → *Start* (ou *Restart* si déjà démarré).
7. **Vérifier les 3 outils** : dans la zone de saisie du chat, ouvrir l'icône outils et
   confirmer la présence de `lister_documents`, `lire_document`, `rechercher_clause`.
8. **Poser la question de référence en mode Agent** : sélectionner le mode *Agent* dans
   le chat, puis poser la question sur l'escale `ESC-2026-0412` (*Vent d'Autan*, jeudi
   8 octobre 2026, pénalité 1 850 €/heure au-delà de 6 heures de franchise) et vérifier
   les appels d'outils affichés (« Ran `<outil>` »).

## À vérifier par le formateur

Ces points ont été établis par lecture de code / documentation lors du spike
(`vscode-spike.md`), pas par un test d'exécution réel de bout en bout :

1. Le fichier « Custom Endpoint » (`chatLanguageModels.json`, option B du spike, clé en
   texte clair pré-provisionnée) démarre bien un aller-retour d'appel d'outil complet
   contre OpenRouter — non testé en exécution.
2. `"chat.defaultModel": "google/gemini-3.6-flash"` présélectionne bien le modèle BYOK
   sur un profil neuf, déconnecté de GitHub.
3. L'écran de chat, déconnecté (pas de compte GitHub / Copilot), mène bien directement à
   **Manage Language Models** sans mur d'inscription bloquant.
4. Sous Remote-WSL, l'extension Copilot Chat intégrée est bien présente côté serveur
   VS Code (`~/.vscode-server`) et exécute bien le chat depuis WSL (et non depuis
   Windows).
5. La fiabilité de Gemini 3.6 Flash pour l'appel d'outils (y compris à travers
   mitmproxy/l'observateur) sur les trois outils du LAB 0.

**Note pédagogique** : VS Code ouvre une boîte de confirmation avant chaque appel
d'outil qui n'a pas `readOnlyHint` : c'est voulu pour le LAB 0 (les arguments de
l'appel sont visibles et modifiables avant confirmation).
