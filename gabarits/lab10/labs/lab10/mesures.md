# LAB 10 — mesures

## Le message de panne retenu (étape 2)

```bash
make lab10-mocks PANNE=meteo
make lab10-question                 # « L'escale du Vent d'Autan de jeudi présente-t-elle un risque ? »
```

Le message rendu par `pharos-ops` quand la météo est tombée — ses trois parties (bloc 17.3) :

| Partie | Texte |
|---|---|
| Ce qui est tombé | |
| Ce qui reste accessible | |
| Ce qu'il ne faut pas conclure | |

## Le comportement de l'agent

Ce que la boucle a fait du message (appels, réessais, note finale). Critère décisif : `make lab10-note-panne`,
qui écrit `labs/lab10/note-panne.md`.

-

## Le coût fixe du catalogue

```bash
make tokens-catalogue SERVEUR=http://observateur:8103/mcp PHAROS_JETON=jeton-exploitation
```

| | Valeur |
|---|---|
| Coût fixe du catalogue de pharos-ops (tokens, les trois outils) | |

Repris au LAB 13 : c'est ce que coûte `pharos-ops` à chaque tour, avant toute question.
