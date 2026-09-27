# LAB 11 — observations

## Ce que voit l'utilisateur, minute par minute (étape 4, vitesse réelle)

```bash
make lab11-scaffold                 # vitesse réelle (sans VITESSE=rapide)
make lab10-question QUESTION="Le plan de placement de jeudi est à revoir, l'escale du Vent d'Autan a été décalée."
```

| Instant | Ce qui s'affiche | Ce que l'agent dit ou fait |
|---|---|---|
| 0 s | Rien sur la question elle-même : seules les lignes de `docker compose` (création du conteneur `atelier`) | Le tour vient d'être lancé, l'agent n'a encore rien renvoyé |
| 30 s | Rien de nouveau à l'écran | Le recalcul tourne côté serveur (le vérificateur, lui, voit bien la progression avancer escale par escale) |
| 90 s | Rien de nouveau à l'écran | idem — toujours en attente du résultat de `recalculer_plan_quai` |
| fin (≈ 2 min 17 s après le lancement) | Tout apparaît d'un coup, dans l'ordre : la question, « tâche … acceptée par le serveur », puis les 23 lignes « N escales sur 24 » à la suite, la trace d'exécution (2 appels, 1 tour) et la réponse finale du modèle | L'agent restitue une réponse fondée sur le résultat réellement reçu (24 escales, 17 maintenues, 7 à décaler, identifiants et motifs exacts) |

Constat inattendu : à vitesse réelle, avec l'invocation standard (`make lab10-question`, qui passe par
`docker compose run --rm -T …`, sans pseudo-terminal), l'utilisateur ne voit **rien avancer** pendant le
calcul — ni à 30 s ni à 90 s — puis les 23 progressions et la réponse s'affichent toutes en même temps, en un
seul bloc, à la fin. Le serveur envoie bien une progression réelle escale par escale (23 messages distincts, vus
un par un par le vérificateur) et le client les affiche bien par `print()` à chaque nouveau message reçu : rien
n'indique une régression du code de la solution. L'explication la plus probable tient à la chaîne
d'exécution : sans tty (`-T`), la sortie du conteneur n'atteint le terminal qu'au moment où le processus rend
la main, malgré `PYTHONUNBUFFERED=1`. Autrement dit, le comportement « barre de progression qui avance » décrit
dans le brief se vérifie côté serveur et côté client (le code), mais pas dans ce que voit concrètement
l'utilisateur avec la commande `make` telle quelle — un écart entre le mécanisme et son affichage réel, qu'il
faudra signaler.

L'agent a-t-il, à un moment, annoncé un résultat qu'il n'avait pas reçu ?

- Non. Le modèle n'a répondu qu'après avoir reçu le résultat réel de `recalculer_plan_quai` (120 416 ms), et sa
  réponse correspond aux données effectivement renvoyées (mêmes identifiants d'escale — dont `ESC-2026-0412`
  pour le Vent d'Autan —, même bilan 17 maintenues / 7 à décaler). En revanche, comme noté ci-dessus, c'est
  l'utilisateur qui n'a rien vu défiler avant la fin, pour une raison d'affichage et non de contenu.

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
