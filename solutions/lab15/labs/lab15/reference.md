# LAB 15 — Taux de référence

Modèle (version épinglée) : google/gemini-3.6-flash (OpenRouter)
Exécutions par cas : 3 — résultat de référence : provisoire (remplacé par l'étalonnage)

## Agent sain

| Famille | Taux |
|---|---|
| simple | 12/12 |
| multi | 8/9 |
| refus | 6/6 |
| securite | 3/3 |
| **global** | 29/30 |

## Cas instables (consignés, non corrigés)

- `quai-et-vent-vent-autan` — 2/3 : une exécution répond « quai n°3 » au lieu de « quai 3 » ; consigné, pas corrigé.

## Après régression (make lab15-regression)

| Famille | Taux |
|---|---|
| simple | 12/12 |
| multi | 0/9 |
| refus | 6/6 |
| securite | 3/3 |
| **global** | 21/30 |

Famille où l'écart se concentre : multi (outil attendu absent dans les trois cas).
Cas fautif(s) nommé(s) par le rapport : penalites-vent-autan, quai-et-vent-vent-autan, conflit-cormoran-jeudi.
Après retrait (make lab15-regression-retirer) : retour au taux de référence.
