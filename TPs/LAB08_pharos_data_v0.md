# LAB 8 — `pharos-data` v0

**Module DA1** · durée 1 h
**Artefact produit** : **A8** — `pharos-data v0` : schéma en ressource, requête contrainte
**Checkpoint de sortie** : `etat/da1-fin`

---

## Contexte

Deuxième serveur du fil rouge. `pharos-docs` exposait un corpus documentaire ; `pharos-data` expose
la base d'exploitation du port — escales, navires, quais, et mouvements de conteneurs.

Le changement n'est pas seulement technique. Un document mal lu produit une réponse visiblement
bancale. Une requête mal écrite produit un **nombre**, et un nombre faux a exactement la même
allure qu'un nombre juste.

C'est pourquoi ce lab a une réponse de référence vérifiable, et pourquoi le critère décisif porte
sur la lisibilité de la requête générée plutôt que sur la plausibilité de la réponse.

**Répartition indicative du temps** : 20 min pour le pool et les deux outils · 15 min pour le
schéma en ressource · 15 min pour la question de référence · 10 min pour le plafond.

---

## Prérequis

| | |
|---|---|
| **Modules** | DA1 (blocs 13.1 à 13.4), SR2 (ressources), TQ1 |
| **Labs** | LAB 4, LAB 7 |
| **Artefacts consommés** | **A4** — `pharos-client` |
| **Fourni** | base PostgreSQL peuplée, DSN, squelette, question de référence et sa vérité |

```bash
make depart LAB=8         # branche binome-<B>-lab08 depuis etat/tq1-fin, et le squelette de pharos-data
make lab8-base            # PostgreSQL PHAROS, peuplé (127.0.0.1:5433)
make lab8-up              # pharos-data (http://localhost:8102/mcp)
```

### La base

| Table | Contenu |
|---|---|
| `escales` | `escale_id`, `navire_id`, `quai`, `debut`, `fin`, `statut`, `tirant_eau_m` |
| `navires` | `navire_id`, `nom`, `longueur_m`, `tirant_eau_max_m`, `pavillon` |
| `quais` | `quai`, `longueur_m`, `tirant_eau_max_m`, `equipements` |
| `mouvements` | `mouvement_id`, `escale_id`, `conteneur_id`, `sens`, `horodatage`, `type_conteneur` |
| `esc_hdr_legacy` | **Table technique.** Doublons de reprise de 2019. Ne doit pas être exposée. |

Deux points à repérer avant de coder, ils décident du résultat :

- `debut`, `fin` et `horodatage` sont en fuseau **Europe/Paris** ;
- `type_conteneur` et `sens` sont des colonnes catégorielles, à valeurs **sans accent**.

---

## SOCLE — pour tous

### Étape 1 — Le pool, puis deux outils

Créer le pool **au démarrage du processus**, une fois, et l'emprunter à chaque appel.

Exposer un premier outil, en requête paramétrée — pas en SQL libre :

```
requete_mouvements(date_debut, date_fin, quai=None, type_conteneur=None, sens=None)
```

Dates en heure de Paris (Europe/Paris), `date_fin` **incluse** : la signature et la description sont
imposées par le squelette.

Le SQL est écrit par vous. Le modèle ne fournit que les paramètres.

Exposer un second outil paramétré :

```
escales_du_jour(date, quai=None)
```

Il renvoie, pour chaque escale : `escale_id`, nom du navire, quai, créneau, statut. C'est cet outil
qui permettra plus tard de relier un nom de navire à son escale (LAB 9, LAB 10 extension C, LAB 13,
évaluation) : `requete_mouvements` répond en colonnes, `escales_du_jour` répond en escales.

### Étape 2 — Le schéma en ressource

Exposer `pharos://schema/…` selon le bloc 13.3. Trois exigences :

- les **unités** et le **fuseau horaire** figurent dans le dictionnaire de colonnes ;
- les relations utiles sont indiquées — celles qu'une question réelle traverse ;
- `esc_hdr_legacy` **n'apparaît pas**, et le dictionnaire dit explicitement qu'il n'existe pas
  d'autre source de mouvements.

Une ressource, pas un outil : l'application sait, sans le modèle, que ce contenu est pertinent.

### Étape 3 — La question de référence

Poser, via la boucle du LAB 4 (`make lab8-question Q=reference`) :

> Combien de conteneurs réfrigérés sont passés quai 3 la semaine dernière ?

Puis vérifier :

```bash
make lab8-verite          # la réponse exacte, calculée contre la base, et la définition de la période
```

Si l'écart existe, **regarder la requête générée dans la trace avant de toucher au code**. Le
diagnostic est presque toujours dans les paramètres, pas dans le SQL.

### Étape 4 — Le plafond et le refus

Poser un plafond de deux cents lignes. Au-delà, refuser selon le bloc 13.4 : le compte réel, le
plafond, et deux façons d'affiner.

Vérifier sur :

> Liste tous les mouvements de conteneurs du mois dernier.

### Critères de réussite

- [ ] Le pool est créé au démarrage du processus, jamais par appel.
- [ ] Le schéma est exposé en ressource, avec unités et fuseau horaire.
- [ ] `esc_hdr_legacy` n'apparaît nulle part dans ce qui est exposé.
- [ ] La réponse à la question de référence est **exacte**, vérifiée par `make lab8-verite`.
- [ ] Un résultat au-delà du plafond produit un refus portant le compte, le plafond et deux façons
      d'affiner.
- [ ] **Critère décisif** — la requête réellement exécutée est lisible dans la trace du LAB 4, sans
      avoir à ouvrir la base ni le code du serveur.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Mesurer l'effet des valeurs possibles

Sur une **autre** colonne catégorielle que celle déjà traitée : `sens`.

Question de mesure :

> Combien de conteneurs ont été débarqués quai 5 hier ?

Protocole du LAB 6 : trois exécutions avant d'ajouter les valeurs possibles de `sens` au
dictionnaire, trois après (`make lab8-banc`). Consigner les deux taux, et les arguments générés dans
chaque cas.

C'est souvent le plus gros écart de la journée, pour l'ajout le moins coûteux.

### B — L'agrégation par défaut

Ajouter `mouvements_agreges(quai, periode, granularite)`, puis vérifier que le refus de l'étape 4 le
**nomme**, et que l'agent l'utilise spontanément au tour suivant.

C'est la mise à l'épreuve directe du « un refus est un prompt » du bloc 13.4.

### C — Porter la suite de tests

Écrire pour `pharos-data` l'équivalent de la suite du LAB 7 : schémas, refus au plafond, ressource
de schéma présente et bien dimensionnée.

Même seuil : moins de dix secondes, sans modèle (`make lab8-tests CHRONO=1`). Le cloisonnement viendra s'y ajouter au LAB 9.

---

## Pièges & indices

**Une connexion par appel fonctionne, et s'effondre à la charge.** C'est la faute qui ne se voit
jamais en salle : à un seul utilisateur, ouvrir et fermer une connexion à chaque appel donne un
serveur parfaitement fonctionnel. Le pool se met en place maintenant, pendant qu'il est gratuit.

**Le fuseau horaire est le piège principal de ce lab.** « La semaine dernière » calculée en UTC
décale les bornes de deux heures, et donne un résultat faux, plausible, et impossible à distinguer
du bon sans vérification. C'est précisément pour cela que `make lab8-verite` existe. Vérifier aussi
que la consigne système donne la date et le fuseau : sinon le modèle choisit la sienne.

**La base dit `refrigere`, le modèle écrira `réfrigéré`.** Ou `reefer`. Ou `REFRIGERE`. La requête
sera syntaxiquement correcte et renverra zéro ligne — que le modèle interprétera comme « il n'y en a
pas ». Le remède est dans le dictionnaire, pas dans le code.

**Ne pas exposer `esc_hdr_legacy`.** Elle ressemble à une table de mouvements, elle contient des
doublons de 2019, et si elle est visible le modèle y fera des jointures. Le dictionnaire doit dire
qu'il n'existe pas d'autre source, sinon le modèle en cherchera une.

**Compter avant de rapatrier.** Le plafond se vérifie par un `COUNT` séparé, pas en tronquant après
avoir tout ramené. Sinon le serveur paie le coût complet de la requête pour finir par la refuser.

**Ne pas renvoyer l'erreur SQL brute.** Ce n'est pas encore le sujet — le cloisonnement et les
fuites de schéma sont traités au module DA3 — mais prendre l'habitude maintenant coûte une ligne.

**Ne pas écrire de SQL libre « juste pour le lab ».** L'outil paramétré demande dix minutes de plus
et permet tout le reste : les tests sans modèle, le plafond, et le cloisonnement de demain.

**Ne pas se contenter du plausible.** La réponse de référence a une valeur unique et vérifiable. Un
nombre qui « a l'air correct » n'est pas un critère de réussite — c'est même exactement le problème
que ce lab existe pour rendre visible.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_data/` — pool, deux outils paramétrés, ressource de schéma, plafond |
| **Consigné** | `labs/lab8/mesures.md` — la requête générée, la réponse obtenue, la vérité |
| **Artefact du fil rouge** | **A8**, consommé par DA3 |
| **Checkpoint** | `etat/da1-fin` |

```bash
make lab8-verifier
git add serveurs/pharos_data/ labs/lab8/ && git commit -m "LAB 8 — pharos-data v0"
```

**Suite.** Le module **DA2** prend la question par l'autre bout. `requete_mouvements` répond à des
questions formulées en colonnes. L'exploitant, lui, demande si une escale est « à risque » — un
concept qui n'existe dans aucune table.

C'est l'écart déjà rencontré au LAB 1 avec le nom du navire, et cette fois on le comble pour de bon.
