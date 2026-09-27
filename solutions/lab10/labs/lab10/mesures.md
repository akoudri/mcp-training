# LAB 10 — mesures

## Le message de panne retenu (étape 2)

```bash
make lab10-mocks PANNE=meteo
make lab10-question                 # « L'escale du Vent d'Autan de jeudi présente-t-elle un risque ? »
```

Le message rendu par `pharos-ops` quand la météo est tombée — ses trois parties (bloc 17.3) :

| Partie | Texte |
|---|---|
| Ce qui est tombé | « Le service météo marine est indisponible (service en panne, HTTP 503). » |
| Ce qui reste accessible | « Les données des navires et de leurs escales restent accessibles (navire_par_nom), comme celles des autres serveurs PHAROS. » |
| Ce qu'il ne faut pas conclure | « Ne pas conclure sur le risque météo : le signaler comme non évalué dans la note. » |

## Le comportement de l'agent

Ce que la boucle a fait du message (appels, réessais, note finale). Critère décisif : `make lab10-note-panne`,
qui écrit `labs/lab10/note-panne.md`.

- À RELEVER à l'étalonnage : les appels de la trace, le message reçu, ce que dit la note.

## Le coût fixe du catalogue

```bash
make tokens-catalogue SERVEUR=http://observateur:8103/mcp PHAROS_JETON=jeton-exploitation
```

| | Valeur |
|---|---|
| Coût fixe du catalogue de pharos-ops (tokens, les trois outils) | À RELEVER à l'étalonnage (make tokens-catalogue) |

Repris au LAB 13 : c'est ce que coûte `pharos-ops` à chaque tour, avant toute question.
