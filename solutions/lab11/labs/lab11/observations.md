# LAB 11 — observations

## Ce que voit l'utilisateur, minute par minute (étape 4, vitesse réelle)

```bash
make lab11-scaffold                 # vitesse réelle (sans VITESSE=rapide)
make lab10-question QUESTION="Le plan de placement de jeudi est à revoir, l'escale du Vent d'Autan a été décalée."
```

| Instant | Ce qui s'affiche | Ce que l'agent dit ou fait |
|---|---|---|
| 0 s | La création du conteneur `atelier`, puis la question, puis « tâche … acceptée par le serveur » dès que le modèle a demandé le recalcul | Le modèle a demandé `recalculer_plan_quai` pour toute la journée ; le serveur en a fait une tâche |
| 30 s | Quatre ou cinq lignes « N escales sur 24 », une nouvelle toutes les 5 s environ | Le recalcul tourne côté serveur ; la boucle interroge toutes les 2 s et n'affiche que ce qui a changé |
| 90 s | Une quinzaine de lignes « N escales sur 24 » | idem — le modèle n'a encore rien reçu, et ne dit rien |
| fin (≈ 2 min 17 s après le lancement) | « 23 escales sur 24 », puis la trace (2 appels, dont `recalculer_plan_quai` · 120 416 ms) et la réponse | L'agent restitue une réponse fondée sur le résultat réellement reçu (24 escales, 17 maintenues, 7 à décaler, identifiants et motifs exacts) |

Les progressions arrivent au terminal au fil de l'eau : `make lab10-question` passe par
`docker compose run -T` sans pseudo-terminal, mais `PYTHONUNBUFFERED=1` (image) suffit, vérifié avec un tube
horodaté et avec un pseudo-terminal. Piège d'observation : un outil qui capture la sortie de `make` pour la
résumer (un proxy de commandes, une CI qui n'affiche le journal qu'à la fin) montre tout d'un bloc à la fin ;
ce n'est ni le serveur ni la boucle.

L'agent a-t-il, à un moment, annoncé un résultat qu'il n'avait pas reçu ?

- Non. Le modèle n'a répondu qu'après avoir reçu le résultat réel de `recalculer_plan_quai` (120 416 ms), et sa
  réponse correspond aux données effectivement renvoyées (mêmes identifiants d'escale — dont `ESC-2026-0412`
  pour le Vent d'Autan —, même bilan 17 maintenues / 7 à décaler). Pendant les deux minutes de calcul, il n'a
  rien dit : seules les progressions du serveur ont défilé.

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
