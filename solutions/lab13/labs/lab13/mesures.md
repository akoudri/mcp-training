# LAB 13 — mesures

Consigner les valeurs relevées, **y compris si le résultat est mauvais** : le chiffre est plus utile que la correction.

## Étape 1 — Le catalogue (make lab13-catalogue)

| | Valeur |
|---|---|
| Coût fixe du catalogue, un seul serveur (LAB 10) | 476 tokens (pharos-ops, 3 outils) |
| Coût fixe du catalogue agrégé | PROVISOIRE 0 tokens |
| Nombre d'outils exposés au total | 14 |

Collision trouvée, et sa correction :

navire_par_nom exposé par pharos-data (module navires de l'équipe référentiel) et par pharos-ops. Corrigée par
préfixage côté serveur : le module est branché sur pharos-data sous le nom data_navire_par_nom.

## Étape 3 — La question cible (make lab13-question, puis make lab13-verifier-note)

| | Valeur |
|---|---|
| Appels superflus dans la trace | PROVISOIRE 0 |
| Données sans origine signalées par le vérificateur de note | PROVISOIRE 0 |

## Étape 5 — Les signaux de dérive (make lab13-derive)

| Signal | Valeur |
|---|---|
| Appels hors plan | PROVISOIRE 0 |
| Étapes annoncées jamais exécutées | PROVISOIRE 0 |
| Retours en arrière | PROVISOIRE 0 |
