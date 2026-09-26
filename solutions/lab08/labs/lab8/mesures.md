# LAB 8 — mesures

Question de référence, posée par la boucle du LAB 4 :

> Combien de conteneurs réfrigérés sont passés quai 3 la semaine dernière ?

```bash
make lab8-question Q=reference      # la boucle du LAB 4, contre pharos-data
make lab8-verite                    # la réponse exacte, calculée contre la base
```

| | Valeur |
|---|---|
| Requête générée (outil et paramètres, relevés dans la trace) | requete_mouvements(date_debut=2026-09-28, date_fin=2026-10-04, quai=3, type_conteneur=refrigere) |
| Réponse obtenue | 16 |
| Vérité (make lab8-verite) | 16 |

Si l'écart existe : ce que la trace montrait, et ce qui a été corrigé (paramètres, dictionnaire, code).

- Premier essai, bornes passées sans fuseau : 15 (le lundi 28 avant 2 h manquait, le lundi 5 avant 2 h
  était compté). Corrigé dans le code : bornes converties depuis Europe/Paris.

## Le plafond

> Liste tous les mouvements de conteneurs du mois dernier.

Le refus obtenu (compte réel, plafond, deux façons d'affiner) :

- « 6504 mouvements correspondent : au-delà du plafond de 200 lignes, rien n'est rendu. Affiner : préciser
  un quai (1 à 7), ou réduire la période à une semaine. »
