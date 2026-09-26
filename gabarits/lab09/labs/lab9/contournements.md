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
| 1 | | |
| 2 | | |
| 3 | | |
