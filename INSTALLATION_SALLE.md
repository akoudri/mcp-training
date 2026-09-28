# Guide d'installation de la salle — formation « Créer des agents IA avec MCP »

Runbook du **formateur**, dans l'ordre d'exécution : de l'arrivée en salle jusqu'à
« tous les postes au vert, service de salle prêt ». Chaque poste suit en plus la
checklist courte `PREPARATION.md` ; ce guide-ci relie les morceaux et donne le pourquoi.

> Deux documents complémentaires, à garder ouverts : `PREPARATION.md` (une case par
> poste) et `PORTS.md` (qui écoute où). Ce guide ne les recopie pas, il les orchestre.

---

## 0. Vue d'ensemble — ce qu'on installe

| Élément | Où | Rôle |
|---|---|---|
| **Poste binôme** (×5 par défaut) | chaque PC | Docker + le kit `pharos-labs` + VS Code |
| **Image `pharos/python:2`** | chaque poste | construite localement (`make construire`), jamais tirée d'un registre |
| **Observateur** (mitmproxy) | chaque poste, `127.0.0.1:7001` | voit tout le trafic MCP ; unique porte vers les serveurs |
| **Modèle** | nuage | `google/gemini-3.6-flash` via la passerelle OpenRouter, **une clé plafonnée par binôme** |
| **Client graphique** | chaque poste | VS Code + chat intégré, mode **PHAROS**, clé OpenRouter en « bring your own key » |
| **Service de salle** (`pharos-salle`) | **poste du formateur uniquement**, `:8300` | seulement au module sécurité (LAB 14) ; seul service ouvert sur le réseau de salle |

**Principe réseau.** Sur un poste, **tout est publié sur `127.0.0.1` seulement** : un
voisin de salle ne peut ni lire le trafic, ni joindre les serveurs. La **seule** exception
est le service de salle du LAB 14, ouvert sur `0.0.0.0:8300` sur le poste du formateur —
et c'est le sujet du lab. Le réseau de la salle n'a donc qu'un besoin : que chaque poste
puisse atteindre `poste-formateur:8300` le jour du LAB 14. Rien d'autre ne traverse.

**Ce qui sort vers Internet** : uniquement les appels au modèle (`openrouter.ai`). S'il y
a un proxy d'entreprise, c'est le seul domaine à débloquer côté runtime (plus
`download.docker.com`, `astral.sh`, `github.com`, `pypi.org`, `docker.io` à
l'installation).

**Carte des phases**

```
A. Veille, formateur          → clés OpenRouter plafonnées + fichiers .env par binôme
B. Chaque poste               → preparer-pc (Docker, uv, clone, image), .env du binôme
C. Chaque poste               → client VS Code (clé, modèle, mode PHAROS)
D. Chaque poste               → make up / lab0-up / doctor = trois lignes OK
E. Jour du LAB 14, formateur  → service de salle + jetons papier + inscription binômes
F. Fin de session, formateur  → révocation des clés
```

Avant d'ouvrir la salle : **faire un poste témoin de bout en bout** (§ Rodage), parce que
quelques points du client n'ont été validés que par lecture de code, pas encore par une
exécution réelle en salle.

---

## Phase A — Avant la session (formateur, la veille)

Se fait **une fois**, depuis un clone du dépôt sur le poste du formateur.

### A.1 Créer une clé OpenRouter plafonnée par binôme

`OPENROUTER_CLE_GESTION` est votre clé de **gestion** du compte OpenRouter (celle qui a le
droit de créer des sous-clés) — jamais distribuée, jamais commitée.

```bash
cd ~/pharos-labs
OPENROUTER_CLE_GESTION=sk-or-… \
  uv run python -m outils.cles_openrouter creer \
    --binomes 5 --plafond 5 --expiration 2026-10-10
```

- `--binomes 5` : une clé `pharos-binome-1` … `pharos-binome-5`.
- `--plafond 5` : plafond **en dollars** par binôme (coupe automatiquement au dépassement).
- `--expiration` : date de fin de session ; la clé meurt seule après.
- Écrit un fichier par binôme dans `sortie/` : `binome-1.env` … `binome-5.env`
  (permissions `600`), contenant `OPENROUTER_API_KEY`, `PHAROS_MODELE=google/gemini-3.6-flash`,
  `PHAROS_BINOME=n`.

Suivre la consommation à tout moment :

```bash
OPENROUTER_CLE_GESTION=sk-or-… uv run python -m outils.cles_openrouter etat
```

### A.2 Distribuer les fichiers `.env`

Remettre à chaque binôme **son** `sortie/binome-N.env` par **clé USB** — jamais par un
canal partagé (mail, dossier réseau, dépôt). Une clé = un binôme = un plafond.

---

## Phase B — Préparer chaque poste

Objectif : Docker fonctionnel sans `sudo`, le dépôt cloné, l'image `pharos/python:2`
construite, l'observateur préchargé. À faire **au plus tard la veille**.

### B.1 Windows → WSL2 (PowerShell administrateur)

1. Virtualisation activée dans le BIOS/UEFI (Intel VT-x / AMD-V).
2. Lancer `outils/preparer-pc.ps1` **en administrateur**. Il installe WSL2, Ubuntu 24.04,
   VS Code et l'extension Remote-WSL. Redémarrer si Windows le demande.
3. Ouvrir « Ubuntu 24.04 », créer l'utilisateur, puis **continuer en B.2 dans Ubuntu**.

### B.2 Linux, ou Ubuntu sous WSL

```bash
# dépôt privé : clé SSH de déploiement configurée, sinon copier le script depuis la clé USB
curl -fsSL https://raw.githubusercontent.com/akoudri/pharos-labs/main/outils/preparer-pc.sh | bash
```

Le script installe Docker Engine + plugin Compose, `uv`, VS Code (hors WSL), clone le
dépôt dans `~/pharos-labs`, crée `.env` depuis `.env.example`, **construit l'image**
(`make construire`, plusieurs minutes) et précharge l'image de l'observateur.

3. **Rouvrir la session** pour que le groupe `docker` prenne effet, puis vérifier :
   `docker run --rm hello-world` doit fonctionner **sans `sudo`**.
4. Copier le `.env` du binôme par-dessus celui créé par le script :
   `cp /media/usb/binome-N.env ~/pharos-labs/.env`.
5. Créer la branche du binôme (les commits des labs restent locaux jusqu'au LAB 15) :
   `cd ~/pharos-labs && git switch -c binome-N`.

---

## Phase C — Client graphique (VS Code), par binôme, ~5 min

Le client est **VS Code + son chat intégré**, avec le modèle OpenRouter en clé apportée
(MCPJam a été écarté — voir `docs/decisions/client-graphique.md`).

1. **Ouvrir le dépôt.** Linux : `make client` (ou `code ~/pharos-labs`). Windows :
   Remote-WSL → *Open Folder in WSL…* → `~/pharos-labs`. **Ne jamais** ouvrir via `\\wsl$`.
2. **Faire confiance au dossier** : « Yes, I trust the authors » (sinon les serveurs MCP
   restent bloqués et le sélecteur de modèle n'affiche que « Auto »).
3. **Saisir la clé** : chat (`Ctrl+Alt+I`) → sélecteur de modèle → **Manage Language
   Models** → **Add Models** → **OpenRouter** → coller la clé du binôme.
4. **Choisir le modèle** `google/gemini-3.6-flash`.
5. **Copier la config MCP** (la commande exacte est aussi affichée par `make lab0-up`) :
   `mkdir -p .vscode && cp labs/lab0/client.config.json .vscode/mcp.json`.
6. **Démarrer le serveur** : palette → **MCP: List Servers** → `pharos-docs-demo` → *Start*.
7. **Vérifier les 3 outils** dans la zone de chat : `lister_documents`, `lire_document`,
   `rechercher_clause`.
8. **Sélectionner le mode PHAROS** dans le sélecteur de mode (pas *Agent*, pas *Ask*). Ce
   mode (`.github/agents/pharos.agent.md`) ne donne au modèle **que** les outils MCP —
   sans lui, le mode *Agent* peut lire la réponse directement dans `donnees/corpus/` sans
   aucun appel MCP, ce qui fausse tout le LAB 0.

> VS Code demande une confirmation avant chaque appel d'outil non `readOnlyHint` : c'est
> **voulu** pour le LAB 0 (les arguments sont visibles et modifiables avant envoi).

---

## Phase D — Vérification finale, par poste

Un poste n'est **prêt** que si ces trois checks passent.

```bash
cd ~/pharos-labs && make up && make lab0-up && make doctor
```

`make doctor` doit afficher **trois lignes OK** :

| Ligne | Ce qu'elle prouve |
|---|---|
| `socle   OK` | l'observateur est joignable (le réseau Compose tourne) |
| `modèle  OK` | la clé OpenRouter du binôme marche **et** `gemini-3.6-flash` sait appeler un outil |
| `serveur OK` | `pharos-docs-demo` expose ses 3 outils **à travers l'observateur** |

Puis, à l'écran :

- **http://localhost:7001** (observateur ; mot de passe `pharos`) s'ouvre dans le navigateur.
- Dans VS Code, le serveur `pharos-docs-demo` est démarré et montre 3 outils (fin de Phase C).

> Chaque `make doctor` fait un vrai (minuscule) appel au modèle : il consomme quelques
> fractions de centime sur le plafond du binôme, et valide la clé du même coup.

---

## Phase E — Service de salle (jour du LAB 14 seulement)

Le service `pharos-salle` tourne **sur le poste du formateur** et n'est démarré que pour
le module sécurité. C'est le **seul** service publié sur le réseau de la salle.

### E.1 Démarrer le service et tirer les jetons

```bash
cd ~/pharos-labs
make salle-demarrer N=5
```

- Publie le service sur `0.0.0.0:8300` et affiche son URL réseau
  (`http://<ip-du-poste-formateur>:8300` — noter cette IP au tableau).
- `N=5` tire un jeton par binôme (+ un **jeton formateur**) dans `salle/jetons.txt`.
  Les régénérer seuls : `make salle-jetons N=5`.
- **Distribuer les jetons sur papier**, un par binôme. Ne pas les afficher ni les envoyer.
- Tableau de bord de salle : `http://<ip-formateur>:8300/tableau` (ou `make lab14-tableau`).

Pour préparer/tester sans ouvrir le réseau : `make salle-locale` (reste sur `127.0.0.1:8300`).

### E.2 Côté binôme (rappel, ils le font depuis leur brief)

```bash
make lab14-inscrire URL=http://<ip-formateur>:8300 BINOME=3 JETON=<jeton papier>
```

### E.3 Faire tourner les manches de l'attaque

```bash
make salle-manche M=1   # anneau : chaque binôme b attaque b+1
make salle-manche M=2   # dépôt fermé
make salle-manche M=3   # anneau : b attaque b+2
```

---

## Phase F — Fin de session (formateur)

Révoquer **toutes** les clés du compte préfixées `pharos-binome-` :

```bash
OPENROUTER_CLE_GESTION=sk-or-… uv run python -m outils.cles_openrouter revoquer
```

Puis, sur les postes qui ne resservent pas : `make down` (arrête tout).

---

## Rodage — un poste témoin, avant d'ouvrir la salle

Quelques points du client n'ont été établis **que par lecture de code / doc** lors du
spike (`docs/decisions/client-graphique.md`, § « À vérifier par le formateur »), pas encore
par une exécution réelle de bout en bout. À smoke-tester sur **un** poste, la veille :

1. Sur un profil VS Code neuf, **déconnecté de GitHub/Copilot**, le chat mène bien à
   *Manage Language Models* sans mur d'inscription.
2. Le modèle BYOK `google/gemini-3.6-flash` se présélectionne et **appelle réellement** un
   outil, **à travers l'observateur** (mitmproxy), sur les 3 outils du LAB 0.
3. Sous Remote-WSL, le chat s'exécute bien **depuis WSL** (`~/.vscode-server`), pas depuis
   Windows.
4. Le mode PHAROS ne propose **que** les outils de `pharos-docs-demo` ; en mode *Ask*,
   aucun appel MCP.

Si l'un de ces points coince, il vaut mieux le découvrir sur le poste témoin que sur cinq
postes à 9 h.

---

## Dépannage

| Symptôme | Cause la plus fréquente | Geste |
|---|---|---|
| `make doctor` : `socle ÉCHEC` | Docker arrêté ou image non construite | `sudo service docker start` ; `make construire` |
| `make doctor` : `modèle ÉCHEC` (clé absente) | `.env` pas copié / mal copié | recopier `binome-N.env` dans `~/pharos-labs/.env` |
| `make doctor` : `modèle ÉCHEC` (injoignable) | proxy bloque `openrouter.ai` | débloquer le domaine côté proxy |
| `make doctor` : `modèle ÉCHEC` (tronqué / pas d'appel) | modèle ou quota | vérifier le plafond (`… cles_openrouter etat`) ; prévenir le formateur |
| `make doctor` : `serveur ÉCHEC` | `make lab0-up` oublié | `make lab0-up` ; sinon `make logs S=pharos-docs-demo` |
| `docker` demande `sudo` | session pas rouverte après `usermod -aG docker` | fermer/rouvrir la session (WSL : `wsl --shutdown` puis rouvrir Ubuntu) |
| **502** sur un port `81xx/82xx` | le serveur de ce lab n'est pas encore démarré (réservé) | normal tant que le lab n'est pas lancé ; sur `8100`, c'est `make lab0-up` oublié |
| VS Code : aucun outil | dossier non approuvé, `.vscode/mcp.json` absent, ou `lab0-up` oublié | refaire les étapes 2, 5, 6 de la Phase C |
| VS Code lit la réponse sans appel MCP | mode *Agent* au lieu de **PHAROS** | changer de mode (étape 8) |
| LAB 14 : binôme ne joint pas `:8300` | service en `salle-locale`, ou réseau/IP | `make salle-demarrer` (pas `-locale`) ; vérifier l'IP et que le poste atteint `poste-formateur:8300` |

Prévenir le formateur avant le premier jour pour tout poste encore en échec.

---

## Annexe — repères de salle

**Ports** (détail complet : `PORTS.md`) — tout sur `127.0.0.1` sauf `pharos-salle:8300`.

| Port | Service |
|---|---|
| 7001 | Observateur du trafic MCP (mot de passe `pharos`) |
| 7002 | Inspector officiel (`make inspector-client`, appels manuels) |
| 8100 | `pharos-docs-demo` (LAB 0) — VS Code s'y connecte |
| 8101–8105, 8201, 8203, 8204 | serveurs et répartiteurs des labs suivants (502 tant qu'inactifs) |
| 8300 | `pharos-salle` (LAB 14, poste formateur) — seul port ouvert sur le réseau de salle |
| 5433 | `pharos-db` (PostgreSQL 17 ; user `postgres`, mdp de salle `pharos-salle-2026`) |

**Comptes / secrets de salle** (valeurs par défaut du kit, non secrètes) : mot de passe
observateur `pharos` ; mdp PostgreSQL de salle `pharos-salle-2026`. Les **jetons** du
service de salle (`salle/jetons.txt`) et les **clés OpenRouter** sont, eux, à protéger et à
distribuer en main propre.

**Commandes de référence**

```bash
make up                 # socle : observateur (+ client)
make lab0-up            # pharos-docs-demo (LAB 0)
make doctor             # trois lignes OK attendues
make doctor SANS_MODELE=1   # sans l'appel au modèle (préparation hors ligne)
make down               # arrête tout
make logs S=<service>   # journaux d'un service
make construire         # (re)construit l'image pharos/python:2
make inspector          # ouvre l'observateur (7001)
```

**Prérequis par poste** : Docker Engine + plugin Compose, `uv`, Python 3.12 (fourni par
l'image du kit), VS Code. Accès Internet vers `openrouter.ai` au runtime.
