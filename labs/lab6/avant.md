## Mesure LAB 6 — premier appel

Modèle : google/gemini-3.6-flash · 3 exécution(s) par question

| # | Question | Attendu | Exécution 1 | Exécution 2 | Exécution 3 | Taux |
|---|---|---|---|---|---|---|
| 1 | Quelles escales sont prévues aujourd'hui ? | get_data | ✅ get_data(d=2026-10-06) | ✅ get_data(d=2026-10-06) | ✅ get_data(d=2026-10-06) | 3/3 |
| 2 | Quel est le tirant d'eau maximal du quai 3 ? | info_quai | ✅ info_quai(id=3) | ✅ info_quai(id=3) | ✅ info_quai(id=3) | 3/3 |
| 3 | Le Vent d'Autan a-t-il un créneau jeudi matin ? | search | ✅ search(q=Vent d'Autan, d=2026-10-08) | ✅ search(d=2026-10-08, q=Vent d'Autan) | ✅ search(q=Vent d'Autan, d=2026-10-08) | 3/3 |
| 4 | Quelles escales sont prévues au quai 3 demain ? | get_data_2 | ❌ get_data(d=2026-10-07) | ❌ get_data(d=2026-10-07) | ❌ get_data(d=2026-10-07) | 0/3 |
| 5 | À quelle heure le Vent d'Autan peut-il accoster jeudi ? | process | ❌ search(q=Vent d'Autan, d=2026-10-08) | ❌ search(d=2026-10-08, q=Vent d'Autan) | ❌ search(q=Vent d'Autan, d=2026-10-08) | 0/3 |

Questions réussies (majorité des exécutions) : 3/5
Tokens : 3519 en entrée, 5157 en sortie · coût : 0.0220 $

Noms : catalogue d'origine (aucun outil renommé)
