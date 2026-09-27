# Recette — assemblage, sécurité, évaluation (LAB 13 à 15)

Complète `2026-donnees-externes.md`. Sous-projet 4, plans 1 à 3.
✅ = vérifié par la CI (job `solutions`) ; 👁 = à constater par le formateur.

## L'agent complet en salle (LAB 13)

- `make lab13-tout` démarre la base, les mocks et les trois serveurs derrière l'observateur (8101, 8102, 8103).
  La base n'est pas rechargée : `make lab8-base` d'abord si elle est vide (le départ du lab le fait).
- La boucle lit `labs/lab13/serveurs.json` : trois serveurs, le jeton `jeton-exploitation` pour pharos-data et
  pharos-ops. `PHAROS_JETON`, s'il est posé, prime sur la configuration (le LAB 14 change ainsi d'identité).
- La collision de départ : le module navires (`serveurs/pharos_data/navires.py`, fourni) s'enregistre par défaut
  sous `navire_par_nom`, que pharos-ops expose déjà. Elle n'apparaît qu'au catalogue agrégé
  (`make lab13-catalogue`) ; la boucle de référence refuse un catalogue ambigu (`CollisionDeNoms`). Correction
  attendue : `navires.enregistrer(mcp, emprunter, nom_outil="data_navire_par_nom")`. L'extension B mesure la
  collision avant de la corriger (`make lab13-banc` : un client naïf, où le dernier serveur écrase l'autre).
- `make lab13-question` pose la question avec le vrai modèle et garde l'exécution dans `labs/lab13/execution.json`
  (question, plan, réponse, trace — secrets masqués) : c'est ce fichier, commité, que relisent
  `make lab13-verifier-note`, `make lab13-derive` et le critère décisif du vérificateur.
- Le vérificateur de note accepte un nombre obtenu par une seule opération sur deux nombres d'un **même** appel
  (la marge 13,5 − 12,9) ; il refuse une combinaison entre deux appels (une coïncidence probable) et ne vérifie
  pas les noms hors de la liste du kit (navires, armateurs, agents).

## La vue du plan de quai (LAB 13, étape 4) 👁

1. `make lab13-tout`, puis `mkdir -p .vscode && cp labs/lab13/client.config.json .vscode/mcp.json`.
2. VS Code (`make client`), chat en mode agent **PHAROS** (`.github/agents/pharos.agent.md` : les outils des
   quatre serveurs PHAROS, rien d'autre) ; réglage `chat.mcp.apps.enabled` actif (valeur par défaut).
3. Demander : « Recalcule le plan de placement à quai de jeudi 8 octobre pour le quai 3. »
4. Attendu : la réponse texte, et sous elle le diagramme des sept quais — le *Vent d'Autan* en rouge (à décaler :
   coup de vent de 34 kt), hachures sur le quai 3.

La vue reçoit le résultat de l'outil par `postMessage` (JSON-RPC, spécification MCP Apps 2026-01-26 :
`ui/initialize`, puis `ui/notifications/tool-result`). Si elle ne s'affiche pas, le socle reste atteignable par la
réponse texte (brief, étape 4) ; noter la version de VS Code dans cette recette.

## Étalonnage du LAB 13 (2026-09-27)

Modèle : `google/gemini-3.6-flash`, par les cibles `make` à la racine du dépôt (`lab13-catalogue`, `lab13-banc`,
`lab13-question`, `lab13-verifier-note`, `lab13-derive`). Trois serveurs démarrés (`make lab13-tout`), base et
mocks chargés (`make lab8-base`, `make lab10-mocks`). `make lab13-verifier SANS_MODELE=1` : 10 ✅, 2 👁 avant
étalonnage (exécution provisoire de la solution).

**Coût fixe du catalogue** (`make lab13-catalogue`, o200k_base, approximation) :

| Serveur | Outils | Tokens |
|---|---|---|
| pharos-docs | 4 | 510 |
| pharos-data | 5 | 662 |
| pharos-ops | 5 | 852 |
| **agrégé** | **14** | **2024** |

Aucune collision de noms sur le catalogue agrégé une fois la correction en place (rappel LAB 10 : un seul
serveur, pharos-ops, 476 tokens pour 3 outils).

**La collision, mesurée avant correction** (extension B — `sed` réintroduit
`navires.enregistrer(mcp, emprunter)` sans `nom_outil`, catalogue relevé, banc relevé, puis correction restaurée
par superposition de l'état LAB 13) :

- Catalogue avec collision : `❌ navire_par_nom — pharos-data, pharos-ops` (14 outils, ~2023 tokens agrégés).
- Banc avant correction (`make lab13-banc`, 3 exécutions × 5 questions) : 5/5 questions réussies (majorité des
  exécutions) — Q1 (`navire_par_nom`) 3/3, Q2 (`navire_par_nom`) 3/3, Q3 (`rechercher_clause`) 3/3, Q4
  (`escales_a_risque`) 3/3, Q5 (`meteo_creneau`) 3/3. Tokens : 22140 en entrée, 2863 en sortie · coût : 0,0273 $.
- Banc après correction : catalogue sans collision (14 outils, 2024 tokens agrégés) ; mêmes taux — 5/5 questions,
  3/3 sur chacune des cinq, y compris Q1 et Q2. Tokens : 23295 en entrée, 3544 en sortie · coût : 0,0308 $.
- Sur ce modèle et ce banc, la collision n'a pas dégradé le taux de réussite de Q1/Q2 : `google/gemini-3.6-flash`
  a résolu `navire_par_nom` de façon stable dans les deux configurations. La correction reste nécessaire (le
  catalogue ambigu est refusé par la boucle de référence, indépendamment du taux du banc) ; l'absence de
  dégradation observée est un résultat de calibration, pas un motif pour l'omettre.

**La question cible, trois exécutions** (`make lab13-question Q=1` avec `ok`/`oui` sur l'entrée standard, puis
`make lab13-verifier-note` et `make lab13-derive`) — question : « L'escale du Vent d'Autan de jeudi est-elle à
risque ? Si oui, prépare la note d'alerte pour l'exploitant. » Dans les trois exécutions, le modèle s'arrête après
avoir proposé le texte de la note et demandé la confirmation en prose, sans appeler `publier_alerte` : le second
jeton (`oui`) posé sur l'entrée standard reste inutilisé, et la confirmation du LAB 12 avant publication n'est
donc atteinte dans aucune des trois.

| # | Plan annoncé | Appels (trace) | Superflus | Données sans origine | Signaux (hors plan / jamais exécutées / retours) | Confirmation avant `publier_alerte` |
|---|---|---|---|---|---|---|
| 1 | 3 étapes : `lister_escales`, `details_escale`, `consulter_meteo` (serveurs non nommés) | `navire_par_nom` (pharos-ops), `escales_a_risque` (pharos-data), `meteo_creneau` (pharos-ops) — 3 appels | 0 | 0 (27 éléments vérifiés) | 3 / 3 / 0 | non atteinte (pas de publication) |
| 2 | 2 étapes : `rechercher_escales`, `obtenir_meteo` | `navire_par_nom`, `escales_a_risque`, `conflits_de_creneau`, `meteo_creneau` — 4 appels | 1 — `conflits_de_creneau` (pharos-data) : mêmes données que `escales_a_risque` (conflit `ESC-2026-0412`/`ESC-2026-0413`, 60 min), aucune valeur de la note n'y est rattachée | 0 (26 éléments vérifiés) | 4 / 2 / 0 | non atteinte (pas de publication) |
| **3 (retenue)** | 3 étapes : `obtenir_escales`, `obtenir_meteo`, `obtenir_alertes` | `navire_par_nom`, `escales_a_risque`, `meteo_creneau`, `meteo_alerte` — 4 appels | 0 — `meteo_alerte` fournit les seuils (25 kt, 35 kt) repris dans la réponse, et confirme le risque | 0 (28 éléments vérifiés) | 4 / 3 / 0 | non atteinte (pas de publication) |

Exécution retenue : **la 3**, dernière des trois dont la note n'a aucune donnée sans origine et au plus un appel
superflu (les trois exécutions satisfont en fait ce double critère ; la règle du brief retient la dernière).
Recopiée dans `solutions/lab13/labs/lab13/execution.json` ; les trois traces complètes sont gardées hors dépôt
sous `sortie/etalonnage-lab13/` (question-1..3.txt, execution-1..3.json, ignoré par git).

Coût connu localement (bancs uniquement, affichés par `make lab13-banc`) : 0,0273 $ + 0,0308 $ = 0,0581 $. Le
coût des trois exécutions de `make lab13-question` n'est pas affiché par cette cible : coût total à relever sur
le tableau de bord OpenRouter (sous le budget de 0,30 $ du plan).
