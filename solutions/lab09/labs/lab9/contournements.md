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

## Au-delà des trois : fonctions, variable de session, conversions, colonnes

Une liste blanche de tables et de colonnes vérifiée nom par nom ne suffit pas : elle ne regarde ni les
fonctions appelées, ni ce qu'une requête peut faire à la variable de session qui porte l'identité, ni le type
vers lequel on convertit, ni ce que PostgreSQL entend vraiment par un nom de colonne. Les requêtes ci-dessous
passent un tel filtre ; la solution de référence les arrête toutes.

| | Contournement | Ce qui l'arrête |
|---|---|---|
| 4 | `set_config('pharos.agent', 'AG-RANCE', true)` appelé dans une sous-requête, pour lire sous une autre identité que la sienne | `set_config` n'est plus exécutable que par `pharos_app` (révoqué de `PUBLIC` dans `donnees/base/__main__.py`) ; posé par lui avant `SET LOCAL ROLE`, il ne peut plus être réécrasé une fois le rôle applicatif endossé — et la transaction est en lecture seule |
| 5 | `query_to_xml(...)` exécutant un second SELECT (sur `tarifs`, `escales.tarif_negocie` ou `information_schema.tables`) caché dans une chaîne, invisible à l'analyse syntaxique de la requête externe | Liste blanche de fonctions à l'étage 2 (`FONCTIONS_AUTORISEES`) : `query_to_xml` n'y figure pas — comme toute fonction que sqlglot classe `exp.Anonymous`, toujours refusée |
| 6 | `to_regclass('esc_hdr_legacy')` — énumère l'existence d'un objet du catalogue sans lire aucune table | Même liste blanche de fonctions : `to_regclass` est `exp.Anonymous`, refusé avant toute exécution |
| 7 | `lo_from_bytea(0, 'x'::bytea)` — écrit un large object, malgré une requête syntaxiquement SELECT seul | Même liste blanche de fonctions, **et** la transaction en lecture seule (`connexion.transaction(readonly=True)`) : une écriture qui passerait l'étage 2 échouerait à l'étage 4 |
| 8 | `'esc_hdr_legacy'::regclass::text`, `'pharos_app'::regrole::text`, `'query_to_xml'::regproc::text` — l'existence d'une table, d'un rôle ou d'une fonction, sans lire aucune table : l'énumération de la ligne 6 revient sous forme de conversion | La conversion (`CAST(x AS type)` ou `x::type`) n'est permise que vers un type de donnée ordinaire (`TYPES_DE_DONNEES_AUTORISEES` : entiers, `numeric`, `real`/`double precision`, texte, `boolean`, dates/heures, `interval`) ; `regclass`, `regrole`, `regproc`, `oid` n'y figurent pas — refusé avant toute exécution, quelle que soit la syntaxe du CAST |
| 9 | `CAST(36907 AS regclass)::text`, `'escales'::regclass::oid::int` — énumération du catalogue par OID, ou obtention de l'OID d'une table connue comme point de départ | Même liste de types : `regclass` et `oid` sont refusés comme cibles de conversion, que la valeur de départ soit un littéral, un OID numérique ou le résultat d'un autre CAST |
| 10 | `SELECT nom::text FROM escales nom WHERE navire_id IN (SELECT navire_id FROM navires)` — `nom` est une colonne autorisée (de `navires`), mais aucune table de la requête externe n'en a : pour PostgreSQL, c'est alors l'alias de table `nom`, c'est-à-dire **la ligne entière** de l'escale, `tarif_negocie` compris | Résolution des colonnes à l'étage 2 (`colonnes_resolues()`) : l'optimiseur de sqlglot rattache chaque colonne à une table de sa portée, sur un schéma qui ne connaît que la liste blanche ; un nom qui ne se résout pas en colonne autorisée est refusé |
| 11 | La même colonne cachée lue autrement : `HAVING max(tarif_negocie) > 50000` (que sqlglot ne rattache à aucune table), `escales AS e(a, b, …, h)` (colonnes renommées par position), `SELECT quai AS tarif_negocie … OVER (ORDER BY tarif_negocie)` (un alias de sortie que PostgreSQL lit comme la colonne d'entrée du même nom) | Même étage : une colonne restée sans table après résolution est refusée, les colonnes d'une table ne se renomment pas, et un alias de sortie n'est admis que nu, dans l'ORDER BY de la requête |
| 12 | `SELECT n.nom FROM navires n NATURAL JOIN (SELECT 'AG-RANCE' AS agent_id) v` — les navires d'une autre compagnie ; `escales e NATURAL JOIN (SELECT 56000.00 AS tarif_negocie) v` — un oracle sur le tarif négocié (aussi en `LEFT`, `FULL`, ou avec une CTE) | `NATURAL JOIN` est refusé quelle que soit sa forme : PostgreSQL joint sur les colonnes communes de la **vraie** table, colonnes cachées comprises, alors que la résolution ne connaît que la liste blanche — elle ne peut pas voir la condition de jointure. Écrire `JOIN … USING (colonne)` ou `JOIN … ON` |

Ce qui reste permis : une conversion vers un type ordinaire (`CAST(quai AS text)`, `debut::date`), une
jointure `USING`, `ORDER BY n` sur un alias de la liste SELECT, `EXISTS (…)`, les sous-requêtes et les CTE
dont les colonnes sont elles-mêmes autorisées.

Ce que garantit la résolution, et sa limite : chaque nom est rapproché de la **liste blanche**, pas du schéma
réel — l'outil ne connaît pas les colonnes cachées, et c'est voulu (il n'a pas à les citer). Tout ce que
PostgreSQL déduit lui-même du schéma réel échappe donc à l'analyse : c'est pourquoi `NATURAL JOIN` est refusé
en bloc, et pourquoi certaines requêtes inoffensives le sont aussi (un alias de sortie repris en `GROUP BY` :
écrire `GROUP BY 1`).

Tous ces contournements sont joués par `tests/pharos_data/test_cloisonnement.py::test_requete_sql_contournements_avances`
(vingt-deux requêtes, sous `jeton-iroise`) : chacune est refusée, sans qu'aucune réponse ne révèle un montant, un
tarif négocié, une table du catalogue, un rôle ou une escale, et chaque refus cite les
fonctions et conversions possibles. Les contrepreuves `test_requete_sql_conversions_de_type_autorisees` et
`test_requete_sql_requetes_legitimes` vérifient que les requêtes ordinaires passent toujours.

Une liste blanche reste une défense de l'outil : la colonne `tarif_negocie` est encore lisible par le rôle
`pharos_agent` dans la base. La masquer au niveau de la base, par les privilèges de colonne, est l'extension B
du LAB 9.
