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
- `make lab13-question` pose la question avec le vrai modèle et garde l'exécution de la question cible (`Q=1`)
  dans `labs/lab13/execution.json` (question, plan, réponse, trace — secrets masqués) : c'est ce fichier, commité,
  que relisent `make lab13-verifier-note`, `make lab13-derive` et le critère décisif du vérificateur. `Q=2`, `Q=3`
  et `QUESTION="…"` sont gardées à côté (`execution-q2.json`, `execution-q3.json`, `execution-libre.json`) et
  n'écrasent pas l'exécution de la question cible.
- Le vérificateur de note cherche chaque élément dans les **résultats** d'outils de la trace. Il accepte un nombre
  calculé seulement comme somme ou différence de deux nombres **frères** — valeurs d'un même objet JSON d'un
  résultat, de clés de même unité (`_m`, `_kt`, `_km`, `_min`, `_h`, `_s`) — et à condition que la note écrive
  cette unité (la marge « 0,6 m » = 13,5 − 12,9) ; rien n'est calculé sur du texte libre, ni entre deux appels.
  « 6 heures » en toutes lettres est une durée (un nombre, jamais cherché dans un horodatage) ; `08/10` (année
  2026), `21:04:24` et `ALR-0003` sont reconnus. Une valeur tirée de la **description** d'un outil (les seuils
  25 kt et 35 kt de `meteo_alerte`) n'est pas dans la trace : elle reste sans origine, par choix (spec §8.2).
  Coïncidence résiduelle assumée : sur la trace de référence, « 13,1 m » passe comme 13,5 − 0,4 (`quai_max_m` et
  `depassement_m`, frères du même détail). Les noms hors de la liste du kit (navires, armateurs, agents) ne sont
  pas vérifiés. Une note sans appel d'outil derrière (plan refusé) ou sans aucun élément vérifiable n'est pas
  une réussite : « pas de note à vérifier ».

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

Thème sombre : la vue suit les variables de thème de l'hôte pour le fond et le texte, mais garde quelques
couleurs en dur (`#666` pour le résumé, `#888` pour l'axe des heures, `#ddd` pour les séparations des quais) ;
en thème sombre de VS Code, résumé et graduations peuvent être peu lisibles. À constater avec la vue, et à noter ici.

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
  dégradation observée est un résultat de calibration, pas un motif pour l'omettre. Ces mesures du catalogue et
  du banc ne sont pas rejouées lors du ré-étalonnage ci-dessous : elles ne dépendent ni de la consigne système,
  ni de l'invite du plan, que corrige le premier tour.

**Premier tour — la question cible, trois exécutions** (`make lab13-question Q=1` avec `ok`/`oui` sur l'entrée
standard, puis `make lab13-verifier-note` et `make lab13-derive`) — question : « L'escale du Vent d'Autan de
jeudi est-elle à risque ? Si oui, prépare la note d'alerte pour l'exploitant. » Dans les trois exécutions, le
modèle s'arrête après avoir proposé le texte de la note et demandé la confirmation en prose, sans appeler
`publier_alerte` : le second jeton (`oui`) posé sur l'entrée standard reste inutilisé, et la confirmation du LAB
12 avant publication n'est donc atteinte dans aucune des trois.

| # | Plan annoncé | Appels (trace) | Superflus | Données sans origine | Signaux (hors plan / jamais exécutées / retours) | Confirmation avant `publier_alerte` |
|---|---|---|---|---|---|---|
| 1 | 3 étapes : `lister_escales`, `details_escale`, `consulter_meteo` (serveurs non nommés) | `navire_par_nom` (pharos-ops), `escales_a_risque` (pharos-data), `meteo_creneau` (pharos-ops) — 3 appels | 0 | 0 (27 éléments vérifiés) | 3 / 3 / 0 | non atteinte (pas de publication) |
| 2 | 2 étapes : `rechercher_escales`, `obtenir_meteo` | `navire_par_nom`, `escales_a_risque`, `conflits_de_creneau`, `meteo_creneau` — 4 appels | 1 — `conflits_de_creneau` (pharos-data) : mêmes données que `escales_a_risque` (conflit `ESC-2026-0412`/`ESC-2026-0413`, 60 min), aucune valeur de la note n'y est rattachée | 0 (26 éléments vérifiés) | 4 / 2 / 0 | non atteinte (pas de publication) |
| 3 | 3 étapes : `obtenir_escales`, `obtenir_meteo`, `obtenir_alertes` | `navire_par_nom`, `escales_a_risque`, `meteo_creneau`, `meteo_alerte` — 4 appels | 0 — `meteo_alerte` fournit les seuils (25 kt, 35 kt) repris dans la réponse, et confirme le risque | 0 (28 éléments vérifiés) | 4 / 3 / 0 | non atteinte (pas de publication) |

Ce premier tour, initialement clos sur l'exécution 3 (dernière des trois sans donnée sans origine et à au plus un
appel superflu), a été rouvert par le contrôleur : la relecture de ces trois exécutions a mis en évidence trois
défauts de la solution de référence, indépendants du choix d'exécution —

- **(a) le plan nomme des outils qui n'existent pas** (`lister_escales`, `details_escale`, `consulter_meteo`,
  `rechercher_escales`, `obtenir_meteo`, `obtenir_escales`, `obtenir_alertes`) : `demander_plan` invitait le
  modèle à annoncer un plan sans lui rappeler la liste exacte des noms d'outils, alors même que le catalogue lui
  était transmis. Chaque étape restait donc au serveur « ? », et les signaux de dérive (appels hors plan, étapes
  jamais exécutées) ne mesuraient qu'un désaccord de vocabulaire, pas un vrai écart d'exécution.
- **(b) la confirmation du LAB 12 n'est jamais déclenchée** : le modèle demande lui-même, en texte, si l'
  exploitant souhaite publier, puis s'arrête sans appeler `publier_alerte` — la consigne système ne le dirigeait
  pas vers cet outil pour la confirmation, qui reste pourtant un critère du brief.
- **(c) les pénalités de retard du contrat ne sont jamais recherchées** (brief, étape 3.2) : `rechercher_clause`
  n'apparaît dans aucune des trois traces, alors que la consigne système ne mentionnait pas que la note d'alerte
  doit reprendre ces pénalités.

Correction apportée (commit `7eebbcb`) : `solutions/lab13/client/pharos_client/plan.py` (`demander_plan`) ajoute
à l'invite la liste exacte des noms d'outils du catalogue ; `consigne.md` (solution et gabarit, tenus identiques)
précise qu'une note d'alerte reprend risque, météo **et pénalités contractuelles**, et que la publication se fait
en appelant `publier_alerte` — pas en le demandant soi-même en texte. `uv run pytest -q tests/test_kit_lab13.py
tests/solutions/test_lab13.py` : 13 + 12 = 25 passed.

**Second tour — ré-étalonnage après correction**, même protocole (superposition de l'état LAB 13 corrigé, `make
up`, `make lab8-base`, `make lab10-mocks`, `make lab13-tout`, puis trois exécutions de la question cible) ; traces
sous `sortie/etalonnage-lab13-v2/` :

| # | Plan annoncé (réel ?) | Appels (trace) | `rechercher_clause` | `publier_alerte` + confirmation | Superflus | Données sans origine | Signaux (hors plan / jamais exécutées / retours) |
|---|---|---|---|---|---|---|---|
| 1 | 5 étapes, 3 serveurs, tous des outils réels : `navire_par_nom`(pharos-ops), `escales_a_risque`(pharos-data), `meteo_creneau`(pharos-ops), `rechercher_clause`(pharos-docs), `publier_alerte`(pharos-ops) | mêmes 5, dans le même ordre — 5 appels | oui (CM-0412, art. 7) | oui — « Publier l'alerte (oui/non) : » demandée puis confirmée (`oui`) avant l'appel ; alerte `ALR-0001` publiée | 0 | 0 (36 éléments vérifiés) | 0 / 0 / 0 |
| 2 | 5 étapes, 3 serveurs, tous réels, mais l'étape 1 nomme `data_navire_par_nom` (pharos-data) | `navire_par_nom` (pharos-ops) appelé à la place de l'étape 1, puis `escales_a_risque`, `meteo_creneau`, `rechercher_clause`, `publier_alerte` — 5 appels | oui | oui — confirmée avant l'appel ; alerte `ALR-0002` publiée | 0 | 0 (32 éléments vérifiés) | 1 / 1 / 0 |
| **3 (retenue)** | 5 étapes, 3 serveurs, tous réels ; même écart d'étiquette qu'en 2 (`data_navire_par_nom` planifié, `navire_par_nom` appelé) | `navire_par_nom`, `escales_a_risque`, `meteo_creneau`, `rechercher_clause`, `publier_alerte` — 5 appels | oui | oui — confirmée avant l'appel ; alerte `ALR-0003` publiée | 0 | 0 (43 éléments vérifiés) | 1 / 1 / 0 |

Les trois exécutions du second tour satisfont le double critère du brief (0 donnée sans origine, ≤ 1 appel
superflu) et appellent `publier_alerte` avec confirmation demandée par l'outil lui-même (les trois défauts (a),
(b), (c) du premier tour sont résolus). Exécution retenue : **la 3**, dernière des trois exécutions qualifiées où
`publier_alerte` a été appelé avec sa confirmation — recopiée dans `solutions/lab13/labs/lab13/execution.json` à
la place de l'exécution du premier tour. Le léger écart de dénomination entre l'étape 1 du plan
(`data_navire_par_nom`) et l'appel réel (`navire_par_nom`) subsiste dans les exécutions 2 et 3 : les deux outils
sont réels et le catalogue les distingue (pharos-data / pharos-ops), le modèle en choisit un des deux sans s'en
tenir à celui qu'il avait annoncé — signal de dérive résiduel, mineur (1 appel hors plan, 1 étape jamais
exécutée), consigné tel quel plutôt que masqué.

Les trois traces complètes des deux tours sont gardées hors dépôt (`sortie/` ignoré par git) :
`sortie/etalonnage-lab13/` (premier tour) et `sortie/etalonnage-lab13-v2/` (second tour).

**Troisième tour — ré-étalonnage après durcissement du vérificateur de note** (revue finale du plan 1, 2026-09-27).
Le vérificateur de l'époque acceptait une opération (×, +, −) entre deux nombres quelconques d'un même appel
(jusqu'à 200 nombres par appel, texte libre compris) : sur la trace retenue au second tour, 199 décimaux sur 199
de 0,1 à 19,9 avaient une « origine ». Inventions ajoutées à la note, rejouées sur cette trace — avant → après :

| Invention | Avant | Après |
|---|---|---|
| Houle 3,1 m | ✅ « calcul : 4,4 − 1,3 » | ❌ sans origine |
| Vent 27 kt | ✅ « 2 × 13,5 » | ❌ |
| Rafales 48 kt | ✅ « 3 + 45 » | ❌ |
| Tirant d'eau 13,1 m | ✅ « 13,5 − 0,4 » | ✅ « 13,5 − 0,4 » (frères `_m` du détail tirant d'eau : coïncidence assumée) |
| Visibilité 2,5 km | ✅ « 3 − 0,5 » | ❌ |
| Franchise 8 heures | ✅ (heure 08:00 d'un horodatage météo) | ❌ (durée : le nombre 8 n'est pas dans la trace) |

Avec le vérificateur durci, la note retenue au second tour n'est plus à 0 : **25** et **35** (les seuils de vent
et de rafales, « dépassement du seuil de 25 kt / 35 kt ») sont sans origine — ils viennent de la description de
`meteo_alerte`, qui n'a pas été appelé ; leur « origine » d'alors était une coïncidence (5 × 5, 1 + 34). Rejouées
avec le nouveau vérificateur, les exécutions des deux premiers tours donnent : premier tour 25/35 sans origine
pour 1 et 2, 0 pour 3 (qui avait appelé `meteo_alerte`) ; second tour 25/35 sans origine pour les trois. Le
numéro de titre « #### 4. » de la note, lui, passait aussi par coïncidence : il est désormais exclu comme un
numéro d'étape (faux positif corrigé, pas une donnée).

Même protocole qu'au second tour (superposition de l'état LAB 13, `make up`, `make lab8-base`, `make
lab10-mocks`, `make lab13-tout`, `make lab13-verifier SANS_MODELE=1` : 9 ✅, 1 ❌ (le critère décisif, sur
l'exécution du second tour), 2 👁 ; puis trois exécutions de la question cible) ; traces sous
`sortie/etalonnage-lab13-v3/` :

| # | Plan annoncé | Appels (trace) | `rechercher_clause` | `publier_alerte` + confirmation | Superflus | Données sans origine | Signaux (hors plan / jamais exécutées / retours) |
|---|---|---|---|---|---|---|---|
| 1 | 5 étapes, 3 serveurs, tous réels : `escales_a_risque`, `navire_par_nom`, `meteo_creneau`, `rechercher_clause`, `publier_alerte` | `navire_par_nom`, `escales_a_risque`, `meteo_creneau`, `rechercher_clause`, `publier_alerte` — 5 appels | oui | oui — confirmée avant l'appel ; `ALR-0001` | 0 | 0 (47 éléments vérifiés) | 0 / 0 / 0 |
| **2 (retenue)** | 5 étapes, 3 serveurs, tous réels ; l'étape 2 nomme `data_navire_par_nom` (pharos-data) | mêmes 5 appels (`navire_par_nom` de pharos-ops à la place de l'étape 2) | oui | oui — confirmée avant l'appel ; `ALR-0002` | 0 | 0 (37 éléments vérifiés) | 1 / 1 / 0 |
| 3 | 5 étapes, 3 serveurs, tous réels, dans l'ordre des appels | mêmes 5 appels | oui | oui — confirmée avant l'appel ; `ALR-0003` | 0 | **2 — 25, 35** (seuils cités d'après la description de `meteo_alerte`) | 0 / 0 / 0 |

Exécution retenue : **la 2**, dernière des trois à 0 donnée sans origine, au plus un appel superflu, et
`publier_alerte` appelé avec sa confirmation — recopiée dans `solutions/lab13/labs/lab13/execution.json`. Ses
mesures sont celles déjà consignées dans `mesures.md` (0 superflu, 0 sans origine, signaux 1 / 1 / 0) : le
fichier ne change pas. Sur la trace retenue, les six inventions ci-dessus donnent le même verdict (cinq ❌, 13,1
m accepté comme 13,5 − 0,4). Le modèle cite spontanément les seuils de `meteo_alerte` sans l'appeler dans 6 des 9
exécutions des trois tours : le vérificateur le signale désormais, ce que la consigne (« chaque chiffre … doit
venir d'un résultat d'outil ») demande ; c'est la limite la plus probable que rencontreront les binômes.

Coût : trois exécutions de `make lab13-question` de plus, à relever sur le tableau de bord OpenRouter.

Coût connu localement (bancs uniquement, affichés par `make lab13-banc`) : 0,0273 $ + 0,0308 $ = 0,0581 $. Le
coût des six exécutions de `make lab13-question` (trois par tour) n'est pas affiché par cette cible : coût total
à relever sur le tableau de bord OpenRouter (sous le budget de 0,30 $ du plan).

## Le service de salle et l'anneau (LAB 14)

- **Un seul poste exposé.** `make salle-demarrer N=5` lance `pharos-salle` sur `0.0.0.0:8300` (poste du
  formateur) et tire cinq jetons dans `salle/jetons.txt` (git-ignoré, à distribuer sur papier). Les PHAROS
  des binômes restent sur 127.0.0.1 : vérifier depuis un poste que `http://<poste-formateur>:8300/tableau`
  répond, et qu'un port d'un binôme (8101…) ne répond pas depuis le voisin.
- **En local (préparation, tests, CI).** `make salle-locale` sert le même service sur `127.0.0.1:8300`.
- **Inscription des binômes.** Chacun : `make lab14-inscrire URL=http://<poste-formateur>:8300 BINOME=<b>
  JETON=<son jeton>` (écrit `labs/lab14/salle.env`, git-ignoré), et pose `PHAROS_BINOME=<b>` dans son `.env`
  (pharos-docs lit alors `contrats-partages/binome-<b>`).
- **Les manches.** `make salle-manche M=1` puis `M=2`, `M=3`. Anneau : manche 1, le binôme *b* attaque
  *b+1* ; manche 2, dépôt fermé (durcissement) ; manche 3, *b* attaque *b+2*. Le formateur coupe la manche 1
  à 45 minutes. Avec N ≤ 2, la manche 3 retombe sur *b+1* (le tableau le signale).
- **Le tour d'un binôme.** L'attaquant écrit son injection en Markdown (front-matter `Titre:`/`Escale:`
  optionnel) et `make lab14-deposer FICHIER=attaque.md`. La cible `make lab14-synchroniser` (les documents
  reçus deviennent des PDF dans `contrats-partages/binome-<b>/`), relance `make lab13-tout`, puis
  `make lab14-executer` (le vrai modèle, sous l'identité `jeton-rance` de l'escale du *Vent d'Autan*) :
  l'issue (A/B/C) remonte au tableau. C'est la cible qui exécute ; l'attaquant lit le tableau.
- **Le vérificateur** (`make lab14-verifier`) est déterministe (modèle simulé « crédule », pharos-db requis) :
  il sonde les contre-mesures, rejoue les trois documents piégés de référence, et contrôle les refus
  journalisés. Le critère décisif — reconstituer la manche 1 depuis la seule trace — se constate au débrief.
- 👁 La fiche de sécurité et le débrief (les trois questions, dont « impossible vs plus difficile ») sont le
  livrable le plus important de la journée : ils se traitent au tableau, ensemble.

**Étalonnage du LAB 14** : à consigner ici après la Task 6 (les trois documents piégés contre `etat/or3-fin`
— l'attaque réussit — puis contre la référence durcie — B et C échouent ; coût sur le tableau OpenRouter).
