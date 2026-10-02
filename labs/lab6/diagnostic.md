# LAB 6 — Diagnostic de la mesure initiale

Une ligne par question ratée dans `avant.md`. L'anti-patron est l'un des six du bloc 10.6 :
texte libre en entrée · identifiant que le modèle ne peut pas connaître · erreur qui ne dit rien ·
deux descriptions interchangeables · description qui décrit l'implémentation · outil qui renvoie un
document entier.

| Question | Ce que le modèle a choisi | Anti-patron | Pourquoi ce choix était défendable |
|---|---|---|---|
| 4 — escales au quai 3 demain | `get_data(d=2026-10-07)`, 3 fois sur 3 | Description qui décrit l'implémentation (`get_data` : « l'index construit au démarrage ») ; et, pour `get_data_2`, « variante … avec filtrage » ne dit pas **sur quoi** on filtre | `get_data` est le seul outil qui promet « les données » à partir d'une seule date ; `f` n'est pas reconnaissable comme un quai. Lister la journée puis filtrer soi-même est une stratégie raisonnable. |
| 5 — heure d'accostage du Vent d'Autan jeudi | `search(q=Vent d'Autan, d=2026-10-08)`, 3 fois sur 3 | Deux descriptions interchangeables (« Recherche. » / « Traite un élément. ») : rien ne dit que `process` calcule une heure d'accostage | `search` est le seul outil dont le nom promet un résultat à partir d'un nom de navire et d'une date ; « Traite un élément » ne dit ni quel élément ni pour obtenir quoi. |
