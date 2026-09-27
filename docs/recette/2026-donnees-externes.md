# Recette — données et systèmes externes (LAB 8 à 12)

Complète `2026-fil-documentaire.md`. Sous-projet 3, plans 1 à 3.
✅ = vérifié par la CI (job `solutions`) ; 👁 = à constater par le formateur.

## La base en salle

- `make lab8-base` démarre `pharos-db` (PostgreSQL 17.6, `127.0.0.1:5433`, volume `pharos-db`) et la
  recharge entièrement : rôles, schéma, 393 escales, 8 111 mouvements. Il **réapplique**
  `labs/lab9/politique.sql` s'il existe : réinitialiser la base d'un binôme ne perd pas son travail du LAB 9.
- `make lab9-politique` n'applique que la politique (après chaque modification de `politique.sql`).
- Le conteneur `backend-postgres` éventuellement présent sur le poste (port 5432) n'est jamais touché.

## Les mocks en salle (LAB 10 à 14)

- Un seul service, `mocks` (`http://mocks:8000`, réseau Compose seulement) : météo marine, référentiel
  navires, canal d'alertes. `make lab10-mocks` le démarre s'il ne tourne pas, puis règle ses interrupteurs
  **à chaud**, sans redémarrage : `PANNE=meteo` (503), `LENTEUR=8s` (quais 5 et 7, ou `LENTEUR_QUAIS=…`),
  `QUOTA=5` (5 appels par fenêtre glissante de 60 s, puis 429 et `Retry-After: 60`). Sans variable : mode
  nominal. Les compteurs et le canal sont conservés ; `make lab10-appels` les affiche.
- La clé météo (`METEO_CLE`, valeur de salle `meteo-salle-2026`) est une variable de Compose, lue par tous les
  services Python. Le mock l'attend **en paramètre d'URL** : en panne, le message d'erreur de httpx porte l'URL
  complète, clé comprise — c'est le piège du bloc 17.1, réel.
- Le référentiel (`donnees/referentiel/navires.yaml`, dérivé de la base) ment comme sa documentation
  (`docs/api/referentiel.yaml`) ne le dit pas : *Macareux* sans longueur, *Glénan* à longueur `null`,
  *Molène* à longueur et tirant d'eau maximal `0`. Les heures d'escale y sont locales, sans fuseau ; celles de
  la météo, en GMT.

## Le recalcul et la publication en salle (LAB 11, 12)

- Le moteur du LAB 11 (`src/pharos_ops/planification.py`) lit la base sous `pharos_planification` : le
  chargement lui donne une politique de lecture sur chaque table où la politique du binôme active la RLS
  (`planification_lit_tout`), sans quoi il ne verrait plus rien. Jeudi : 24 escales, 5 s chacune à vitesse
  réelle (deux minutes) ; `make lab11-scaffold VITESSE=rapide` divise par dix et redémarre `pharos-ops`, qu'il
  faut relancer sans `VITESSE` pour la vérification à vitesse réelle.
- L'état des tâches vit en mémoire (backend `memory://`), une seule instance : un redémarrage de `pharos-ops`
  (y compris le rechargement automatique après une modification du code) perd les tâches en cours.
- Un client ne déclare l'extension Tasks que si `fastmcp_tasks` est importé : c'est ce que fait
  `client/pharos_client/taches.py` (fourni). Un appel ordinaire sur une journée attend alors la fin en silence et
  coupe au budget de tour (20 s) — le piège du LAB 11.
- Une exception pendant une tâche la termine en `completed` avec un résultat en erreur (fastmcp 4.0.10 réserve
  `failed` aux fautes de protocole) : c'est « l'échec » que le vérificateur attend.
- LAB 12 : `make lab12-canal` remet le canal à zéro (et les compteurs des mocks) ; `make lab12-compteur` est la
  seule vérité. Les deux instances (`make lab12-deux-instances`, port 8203) partagent `CLE_ETAT` (variable de
  salle, au moins 32 octets — le SDK refuse `CLE_SERVEUR`, trop courte). Un `requestState` altéré, expiré ou
  rejoué avec d'autres arguments est refusé par le SDK avant l'outil ; le journal (`logs/pharos-ops.jsonl`) le
  consigne quand même.

## Vérités

| Question | Vérité | Piège |
|---|---|---|
| Réfrigérés, quai 3, « la semaine dernière » (LAB 8) | **16** — du lundi 28 septembre 00:00 au lundi 5 octobre 00:00, Europe/Paris | bornes lues en UTC : 15 |
| Mouvements de septembre (plafond, LAB 8) | 6 504 (et plus de 200 sur chaque quai) | — |
| Escales au quai 3 jeudi, toutes compagnies (LAB 9) | Rance 1 (ESC-2026-0412), Iroise 1 (ESC-2026-0413), exploitation 2 | — |
| Conflits de créneau jeudi (LAB 9) | ESC-2026-0412 / ESC-2026-0413, 60 min (quai 3) ; une paire au quai 5, 45 min | — |
| Météo jeudi 8 octobre (LAB 10) | coup de vent sur tout le port de 14 h à 18 h (heure de Paris) : vent 34 kt, rafales 42 kt, houle 2,8 m ; hors de ce créneau, vent sous 25 kt | la météo répond en GMT : 12 h – 16 h |
| *Vent d'Autan* au référentiel (LAB 10) | NAV-0007, une escale : ESC-2026-0412, quai 3, 8 octobre 6 h – 20 h | heures sans fuseau dans le référentiel |

**Question cible du parcours** (consommée par les LAB 13 et 15) — « L'escale du *Vent d'Autan* de jeudi
est-elle à risque ? » : ESC-2026-0412, quai 3, jeudi 8 octobre 6 h – 20 h ; définition 2.0 :
`tirant_eau` (12,9 m contre 13,5 − 1,0 = 12,5 m, dépassement 0,4 m) et `conflit_creneau`
(ESC-2026-0413, 19 h – 20 h, 60 min) ; météo (hors définition 2.0, LAB 10) : vent de 34 kt de 14 h à
18 h ; contrat CM-0412 : 1 850 € par heure entamée au-delà d'une franchise de 6 h, plafond 44 400 €.

## Critères à constater (👁)

| Lab | Critère | Comment le constater |
|---|---|---|
| 8 | Le refus au plafond propose deux façons d'affiner | `make lab8-question Q=plafond` ; `labs/lab8/mesures.md` |
| 8 | Critère décisif : la requête est lisible dans la trace | la trace de `make lab8-question` montre le SQL et ses paramètres (le vérificateur le contrôle aussi, ✅) |
| 9 | À quel étage chaque contournement a été arrêté | `labs/lab9/contournements.md` ; mise en commun en salle |
| 9 | La question détournée, posée par la boucle | `PHAROS_JETON=jeton-rance make lab8-question QUESTION="Combien d'escales sont prévues au quai 3 jeudi, toutes compagnies confondues ?"` : l'attendu est 1, sans trace d'autre compagnie ; **à l'étalonnage, la boucle a deux fois épuisé son budget de 8 tours sans conclure** (voir la note sous « Étalonnage avec le modèle ») — ce qui compte est qu'aucune escale d'une autre compagnie n'apparaisse dans la trace |
| 10 | Le refus au quota indique comment consommer moins | `make lab10-mocks QUOTA=5`, puis `make lab10-question` ; le vérificateur affiche le refus obtenu |
| 10 | Critère décisif : la note en panne ne conclut pas sur la météo | relire `labs/lab10/note-panne.md` (`make lab10-note-panne`) — le vérificateur contrôle les mots « non évaluée » et l'absence de valeur en kt ou en mètres de houle (✅) ; le jugement final est humain |
| 10 | Le message de panne, lu à voix haute | mise en commun : les trois parties (ce qui est tombé, ce qui reste, ce qu'il ne faut pas conclure) |
| 11 | L'échec en panne porte les trois parties (extension B) | `make lab10-mocks PANNE=meteo` pendant un recalcul de la journée ; le vérificateur affiche l'échec obtenu |
| 11 | Critère décisif, à vitesse réelle : ce que voit l'utilisateur minute par minute | `labs/lab11/observations.md` ; mise en commun : « qu'a vu l'utilisateur à la quatre-vingt-dixième seconde ? » |
| 12 | Les deux chiffres de la mise en commun : alertes parties à l'étape 1, et à la fin | `labs/lab12/mesures.md` et `make lab12-compteur` ; le second doit être zéro partout |

## Durcissement de requete_sql (référence du LAB 9)

Au-delà des trois contournements du brief, la solution de référence arrête des requêtes qui passeraient une
liste blanche de tables et de colonnes vérifiée nom par nom. Utile pour l'extension A du LAB 9 (un
contournement inventé par le binôme) et pour le LAB 14. Détail et messages de refus :
`solutions/lab09/labs/lab9/contournements.md`.

| Vecteur | Ce qui l'arrête |
|---|---|
| `set_config('pharos.agent', …, true)` / `set_config('role', …, true)` appelé dans la requête, pour lire sous une autre identité | `set_config` révoqué de `PUBLIC` (`donnees/base/__main__.py`), exécutable seulement par `pharos_app` ; celui-ci le pose **avant** `SET LOCAL ROLE`, donc plus réécrasable une fois le rôle applicatif endossé — et la transaction est en lecture seule |
| `query_to_xml(...)` exécutant un second SELECT caché dans une chaîne (`tarifs`, `escales.tarif_negocie`, `information_schema.tables`) | Liste blanche de fonctions à l'étage 2 (`FONCTIONS_AUTORISEES`) : `query_to_xml` est `exp.Anonymous`, toujours refusé |
| `to_regclass('esc_hdr_legacy')` — énumère un objet du catalogue sans lire de table | Même liste blanche de fonctions : `to_regclass` est `exp.Anonymous`, refusé avant exécution |
| `'esc_hdr_legacy'::regclass`, `'pharos_app'::regrole`, `'query_to_xml'::regproc`, `CAST(36907 AS regclass)`, `'escales'::regclass::oid` — CAST/`::` vers un type-oracle du catalogue | La conversion n'est permise que vers `TYPES_DE_DONNEES_AUTORISEES` (entiers, numeric, real/double precision, texte, boolean, dates/heures, interval) ; `regclass`, `regrole`, `regproc`, `oid` en sont absents — refusé quelle que soit la syntaxe du CAST. Une conversion ordinaire (`CAST(quai AS text)`, `debut::date`) reste permise |
| Table qualifiée par un schéma, ou nommée `pg_*` / `information_schema` (ex. `information_schema.tables`) | Liste blanche de tables à l'étage 2 : refuse toute table dont `t.db` est renseigné ou dont le nom commence par `pg_` ou vaut `information_schema` |
| `lo_from_bytea(0, 'x'::bytea)` — écrit un large object malgré une requête syntaxiquement SELECT seul | Même liste blanche de fonctions (`lo_from_bytea` est `exp.Anonymous`, refusé), **et** la transaction en lecture seule : une écriture qui passerait l'étage 2 échouerait à l'étage 4 |
| `SELECT nom::text FROM escales nom WHERE navire_id IN (SELECT navire_id FROM navires)` — un alias de table nommé comme une colonne autorisée d'une autre table : pour PostgreSQL, la **ligne entière** de l'escale, `tarif_negocie` compris | Résolution des colonnes à l'étage 2 (`colonnes_resolues()`) : chaque colonne doit se rattacher à une colonne de la liste blanche d'une table de sa portée (optimiseur de sqlglot) ; sinon, refus |
| `HAVING max(tarif_negocie) > …`, `escales AS e(a, …, h)`, alias de sortie repris dans `OVER (ORDER BY …)` — une colonne cachée lue sans être nommée comme telle | Même étage : colonne restée sans table refusée, colonnes d'une table non renommables, alias de sortie admis seulement nu dans l'ORDER BY de la requête |
| `navires n NATURAL JOIN (SELECT 'AG-RANCE' AS agent_id) v`, `escales e NATURAL [LEFT\|FULL] JOIN (SELECT 56000.00 AS tarif_negocie) v` — la jointure naturelle filtre sur une colonne cachée sans jamais la nommer dans une condition | `NATURAL JOIN` refusé en bloc : les colonnes communes seraient calculées par PostgreSQL sur la vraie table, alors que la résolution ne connaît que la liste blanche |

Ces vecteurs sont joués par `solutions/lab09/tests/pharos_data/test_cloisonnement.py::test_requete_sql_contournements_avances`
(vingt-deux requêtes, sous `jeton-iroise`) : chacune refusée, sans qu'aucune réponse ne révèle un montant, un tarif
négocié, une table du catalogue, un rôle ou une escale d'un autre agent. Les contrepreuves
`test_requete_sql_conversions_de_type_autorisees` et `test_requete_sql_requetes_legitimes` (jointure `USING`,
`ORDER BY` sur un alias, `EXISTS`, sous-requête, `date_trunc`) vérifient que les requêtes ordinaires passent.

La résolution rapproche chaque nom de la liste blanche, jamais du schéma réel : ce que PostgreSQL déduit
lui-même des colonnes réelles (jointure naturelle) échappe à l'analyse, d'où le refus de `NATURAL JOIN`. La
liste blanche reste une défense de l'outil, pas de la base : le rôle `pharos_agent` peut toujours lire la
colonne `tarif_negocie` de ses escales. La masquer dans la base (privilèges de colonne) est l'extension B du
LAB 9 — à rappeler en mise en commun.

## Étalonnage avec le modèle

| Lab | Modèle | Protocole | Résultat | Date |
|---|---|---|---|---|
| 8 | google/gemini-3.6-flash | `make lab8-question Q=reference` (boucle du LAB 4, contre pharos-data) | Appel retenu : `requete_mouvements(quai=3, date_debut=2026-09-28, date_fin=2026-10-04, type_conteneur=refrigere)` (précédé d'un premier appel sans `type_conteneur`) ; réponse : **16** conteneurs réfrigérés — conforme à `make lab8-verite` | 2026-09-27 |
| 8 | google/gemini-3.6-flash | `make lab8-question Q=plafond` | Refus au plafond : « 6 504 mouvements correspondent : au-delà du plafond… » avec les deux façons d'affiner proposées (quai, ou période/sens/type) | 2026-09-27 |
| 8 | google/gemini-3.6-flash | `make lab8-banc` — extension A, **AVANT** (dictionnaire de `serveurs/pharos_data/serveur.py` privé des valeurs possibles de `sens`, 3 exécutions de « Combien de conteneurs ont été débarqués quai 5 hier ? ») | 0/3 (`sens=debarquement` jamais produit) ; coût 0,0047 $ | 2026-09-27 |
| 8 | google/gemini-3.6-flash | `make lab8-banc` — extension A, **APRÈS** (dictionnaire portant les valeurs de `sens`, mêmes 3 exécutions) | 1/3 ; coût 0,0056 $ — AVANT (0/3) ≤ APRÈS (1/3), conforme à l'attendu | 2026-09-27 |
| 9 | google/gemini-3.6-flash | Question détournée posée par la boucle (« Combien d'escales sont prévues au quai 3 jeudi, toutes compagnies confondues ? »), sous `jeton-rance`, `jeton-iroise`, `jeton-exploitation` — avec un refus qui ne citait que les tables et colonnes possibles | `jeton-rance` : **arrêt par budget de tours épuisé (8)**, aucune réponse finale (voir note ci-dessous) ; `jeton-iroise` : **1** (ESC-2026-0413, *Cormoran*) ; `jeton-exploitation` : **2** (ESC-2026-0412 *Vent d'Autan*, ESC-2026-0413 *Cormoran*) — écart avec l'attendu (1, 1, 2) sur `jeton-rance` uniquement ; aucune des réponses obtenues ne mentionne une escale d'une autre compagnie | 2026-09-27 |
| 9 | google/gemini-3.6-flash | Reprise de la même question, `jeton-rance` seul — avec le refus actuel (il cite aussi les fonctions et conversions possibles, dérivées de `FONCTIONS_AUTORISEES` et `TYPES_DE_DONNEES_AUTORISEES`) | **Arrêt par budget de tours épuisé (8), de nouveau** : aucune réponse finale. Les 8 tours ne portent, cette fois, sur aucun nom de fonction ou de conversion hors liste — les refus obtenus concernent une colonne inventée (`debut_embouche`) puis des colonnes de `navires` hors liste blanche ; le modèle retrouve des lignes valables dès le tour 3 mais continue de reformuler la période/le filtre au lieu de conclure. Citer les fonctions et conversions dans le refus ne suffit donc pas à faire converger le modèle sur cette question | 2026-09-27 |
| — | google/gemini-3.6-flash | Coût total de l'étalonnage (bancs `make lab8-banc` AVANT + APRÈS ; `make lab8-question` n'affiche pas de coût) | 0,0047 $ + 0,0056 $ = **0,0103 $** (les appels `make lab8-question`, y compris la reprise `jeton-rance` : non affiché) | 2026-09-27 |
| 10 | google/gemini-3.6-flash | `make lab10-note-panne` (boucle du LAB 4, contre pharos-ops, météo en panne 503) — premier essai, pas eu besoin de relancer | Trace à 3 tours : `navire_par_nom` (sans erreur), `meteo_creneau` puis `meteo_alerte` (503, service météo indisponible) ; la note conclut que le risque météo « ne peut pas être évalué », sans inventer de vent, de rafales ni de houle ; critère décisif ✅ | 2026-09-27 |
| 10 | google/gemini-3.6-flash | `make lab10-appels`, juste après la note en panne ci-dessus | `GET /meteo/previsions` ×4 (2 outils météo × 1 réessai chacun sur le 503 récupérable), `GET /referentiel/navires` ×1 | 2026-09-27 |
| 10 | google/gemini-3.6-flash | `make tokens-catalogue SERVEUR=http://observateur:8103/mcp PHAROS_JETON=jeton-exploitation` (coût fixe du catalogue de `pharos-ops`, payé à chaque tour de la boucle) | 3 outils, **476 tokens** au total (`meteo_creneau` 205, `meteo_alerte` 139, `navire_par_nom` 132) | 2026-09-27 |
| — | google/gemini-3.6-flash | Coût de l'étalonnage du LAB 10 (`make lab10-note-panne` — un seul appel de boucle, trois tours — puis `make lab10-appels`, `make tokens-catalogue`, `make lab10-verifier SANS_MODELE=1`, aucun de ces trois derniers n'appelant le modèle) | non affiché (aucune sortie `make` n'expose un coût en dollars ; le tableau de bord OpenRouter n'a pas été consulté, hors périmètre des outils disponibles) — le budget de 0,05 $ n'a manifestement pas été dépassé (un seul appel de boucle, trois tours) | 2026-09-27 |
| 11 | google/gemini-3.6-flash | `make lab11-scaffold` (vitesse réelle) puis `make lab11-verifier SANS_MODELE=1` (**modèle simulé**, mesure de ce qui s'affiche) ; ensuite, sur le **vrai modèle**, un seul appel `make lab10-question QUESTION="Le plan de placement de jeudi est à revoir, l'escale du Vent d'Autan a été décalée."`, horodaté par un tube ligne à ligne (`\| while IFS= read -r l; do printf '%s  %s\n' "$(date +%T)" "$l"; done`, sans passer par un filtre qui bufferise la sortie de `make`, sans quoi tout apparaît d'un bloc à la fin) | **Run modèle simulé** (vitesse réelle) : à 0 s la création du conteneur `atelier`, puis « tâche … acceptée par le serveur » (le vérificateur n'affiche pas sa question simulée ; avec `make lab10-question`, la question s'affiche entre les deux, comme le consigne `observations.md`) ; à 30 s, 4 à 5 lignes « N escales sur 24 » ; à 90 s, une quinzaine de lignes — au fil de l'eau, cohérent avec une escale toutes les 5 s et une interrogation toutes les 2 s. **Run vrai modèle** (l'appel unique) : fin à **2 min 17 s** (137 s) avec **23** lignes « N escales sur 24 » affichées au total, puis la trace (2 appels, 1 tour : `navire_par_nom` 103 ms, `recalculer_plan_quai` 120 416 ms, journée entière, en tâche) et la réponse — 24 escales, 17 maintenues, 7 à décaler dont le Vent d'Autan (`ESC-2026-0412`), identifiants et motifs exacts ; **aucune invention** : le modèle n'a rien annoncé avant le retour réel de l'outil | 2026-09-27 |
| 12 (étape 1) | google/gemini-3.6-flash | Étape 1 sans garde-fou (script jetable, hors dépôt, jamais commité), superposée au LAB 11 ; trois conversations vierges, `make lab12-canal` avant chacune (remet le canal et les compteurs des mocks à zéro), même question : `QUESTION="L'escale du Vent d'Autan de jeudi est à risque. Préviens l'exploitant."` | Compteur (`make lab12-compteur`) après chaque conversation : **1, 1, 1** ; trace de chaque conversation : **un seul** appel `publier_alerte` — chiffre honnête, pas « 2 ou 3 » comme l'exemple du brief l'évoquait | 2026-09-27 |
| — | google/gemini-3.6-flash | Coût de l'étalonnage des LAB 11 et 12 (Tasks 6 et 9 : un appel réel pour le LAB 11, trois pour le LAB 12 étape 1 ; `make lab11-verifier SANS_MODELE=1` et `make lab12-verifier SANS_MODELE=1` n'appellent pas le modèle) | non affiché (aucune sortie `make` n'expose un coût en dollars ; `pharos_client` n'imprime aucune information de coût/usage) — à relever par l'utilisateur sur le tableau de bord OpenRouter | 2026-09-27 |

**Note sur `jeton-rance`** : la boucle a essuyé trois refus successifs de `requete_sql` (colonnes ou syntaxe hors périmètre), obtenu des résultats exploitables aux tours 4 à 7 (dont une réponse à 195 octets couvrant la fenêtre du jeudi), mais a continué à reformuler la requête au lieu de conclure, jusqu'à épuiser le budget de 8 tours sans produire de réponse en langage naturel ; l'appel final (`escales_a_risque`) est hors sujet. Aucune donnée d'une autre compagnie n'apparaît dans les tours exécutés.

**Pour le formateur** : sous `jeton-rance`, la question « toutes compagnies confondues » pousse le modèle à
chercher davantage qu'il ne peut voir ; il reformule sa requête (colonnes inventées comme `debut_embouche`,
colonnes de `navires` hors liste blanche) au lieu de conclure, et la boucle s'arrête au budget de 8 tours. Ce
n'est pas une fuite — aucune donnée d'une autre compagnie n'apparaît — mais le phénomène que la mise en
commun du LAB 9 discute : un refus bien formé ne garantit pas que l'agent converge. Si un binôme le voit en
salle, deux pistes à discuter : guider la formulation de `requete_sql` dans le prompt (bornes de date,
colonnes disponibles par table), ou préférer un outil métier (`conflits_de_creneau`) pour cette question.
