# LAB 12 — mesures

## Étape 1 — l'action irréversible, sans garde-fou

`publier_alerte(escale_id, niveau, destinataire="exploitation", note="")` publie directement. Trois
conversations vierges, la même question, le compteur remis à zéro avant chacune :

```bash
make lab12-canal                    # remet le canal à zéro
make lab10-question QUESTION="L'escale du Vent d'Autan de jeudi est à risque. Préviens l'exploitant."
make lab12-compteur                 # alertes réellement parties, par destinataire
```

| | Valeur |
|---|---|
| Alertes parties à l'étape 1 (trois conversations, par exemple « 2, 1, 3 ») | |

Consigner le chiffre AVANT toute correction : c'est l'état des lieux.

## Le repli (étape 4)

```bash
make lab12-clients SANS_ELICITATION=1
```

Le refus obtenu, et ce qu'il propose à la place :

-

## Les deux instances (étape 5)

Ce qui a changé côté serveur pour que le rejeu passe d'une instance à l'autre, et ce qu'affiche le refus d'un
`requestState` altéré au milieu de la chaîne :

-
