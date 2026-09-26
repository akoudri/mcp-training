# Préparation des postes — liste de vérification du centre

À faire sur chaque PC, au plus tard la veille. Un poste n'est prêt que si la dernière case est cochée.

## Windows uniquement
- [ ] Virtualisation activée dans le BIOS/UEFI.
- [ ] `outils/preparer-pc.ps1` exécuté dans PowerShell **en administrateur** ; PC redémarré si demandé.
- [ ] VS Code et l'extension Remote-WSL installés (fait par le script).
- [ ] « Ubuntu 24.04 » ouvert, utilisateur créé.

## Linux, ou Ubuntu sous WSL
- [ ] `outils/preparer-pc.sh` exécuté sans erreur (construit l'image via `make construire`, précharge l'image de l'observateur ; accès au dépôt privé : clé SSH de déploiement ou copie depuis la clé USB).
- [ ] Session rouverte (groupe `docker` pris en compte) : `docker run --rm hello-world` fonctionne sans `sudo`.
- [ ] `.env` du binôme copié dans `~/pharos-labs/.env` (fichiers `sortie/binome-N.env` remis par le formateur).

## Client graphique (par binôme, 5 minutes)
- [ ] Ouvrir le dépôt dans VS Code : Linux → `make client` ; Windows → Remote-WSL > *Open Folder in WSL* > `~/pharos-labs`.
- [ ] Faire confiance au dossier (« Yes, I trust the authors »).
- [ ] Saisir la clé OpenRouter du binôme : Chat → sélecteur de modèle → **Manage Language Models** → **Add Models** → **OpenRouter** → coller la clé.
- [ ] Choisir le modèle `google/gemini-3.6-flash` dans le sélecteur de modèle du chat.

Détail complet de la procédure : `docs/decisions/client-graphique.md`.

## Vérification finale
- [ ] `cd ~/pharos-labs && make up && make lab0-up && make doctor` affiche **trois lignes OK**.
- [ ] http://localhost:7001 (Inspector — observateur de trafic, mot de passe `pharos`) s'ouvre dans le navigateur du poste.
- [ ] Dans VS Code, après `mkdir -p .vscode && cp labs/lab0/client.config.json .vscode/mcp.json`, le serveur `pharos-docs-demo` démarre (palette > « MCP: List Servers » > *Start*) et expose 3 outils.

## En cas d'échec
| Ligne `make doctor` | Cause la plus fréquente |
|---|---|
| `socle ÉCHEC` | Docker arrêté (`sudo service docker start`) ; images non construites (`make construire`) |
| `modèle ÉCHEC` | `.env` absent ou clé mal copiée ; proxy d'entreprise bloquant `openrouter.ai` |
| `serveur ÉCHEC` | `make lab0-up` oublié ; `make logs S=pharos-docs-demo` |
| Client VS Code : aucun outil | Dossier non approuvé (trust) ; `.vscode/mcp.json` absent ; `make lab0-up` oublié |

Prévenir le formateur avant le premier jour pour tout poste qui reste en échec.

## Fin de session (formateur)
- `OPENROUTER_CLE_GESTION=… python -m outils.cles_openrouter revoquer`
