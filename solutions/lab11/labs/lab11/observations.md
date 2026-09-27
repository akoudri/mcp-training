# LAB 11 — observations

## Ce que voit l'utilisateur, minute par minute (étape 4, vitesse réelle)

```bash
make lab11-scaffold                 # vitesse réelle (sans VITESSE=rapide)
make lab10-question QUESTION="Le plan de placement de jeudi est à revoir, l'escale du Vent d'Autan a été décalée."
```

| Instant | Ce qui s'affiche | Ce que l'agent dit ou fait |
|---|---|---|
| 0 s | À RELEVER à l'étalonnage | |
| 30 s | | |
| 90 s | | |
| fin | | |

L'agent a-t-il, à un moment, annoncé un résultat qu'il n'avait pas reçu ?

- À RELEVER à l'étalonnage.

## L'intervalle d'interrogation retenu

Valeur, et pourquoi (trop court : charge inutile ; trop long : l'utilisateur croit que c'est bloqué) :

- 2 s. Le moteur traite une escale toutes les 5 s à vitesse réelle : à 2 s, chaque escale traitée est vue, et
  une interrogation de `tasks/get` coûte moins d'une milliseconde au serveur. Au-delà de 5 s, deux escales
  passent entre deux affichages et la barre semble sauter ; en dessous d'une seconde, on interroge pour rien.

## Le plan B (étape 3)

```bash
make lab11-clients SANS_TASKS=1
```

Le refus obtenu (ce qui n'est pas possible, ce qui l'est) :

- « Recalcul de la journée entière impossible avec ce client : il dure deux minutes environ et exige un client
  qui suit les tâches (extension Tasks), que celui-ci ne déclare pas. Possible : recalculer quai par quai
  (quai=1 à 7), quelques secondes chacun, puis assembler les résultats. »
