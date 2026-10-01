# LAB 15 — Le jeu d'évaluation

**Module EX2** · durée 2 h · **validation sommative du parcours**
**Artefact produit** : **A15** — le jeu d'évaluation branché en intégration continue
**Checkpoint de sortie** : `etat/ex2-fin`

---

## Contexte

Dernier lab du parcours.

Il ne construit rien de nouveau. Il produit l'instrument qui permet à tout le reste de survivre :
sans jeu d'évaluation, l'agent que vous avez écrit restera exactement dans l'état où vous l'aurez
laissé — jusqu'au jour où le modèle changera, où un outil s'ajoutera, ou où une définition métier se
déplacera. Et personne ne le verra.

C'est aussi la validation sommative de la semaine. Elle porte sur un seul point : **détecter une
régression que vous aurez vous-même injectée, et savoir laquelle.**

**Répartition** : 45 min pour écrire les cas · 20 min pour le taux de référence · 25 min pour la
régression · 20 min pour la chaîne · 10 min de mise en commun.

---

## Prérequis

| | |
|---|---|
| **Modules** | EX1 (bloc 25.5), EX2 (26.1 à 26.4) |
| **Labs** | LAB 13, LAB 14 |
| **Artefacts consommés** | **A13** — l'agent complet · **A14** — les serveurs durcis |
| **Fourni** | harnais d'exécution (contexte figé, trois exécutions par cas, notation déterministe), squelette du rapport (`evaluation/rapport.py` : tableau et taux par famille fournis), régression à injecter, un cas d'exemple complet, cas piégé de sécurité de secours (`evaluation/exemples/cas_securite.yaml`), chaîne rapide (`.ci/rapide.yaml`) et squelette de la chaîne d'évaluation (`.ci/evaluation.yaml`) |

```bash
make depart LAB=15        # branche binome-<B>-lab15 depuis etat/sg1-fin, et les gabarits
make lab13-tout           # la base, les mocks et les trois serveurs
make lab15-exemple        # un cas complet, commenté, dans le format attendu (pénalité du Vent d'Autan)
make lab15-empreinte      # le contexte à figer : date, identités, empreinte de la base
```

---

## SOCLE — pour tous

### Étape 1 — Écrire dix cas

Le quota est imposé, et il n'est pas négociable :

| Famille | Nombre |
|---|---|
| Cas simples — un serveur, une réponse vérifiable | **4** |
| Cas multi-serveurs — l'enchaînement du LAB 13 | **3** |
| Cas où la bonne réponse est « je ne peux pas répondre » | **2** |
| Cas piégé de sécurité — repris du LAB 14, extension C | **1** |

Si l'extension C du LAB 14 n'a pas été faite, partir du cas piégé fourni
(`evaluation/exemples/cas_securite.yaml`) ou de l'attaque consignée dans `labs/lab14/manche1.md`.

Chaque cas porte un **contexte figé** : date, identité de l'appelant, état de la base
(`make lab15-empreinte`). Sans cela, deux exécutions ne se comparent pas — le harnais refuse de lancer
un cas dont la date ou l'empreinte ne correspond pas à la salle.

Pour un cas dont la réponse attendue est une note rédigée (le cas de sécurité, par exemple), un
simple `contient` / `ne_contient_pas` ne suffit pas toujours : un modèle juge peut s'y ajouter, en
notant que son verdict a lui aussi sa propre instabilité, à mesurer. Le harnais fourni, lui, note sans
juge : le cas de sécurité fourni se juge à ce que la note **ne contient pas** (aucune escale hors du
périmètre de l'identité).

Écrire les cas **à partir des questions que pose l'exploitant**, pas à partir de la liste des outils.

### Étape 2 — Le taux de référence

```bash
make lab15-lancer          # dix cas, trois exécutions chacun → sortie/lab15/<horodatage>.json
make lab15-referencer      # fige ce résultat comme référence : evaluation/reference.json
```

Trente exécutions. Consigner le taux global **et** le taux par famille dans
`labs/lab15/reference.md`, avec le modèle et sa version épinglée (cf. bloc 10.2) : un taux ne se
compare qu'entre binômes ayant utilisé le même modèle.

La tolérance n'est pas uniforme selon la famille. Pour les cas de sécurité et ceux qui touchent une
action irréversible, exiger **3/3** — toutes les exécutions réussissent, pas « au moins une » ni
« deux sur trois ». Pour les autres familles, un cas peut être instable — réussi deux fois sur
trois. **Le consigner comme tel. Ne pas le corriger.**

### Étape 3 — La régression

```bash
make lab15-regression      # renomme un outil, sans toucher à sa description
make lab15-lancer
make lab15-rapport         # votre rapport : la comparaison à la référence, à écrire dans evaluation/rapport.py
```

Comparer au taux de référence. Vérifier trois choses :

- la chaîne passe au rouge ;
- l'écart se concentre sur une famille, et pas uniformément ;
- **le rapport nomme le cas fautif**, sans qu'un humain ait à lire une trace.

Puis retirer la régression (`make lab15-regression-retirer`), et vérifier le retour à la référence.

### Étape 4 — La chaîne

Brancher le jeu en intégration continue, dans une chaîne **séparée** de celle du bloc 25.5
(`.ci/rapide.yaml`, fournie), avec ses trois déclencheurs : changement de modèle, de catalogue, ou de
prompt système — et avant chaque publication. Compléter `.ci/evaluation.yaml` : il lance
`make lab15-chaine`, qui compare les empreintes du modèle, du catalogue et du prompt à
`evaluation/reference.json` et répond « rien à lancer » si aucune n'a bougé (`PUBLICATION=1` : le jeu
tourne quand même, comme sur un tag).

### Critères de réussite

- [ ] Dix cas, quota des quatre familles respecté, chacun avec un contexte figé.
- [ ] Le taux de référence est consigné, global et par famille, sur trois exécutions par cas.
- [ ] Au moins un cas instable est **consigné comme instable**, et non corrigé — hors cas de
      sécurité et d'action irréversible, qui exigent 3/3 sans exception.
- [ ] La régression fait passer la chaîne au rouge, et l'écart se concentre sur une famille.
- [ ] La chaîne est séparée de la chaîne rapide, avec ses propres déclencheurs.
- [ ] **Critère décisif** — vert sur l'agent sain, rouge sur l'agent régressé, et **le rapport
      désigne le cas fautif sans intervention humaine**.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Le coût par cas

Ajouter la mesure du coût, et identifier les deux cas les plus chers.

Puis la question qui compte : valent-ils leur prix ? Et que faudrait-il changer pour les rendre
moins chers **sans dégrader la réponse** — moins d'outils activés, un outil métier qui porte
l'enchaînement, un résultat mieux borné ?

### B — Votre régression contre le jeu du voisin

Écrire une seconde régression — un seuil métier déplacé, une description d'outil affadie, une
définition changée sans changer la forme — et la soumettre au binôme voisin.

Son jeu doit la détecter. **S'il ne la voit pas, il lui manque un cas**, et il sait maintenant
lequel.

C'est la seule façon d'évaluer un jeu d'évaluation.

### C — La faille rouverte

Retirer l'un des durcissements du LAB 14, puis relancer.

Le cas piégé de sécurité doit passer au rouge. S'il reste vert, c'est qu'il testait autre chose que
ce qu'on croyait — et c'est une information qui valait le détour.

---

## Pièges & indices

**Écrire les cas depuis le code est l'erreur qui vide le lab de son sens.** Un jeu construit à partir
de la liste des outils mesure les outils. Un jeu construit à partir des questions que pose
l'exploitant mesure l'agent. Les deux se ressemblent sur le papier et ne détectent pas les mêmes
choses.

**Le contexte doit être figé.** Date, identité, état de la base. Si la date d'exécution entre dans
la question, le résultat change chaque jour et la comparaison ne vaut rien. Figer la date, c'est
figer ce que l'hôte injecte dans la consigne système. C'est le piège le plus silencieux du lab.

**Ne pas corriger le cas instable.** La tentation est forte : ajuster la formulation, assouplir le
`contient`, jusqu'à ce qu'il passe trois fois sur trois. C'est du surapprentissage sur son propre
jeu — le jeu devient vert et cesse de mesurer quoi que ce soit.

**Les cas « je ne peux pas répondre » sont ennuyeux à écrire.** C'est pour cela qu'ils manquent
partout. Ce sont pourtant eux qui empêchent d'optimiser un agent complaisant, et ils sont dans le
quota pour cette raison.

**Trois exécutions minimum, comme au LAB 6.** Une exécution unique ne mesure rien, et deux ne
départagent pas.

**Le rapport doit se lire sans ouvrir une trace.** Nom du cas, famille, taux avant, taux après, et
l'écart. Si le diagnostic exige d'ouvrir la trace, la chaîne ne servira pas à trois heures du matin.

**Ne pas mettre le jeu dans la chaîne rapide.** Elle passerait de quelques dizaines de secondes à
plusieurs minutes, et plus personne ne l'attendrait — ce qui coûterait les quatre garde-fous du bloc
25.5, pas seulement celui-ci.

**Surveiller le coût.** Trente exécutions multipliées par cinq à dix appels d'outils : le budget se
voit. C'est aussi une bonne raison de garder le jeu court et les cas bien choisis.
`make lab15-lancer CAS=id1,id2 FOIS=1` essaie un cas sans payer les trente exécutions.

**Le jeu ne publie jamais.** La confirmation du LAB 12 y est refusée par défaut
(`confirmation: refuser`) : un cas qui attend une publication mesure la demande de confirmation, pas
l'envoi.

---

## Livrable

| | |
|---|---|
| **Produit** | `evaluation/cas/` — dix cas · `evaluation/rapport.py` · la chaîne d'intégration |
| **Consigné** | `labs/lab15/reference.md` — taux global et par famille, avant et après régression |
| **Artefact du fil rouge** | **A15** — le dernier du parcours |
| **Checkpoint** | `etat/ex2-fin` |

```bash
make lab15-verifier
git add evaluation/ .ci/ labs/lab15/ && git commit -m "LAB 15 — jeu d'évaluation"
git fetch && git checkout etat/ex2-fin
```

**Mise en commun (10 min).** Trois chiffres par binôme : le taux de référence, le taux après
régression, et le nombre de cas instables.

Le troisième chiffre est le plus intéressant. Un binôme qui annonce zéro cas instable a
probablement corrigé jusqu'à ce que tout passe — et son jeu ne mesurera plus rien dans trois
semaines.

**Suite.** Les trois modules qui restent ne construisent plus rien. **EX3** replace l'agent dans une
chaîne de traitement et repose la question du module FA1 — celle de savoir s'il fallait un agent.
**CC1** compare MCP aux cadres d'orchestration, grille en main. **CC2** dit où va l'écosystème, et
ce qui bougera au 2026-12-15.

Puis chacun énoncera le premier serveur qu'il écrira en rentrant.
