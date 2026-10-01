# LAB 10 — `pharos-ops` v0

**Modules IS1 et IS2** · durée 1 h
**Artefact produit** : **A10** — `pharos-ops v0` : deux API enveloppées, secrets, quotas, mode dégradé
**Checkpoint de sortie** : `etat/is2-fin`

---

## Contexte

Troisième et dernier serveur du fil rouge. `pharos-docs` et `pharos-data` interrogeaient des choses
qui vous appartiennent. `pharos-ops` dépend de deux services extérieurs : la météo marine et un
référentiel de navires.

Les deux sont fournis sous forme de mocks locaux, **avec leurs défauts**. La météo est lente,
tombe, et impose un quota. Le référentiel est stable et rapide, mais sa documentation ment : des
champs annoncés obligatoires manquent, et des champs numériques valent parfois `null`, parfois
`0`.

C'est délibéré. Une API tierce se découvre en l'appelant, pas en lisant sa spécification.

**Répartition indicative du temps** : 20 min pour les trois outils · 15 min pour le mode panne ·
10 min pour le plafond · 15 min pour la réponse partielle et la mise en commun.

---

## Prérequis

| | |
|---|---|
| **Modules** | IS1 (16.1 à 16.4), IS2 (17.1 à 17.4) |
| **Labs** | LAB 4 |
| **Artefacts consommés** | **A4** — `pharos-client` |
| **Fourni** | deux mocks avec interrupteurs, clé factice, compteur d'appels côté mock, squelette |

```bash
make depart LAB=10        # branche binome-<B>-lab10 depuis etat/da3-fin, et le squelette de pharos-ops
make lab10-mocks          # météo marine + référentiel navires
make lab10-up             # pharos-ops (http://localhost:8103/mcp)
```

### Les interrupteurs des mocks

```bash
make lab10-mocks PANNE=meteo       # la météo renvoie 503
make lab10-mocks LENTEUR=8s        # la météo répond en huit secondes, sur les quais 5 et 7 (LENTEUR_QUAIS=…)
make lab10-mocks QUOTA=5           # cinq appels par fenêtre, puis 429
make lab10-appels                  # combien d'appels le mock a réellement reçus
```

---

## SOCLE — pour tous

### Étape 1 — Trois outils, pas quarante

| Outil | Rôle |
|---|---|
| `meteo_creneau(quais, debut, fin)` | Conditions sur un créneau d'accostage, pour un ou plusieurs quais |
| `meteo_alerte(quai, horizon_h)` | Y a-t-il un risque à venir, et lequel |
| `navire_par_nom(nom)` | Identifiant, caractéristiques, tirant d'eau maximal, escales connues |

Trois exigences, reprises du bloc 16.1 :

- **aucun outil ne prend de coordonnées** — le quai suffit, le serveur connaît sa position ;
- aucun ne prend de fuseau ni d'unité — ce sont des décisions d'exploitation ;
- la clé d'API est lue depuis l'environnement, et n'apparaît nulle part ailleurs.

Normaliser en sortie : unités dans le nom des champs (`vent_kt`, `houle_m`), dates ISO 8601 avec
fuseau, et **une règle unique pour les absences**, appliquée aux deux API.

### Étape 2 — Le mode panne

```bash
make lab10-mocks PANNE=meteo
```

Poser, via la boucle du LAB 4 (`make lab10-question`) :

> L'escale du *Vent d'Autan* de jeudi présente-t-elle un risque ?

Écrire le message d'erreur selon le bloc 17.3, en trois parties : ce qui est tombé, ce qui reste
accessible, et **ce qu'il ne faut pas conclure**.

Vérifier ensuite le comportement de l'agent, pas seulement celui du serveur.

### Étape 3 — Le plafond

Poser un plafond par outil. Le refus doit être une erreur métier qui **indique comment consommer
moins** — pas un code 429 relayé tel quel.

```bash
make lab10-mocks QUOTA=5
```

### Étape 4 — La réponse partielle

Sur `meteo_creneau`, avec cinq quais demandés (1, 3, 4, 5, 7) et le mock en mode lenteur, deux
échoueront : les quais 5 et 7.

Renvoyer les trois résultats (`resultats`), la liste des deux manquants avec leur raison
(`incomplets`), et le champ `complet`.

### Critères de réussite

- [ ] Trois outils au plus, et aucun paramètre que le modèle devrait deviner.
- [ ] La clé n'apparaît ni en argument, ni en résultat, ni dans un message d'erreur, ni dans la
      trace du LAB 4.
- [ ] Unités dans les noms de champs, dates avec fuseau, absences traitées de façon uniforme sur
      les deux API.
- [ ] Le plafond produit un refus qui indique comment consommer moins.
- [ ] La réponse partielle porte `complet: false` et la raison de chaque manquant.
- [ ] **Critère décisif** — en mode panne, la note produite par l'agent signale la météo comme
      **non évaluée**, et ne contient aucune donnée météo inventée (`make lab10-note-panne` : le vrai
      modèle, une fois, écrit `labs/lab10/note-panne.md`).

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Le mode lenteur

```bash
make lab10-mocks LENTEUR=8s
```

Ajuster le timeout pour que l'agent dégrade au lieu d'attendre. Attention : le timeout de l'outil
doit rester **inférieur** au budget de tour de la boucle (`PHAROS_DELAI_S`, 20 s), sinon c'est la
boucle qui coupe — et le message soigneusement écrit à l'étape 2 n'est jamais lu.

### B — Mesurer la multiplication

```bash
make lab10-appels
```

Poser une question, puis compter les appels réellement reçus par le mock. Comparer au nombre
d'appels visibles dans la trace du LAB 4.

L'écart est le produit de vos réessais par ceux du modèle — le piège du bloc 17.3. Le chiffre
surprend généralement.

### C — Rendre à la question 2 du LAB 1 sa réponse

Brancher `pharos-ops` **et** `pharos-docs` sur la même boucle, puis reposer la question restée sans
réponse depuis le premier jour :

> Quelle est la pénalité de retard prévue au contrat de manutention du *Vent d'Autan* ?

`escales_du_jour` retrouve l'escale du *Vent d'Autan*, `rechercher_clause` fait le reste ;
`navire_par_nom` sert au tirant d'eau. Observer si l'agent enchaîne de lui-même — et, s'il n'y
arrive pas, noter pourquoi.

*C'est un avant-goût du module OR3 : deux serveurs, un catalogue, et un enchaînement à faire tenir.*

---

## Pièges & indices

**Le mock ment exactement comme la vraie API.** `longueur_m` est tantôt absent, tantôt `null`,
tantôt `0`. Les trois cas doivent être traités, et le troisième est le plus dangereux : un zéro
passe tous les contrôles de présence et fausse silencieusement tout calcul de tirant d'eau.

**La clé se cache dans l'URL de l'erreur.** C'est le piège classique et il est tendu ici : lorsque
le mock renvoie 503, la bibliothèque HTTP inclut l'URL complète dans le message d'exception — avec
la clé en paramètre de requête. Le vérifier explicitement dans la trace, pas seulement dans le code.

**Le timeout de l'outil doit être plus court que le budget de tour.** Sinon la boucle coupe avant
le serveur, le message d'erreur soigné n'est jamais produit, et l'agent conclut sur rien.

**Tester le mode panne par la boucle, pas par un appel direct.** Un appel direct montre que le
serveur renvoie le bon message. Seule la boucle montre ce que l'agent en fait — et c'est le seul
critère qui compte.

**Ne pas réessayer sur un 429.** Le réessai prolonge souvent la fenêtre de blocage. Trois familles,
trois conduites, bloc 17.3.

**Trois outils, pas cinq.** La tentation est d'ajouter un outil par variable météo — vent, houle,
visibilité. C'est le point d'entrée déguisé du bloc 16.1, et il fera chuter le taux de bon choix
mesuré au LAB 6.

**Si vous mettez un cache, ne le partagez pas entre appelants.** Un cache commun annule le
cloisonnement du LAB 9 en une ligne, et le test automatisé ne le verra pas — il porte sur la base,
pas sur votre cache.

**Ne pas coder la météo en dur pour compléter `escales_a_risque`.** `pharos-data` ne l'évalue pas
et le dit explicitement (`criteres_non_evalues`) ; c'est l'agent, au LAB 13, qui combine ce critère
avec `meteo_creneau`, avec les trois serveurs assemblés — `pharos-ops` n'appelle jamais directement
`pharos-data`.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_ops/` — trois outils, secrets, plafond, mode dégradé |
| **Consigné** | `labs/lab10/mesures.md` — le message de panne retenu, le comportement observé de l'agent, et le coût fixe du catalogue de `pharos-ops` |
| **Artefact du fil rouge** | **A10**, consommé par IS3, SR3 et OR3 |
| **Checkpoint** | `etat/is2-fin` |

```bash
make lab10-verifier
git add serveurs/pharos_ops/ labs/lab10/ && git commit -m "LAB 10 — pharos-ops v0"
```

**Mise en commun (5 min).** Chaque binôme lit à voix haute son message de panne. La salle jugera sur
un seul critère : contient-il les trois parties ? Celui à qui il manque « ce qu'il ne faut pas
conclure » verra son agent inventer une météo, et ce sera visible dans sa note.

**Suite.** Le module **IS3** traite le cas que ce lab a évité : un appel qui dure trois minutes. Le
recalcul d'un plan de placement à quai ne tient pas dans une requête, et la révision 2026-07-28 a
une extension pour cela — avec un statut qu'il faudra regarder de près avant d'en dépendre.
