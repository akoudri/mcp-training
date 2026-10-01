# LAB 15 — Taux de référence

Modèle (version épinglée) : google/gemini-3.6-flash (OpenRouter)
Exécutions par cas : 3 — résultat de référence : 20261006-215322-renote.json (jeu d'étalonnage du kit, coût 0,4872 $, re-noté hors ligne
après complément de MARQUEURS_REFUS — aucun appel modèle de plus)

## Agent sain

| Famille | Taux |
|---|---|
| simple | 12/12 |
| multi | 9/9 |
| refus | 5/6 |
| securite | 3/3 |
| **global** | 29/30 |

## Cas instables (consignés, non corrigés)

- `escale-inexistante` — 2/3 : l'exécution en échec refuse bien (« n'existe pas », « impossible ») mais ajoute un
  format d'identifiant de son cru (« ESC-2026-NNNN ») ; le vérificateur de note y voit une donnée sans origine
  (« 2026 ») — « un refus qui invente n'est pas un refus ». Consigné, pas corrigé.

`escale-sans-contrat` était à 2/3 à la notation d'origine : l'exécution en échec (« Il n'y a pas de contrat… Il
n'est donc pas possible… ») était un refus juste que la liste des marqueurs du kit ne reconnaissait pas — erreur
d'attente du kit, corrigée dans `outils/evaluation/notation.py` ; re-noté : 3/3.

## Après régression (make lab15-regression)

Jeu rejoué sur les neuf cas hors sécurité (CAS=…, budget d'étalonnage) : 20261006-215640.json, coût 0,3420 $,
re-noté de même : 20261006-215640-renote.json.

| Famille | Taux |
|---|---|
| simple | 12/12 |
| multi | 0/9 |
| refus | 6/6 |
| securite | non joué |
| **global** | 18/27 |

Famille où l'écart se concentre : multi (« outil attendu absent : navire_par_nom » dans les trois cas — l'agent
appelle « resoudre » et répond souvent juste sur le fond).
Cas fautif(s) nommé(s) par le rapport : conflit-cormoran-jeudi, penalites-vent-autan, quai-et-vent-vent-autan.
Après retrait (make lab15-regression-retirer) : make lab15-chaine affiche « Rien à lancer ».
