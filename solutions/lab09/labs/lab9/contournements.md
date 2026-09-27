# LAB 9 — trois contournements

Ils ont été écrits pour passer. Les envoyer à `requete_sql`, sous l'identité d'un agent maritime :

```bash
make lab9-contourner N=1 PHAROS_JETON=jeton-rance      # N=1, 2 ou 3
```

| | Contournement | Ce qui doit l'arrêter |
|---|---|---|
| 1 | Écriture déguisée dans une expression de table commune | Liste blanche d'instructions **et** rôle en lecture seule |
| 2 | Jointure vers une table hors périmètre (`tarifs`) | Liste blanche de tables, avant exécution |
| 3 | Énumération du schéma par messages d'erreur successifs | Message uniforme, ne portant que la liste blanche |

## 1 — Écriture déguisée

```sql
WITH x AS (DELETE FROM mouvements RETURNING *) SELECT count(*) FROM x
```

## 2 — Jointure hors périmètre

```sql
SELECT e.escale_id, t.montant FROM escales e JOIN tarifs t ON t.navire_id = e.navire_id
```

## 3 — Énumération par l'erreur

```sql
SELECT e.tarif_negocie FROM escales e
SELECT e.armateur FROM escales e
SELECT x.mouvement_id FROM esc_hdr_legacy x
```

## Ce qui les a arrêtés, et à quel étage

| | Arrêté à l'étage | Message reçu (début) |
|---|---|---|
| 1 | 1 — syntaxe (écriture cachée dans la CTE) ; le rôle en lecture seule l'aurait arrêtée aussi | « Requête refusée (instruction non autorisée). Seules des lectures SELECT… » |
| 2 | 2 — liste blanche de tables, avant exécution | « Requête refusée (table ou colonne hors périmètre). Seules des lectures SELECT… » |
| 3 | 2 — liste blanche de colonnes ; les trois refus ont la même forme et ne citent que la liste blanche | « Requête refusée (table ou colonne hors périmètre). Seules des lectures SELECT… » |

## Au-delà des trois : fonctions et variable de session

Trouvés par la revue de sécurité (correctif Task 11) : quatre sondes qui passaient les quatre étages sans
qu'aucune des trois contournements ci-dessus ne les couvre — la liste blanche de tables et de colonnes ne
regarde jamais les fonctions appelées, ni ce qu'une requête peut faire à la variable de session qui porte
l'identité.

| | Contournement | Ce qui l'arrête |
|---|---|---|
| 4 | `set_config('pharos.agent', 'AG-RANCE', true)` appelé dans une sous-requête, pour lire sous une autre identité que la sienne | `set_config` n'est plus exécutable que par `pharos_app` (révoqué de `PUBLIC` dans `donnees/base/__main__.py`) ; posé par lui avant `SET LOCAL ROLE`, il ne peut plus être réécrasé une fois le rôle applicatif endossé — et la transaction est en lecture seule |
| 5 | `query_to_xml(...)` exécutant un second SELECT (sur `tarifs`, `escales.tarif_negocie` ou `information_schema.tables`) caché dans une chaîne, invisible à l'analyse syntaxique de la requête externe | Liste blanche de fonctions à l'étage 2 (`FONCTIONS_AUTORISEES`) : `query_to_xml` n'y figure pas — comme toute fonction que sqlglot classe `exp.Anonymous`, toujours refusée |
| 6 | `to_regclass('esc_hdr_legacy')` — énumère l'existence d'un objet du catalogue sans lire aucune table | Même liste blanche de fonctions : `to_regclass` est `exp.Anonymous`, refusé avant toute exécution |
| 7 | `lo_from_bytea(0, 'x'::bytea)` — écrit un large object, malgré une requête syntaxiquement SELECT seul | Même liste blanche de fonctions, **et** la transaction en lecture seule (`connexion.transaction(readonly=True)`) : une écriture qui passerait l'étage 2 échouerait à l'étage 4 |

Les quatre sont testés dans `tests/pharos_data/test_cloisonnement.py::test_requete_sql_contournements_avances`,
sous `jeton-iroise` — chacun refusé, sans qu'aucune réponse ne révèle un montant, un tarif négocié, une table
du catalogue ou une escale d'un autre agent.
