# Les cas du jeu d'évaluation

Un fichier YAML par cas, ici — dix au total, quota imposé : **4** simples, **3** multi-serveurs, **2** refus,
**1** sécurité. Le format : `make lab15-exemple` (et `evaluation/exemples/`).

- Écrire chaque cas **depuis une question de l'exploitant**, pas depuis la liste des outils.
- Chaque cas porte son **contexte figé** (`make lab15-empreinte`) : date, identité, empreinte de la base.
- `make lab15-lancer CAS=id1,id2 FOIS=1` essaie quelques cas sans payer les trente exécutions.
- Un cas instable (2/3) se **consigne** dans `labs/lab15/reference.md` ; il ne se corrige pas.
