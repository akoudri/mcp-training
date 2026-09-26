# LAB 1 — Les cinq questions de test

Les poser au client (VS Code, mode PHAROS), dans l'ordre, **en repartant d'une conversation vierge
à chaque fois**. Consigner le résultat dans `resultats.md`.

| | Question | Attendu |
|---|---|---|
| 1 | Quels documents sont rattachés à l'escale ESC-2026-0412 ? | `lister_documents` |
| 2 | Quelle est la pénalité de retard au contrat de manutention du *Vent d'Autan* ? | `rechercher_clause`, sujet `penalites` |
| 3 | À quelle date expire le contrat de l'escale ESC-2026-0412 ? | `extraire_dates_contractuelles` |
| 4 | Y a-t-il une clause d'assurance dans ce contrat ? | `rechercher_clause`, sujet `assurance` |
| 5 | Quelle est la pénalité pour l'escale ESC-2026-9999 ? | **erreur métier**, et le modèle explique |

`make lab1-verifier` relève aussi, pour chaque question, le premier outil choisi par le modèle.
