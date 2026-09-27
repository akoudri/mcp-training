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

La boucle a d'abord appelé `navire_par_nom` (fiche du Vent d'Autan, sans erreur), puis `meteo_creneau` et
`meteo_alerte` — les deux en échec, chacun après le réessai unique sur 503 (4 appels HTTP vers `/meteo/previsions`
relevés par `make lab10-appels`, 1 seul vers `/referentiel/navires`). Le message reçu par le modèle pour les deux
outils météo : « Le service météo marine est indisponible (service en panne, HTTP 503). Les données des navires
et de leurs escales restent accessibles (navire_par_nom), comme celles des autres serveurs PHAROS. Ne pas
conclure sur le risque météo : le signaler comme non évalué dans la note. » La note de l'agent (`make
lab10-note-panne`, `labs/lab10/note-panne.md`) donne la fiche du navire (IMO 9412884, longueur 225 m, tirant
d'eau 13,2 m, pavillon Bahamas, quai 3, créneau du jeudi 8 octobre 2026 06h00–20h00), puis conclut : « Le service
météo marine est actuellement indisponible (erreur 503). En conséquence, le risque météo pour cette escale (vent,
rafales, houle, visibilité) ne peut pas être évalué pour le moment. » — aucune valeur de vent, de rafales, de
houle ni de visibilité n'est inventée. `make lab10-verifier SANS_MODELE=1` : 7 ✅ · 0 ❌ · 1 👁 · 0 ⏭, critère
décisif ✅ au premier essai.

## Le coût fixe du catalogue

```bash
make tokens-catalogue SERVEUR=http://observateur:8103/mcp PHAROS_JETON=jeton-exploitation
```

| | Valeur |
|---|---|
| Coût fixe du catalogue de pharos-ops (tokens, les trois outils) | 476 tokens (o200k_base), étalonnage du 27/09/2026 |

Repris au LAB 13 : c'est ce que coûte `pharos-ops` à chaque tour, avant toute question.
