# LAB 6 — Réécriture de catalogue

**Module SR1** · durée 1 h
**Artefact produit** : **A6** — un catalogue réécrit, et une mesure avant / après
**Checkpoint de sortie** : `etat/sr1-fin`

---

## Contexte

Un quatrième serveur est fourni : `pharos-quai`. Il gère les quais, les créneaux et les
accostages. Il fonctionne parfaitement — son code est correct, ses schémas valides, ses erreurs
propres.

Son catalogue, en revanche, a été écrit par quelqu'un qui n'avait jamais lu le module SR1.

**Le livrable de ce lab n'est pas un catalogue. C'est un chiffre**, avant et après. Le catalogue
réécrit n'est que le moyen de faire bouger ce chiffre.

**Pourquoi un serveur fourni plutôt que le vôtre.** Deux raisons. Mesurer sur son propre code
appelle la justification plutôt que le constat. Et le catalogue doit être identiquement mauvais pour
tous, sinon les chiffres de la salle ne se comparent pas.

**Répartition indicative du temps** : 12 min de mesure initiale · 8 min de diagnostic écrit ·
25 min de réécriture · 10 min de mesure finale · 5 min d'attribution.

---

## Prérequis

| | |
|---|---|
| **Modules** | SR1 (blocs 10.1 à 10.6) |
| **Labs** | le banc du premier appel fourni (le même protocole que le bloc 10.2) |
| **Artefacts consommés** | aucun : le banc de mesure est fourni |
| **Fourni** | `pharos-quai` et son catalogue dégradé, la table de vérité, les cinq questions, le script de mesure |

```bash
make depart LAB=6         # branche binome-<B>-lab06 depuis etat/or2-fin, table de vérité et grilles
make lab6-quai            # démarre pharos-quai
```

### Le catalogue fourni

| Nom | Description fournie |
|---|---|
| `get_data` | « Récupère les données depuis la base en utilisant l'index construit au démarrage. » |
| `get_data_2` | « Variante de get_data avec filtrage. » |
| `process` | « Traite un élément. » |
| `info_quai` | « Informations. » |
| `search` | « Recherche. » |
| `check` | « Vérifie la disponibilité. » |

`labs/lab6/verite.md` donne ce que chaque outil **fait réellement**. Le lire : sans cela, la
réécriture est impossible, et ce n'est pas un exercice de devinette.

Les paramètres (`d`, `f`, `x`, `id`, `q`, `h`) font partie des schémas : on ne les renomme pas.
`verite.md` dit ce que chacun contient ; la description est l'endroit où le dire. Le script de mesure
retrouve chaque outil par son schéma : renommer un outil ne fausse pas la mesure, changer un schéma
l'arrête.

### Les cinq questions

| | Question | Outil attendu au premier appel |
|---|---|---|
| 1 | Quelles escales sont prévues aujourd'hui ? | `get_data` |
| 2 | Quel est le tirant d'eau maximal du quai 3 ? | `info_quai` |
| 3 | Le *Vent d'Autan* a-t-il un créneau jeudi matin ? | `search` |
| 4 | Quelles escales sont prévues au quai 3 demain ? | `get_data_2` |
| 5 | À quelle heure le *Vent d'Autan* peut-il accoster jeudi ? | `process` |

---

## SOCLE — pour tous

### Étape 1 — La mesure initiale

```bash
make lab6-mesurer SORTIE=labs/lab6/avant.md
```

Cinq questions, trois exécutions chacune, quinze exécutions au total. Le script relève **le premier
appel d'outil** de chaque exécution et le compare à l'attendu.

Consigner le tableau tel quel, avec le modèle utilisé et sa version épinglée : un taux ne se compare
qu'entre binômes qui ont mesuré avec le même modèle. Ne rien corriger encore.

### Étape 2 — Le diagnostic, par écrit

Pour chaque question ratée, nommer l'anti-patron responsable, parmi les six du bloc 10.6. Écrire
dans `labs/lab6/diagnostic.md` :

| Question | Ce que le modèle a choisi | Anti-patron | Pourquoi ce choix était défendable |
|---|---|---|---|

La dernière colonne est la plus utile : elle oblige à raisonner depuis ce que le modèle voyait, et
non depuis ce que vous savez.

### Étape 3 — La réécriture

Réécrire **les noms et les descriptions**, selon les cinq éléments du bloc 10.2.

**Contrainte du socle** : ne pas toucher aux schémas, et ne pas changer le nombre d'outils. Six
outils avant, six après. Sans cela, la seconde mesure ne compare plus la même chose — et le lab perd
son unique livrable.

### Étape 4 — La mesure finale

```bash
make lab6-mesurer SORTIE=labs/lab6/apres.md
```

Mêmes questions, même protocole, même nombre d'exécutions. Reconsigner le modèle et sa version dans
`apres.md`, à côté du chiffre.

### Étape 5 — L'attribution

Dans `labs/lab6/attribution.md`, une ligne par gain :

> « +1 sur la question 4, grâce à la mention *« filtre par quai »* ajoutée dans la description de
> `get_data_2`. »

Un gain que l'on ne sait pas attribuer n'est pas un résultat : c'est du bruit.

### Critères de réussite

- [ ] `avant.md` est consigné : cinq questions, trois exécutions chacune.
- [ ] Chaque échec initial est rattaché à un anti-patron nommé du bloc 10.6.
- [ ] La réécriture ne touche ni les schémas ni le nombre d'outils.
- [ ] `apres.md` est consigné, selon le même protocole.
- [ ] **Critère décisif** — le taux progresse d'au moins deux questions sur cinq, **et** chaque gain
      est attribué à une modification précise et nommée.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Fusionner, ou scinder

`get_data` et `get_data_2` sont-ils deux outils, ou un seul avec un paramètre facultatif ? Trancher,
mesurer à nouveau, puis **défendre le choix devant un autre binôme**.

La mesure du socle refuse un catalogue fusionné : mesurer avec `make lab6-banc
QUESTIONS=labs/lab6/questions.yaml`, sur une copie de `outils/questions/lab6.yaml` où `attendu` porte
les noms actuels.

La règle du débat : celui qui écoute doit pouvoir contester la **mesure**, pas seulement l'avis. Si
la contestation ne porte que sur le goût, c'est que la mesure manque.

### B — La sixième question, celle sans réponse

Ajouter :

> Quelle est la météo prévue jeudi sur le quai 3 ?

Aucun outil de `pharos-quai` ne peut y répondre. Mesurer combien d'exécutions sur trois choisissent
malgré tout un outil au hasard.

Mesurer avec `make lab6-banc QUESTIONS=…`, la question météo avec `attendu: aucun` : une exécution
sans appel d'outil compte comme réussie.

**Un bon catalogue rend le refus possible.** Si le modèle appelle `check` sur une question météo,
c'est que les descriptions ne délimitent pas leur périmètre — c'est l'élément « ce qu'il ne fait
pas » du bloc 10.2 qui manque.

### C — Le report sur votre propre serveur

Appliquer les enseignements à `pharos-docs`, puis remesurer avec les cinq questions du LAB 1.

Comparer au nombre d'appels relevé à la question 1 du LAB 4 — celui que vous aviez pour consigne de
ne pas corriger. C'est aujourd'hui qu'on le corrige, et qu'on sait de combien.

---

## Pièges & indices

**Mesurer une seule fois ne mesure rien.** Le modèle n'est pas déterministe : deux exécutions de la
même question donnent parfois deux outils différents. Trois exécutions est un minimum, et l'écart
entre les trois est lui-même une information — un outil choisi deux fois sur trois n'est pas un
outil bien nommé.

**Toucher aux schémas invalide le lab.** C'est l'erreur qui coûte le plus cher, parce qu'elle ne se
voit pas : la mesure finale sera meilleure, et on ne saura pas si c'est grâce aux descriptions ou
aux schémas. Les schémas se travaillent, mais pas dans la même passe.

**Réécrire les six d'un coup empêche l'attribution.** Si le temps le permet, réécrire deux outils,
mesurer, puis les quatre autres. Sinon, grouper — mais noter précisément quelles modifications sont
regroupées, pour ne pas attribuer un gain à la mauvaise cause.

**Ne pas ajouter d'outil pour sauver une question.** Interdit au socle. Une question ratée qui reste
ratée après réécriture est une information : elle dit que le problème n'est pas dans le catalogue,
et le bloc 10.4 dit souvent où il est.

**Un nom long n'est pas un bon nom.**
`lister_les_escales_prevues_pour_une_date_donnee` coûte des tokens à chaque tour et n'aide pas plus
que `escales_du_jour`. La précision se met dans la description, la lisibilité dans le nom.

**Le « quand l'appeler » est presque toujours le plus gros gain.** C'est l'élément le plus souvent
absent des descriptions d'origine, et celui dont l'ajout déplace le plus le chiffre. Si vous devez
choisir une seule chose à ajouter, c'est celle-là.

**« Aujourd'hui » et « demain » ne se résolvent que si la date est fournie.** Les questions 1 et 4
ne trouvent le bon outil que si l'hôte injecte la date courante et le fuseau dans la consigne
système. Sans cela, aucune réécriture de catalogue ne les corrigera.

**La question 3 demande deux appels.** `search` puis `check`. On ne mesure que le premier : c'est le
protocole du bloc 10.2, et la raison en est que le second est déjà influencé par le résultat du
premier.

**Ne pas juger la réponse finale.** Elle peut être correcte avec un mauvais premier appel, et
fausse avec le bon. Ce lab mesure la sélection, pas la réponse. La réponse est l'affaire du module
EX2.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_quai/` — catalogue réécrit, schémas inchangés |
| **Consigné** | `labs/lab6/avant.md`, `diagnostic.md`, `apres.md`, `attribution.md` |
| **Artefact du fil rouge** | **A6** — un livrable de méthode : il se rejoue sur n'importe quel serveur |
| **Checkpoint** | `etat/sr1-fin` |

```bash
make lab6-verifier
git add serveurs/pharos_quai/ labs/lab6/ && git commit -m "LAB 6 — réécriture de catalogue"
```

**Mise en commun (5 min).** Chaque binôme annonce deux chiffres et une phrase : le taux avant, le
taux après, et la modification qui a produit le plus gros gain. La salle constatera que ce n'est pas
la même partout — et c'est précisément pourquoi on mesure au lieu d'appliquer des règles.

**Suite.** Le module **SR2** pose une question que ce lab n'a pas le droit de poser : et si la bonne
réponse n'était pas de réécrire l'outil, mais de ne pas en faire un outil du tout ? Ressources et
prompts, juste après la pause.
