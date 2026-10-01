# LAB 0 — Premier contact

**Module FA2** · durée 45 minutes · aucun code à écrire
**Checkpoint de sortie** : `etat/fa2-fin`

---

## Contexte

L'opérateur portuaire PHAROS reçoit chaque jour des documents déposés par les agents maritimes :
contrats de manutention, connaissements, avis d'escale. Un serveur de démonstration est fourni :
il expose ces documents à un client MCP à travers trois outils.

Ce lab ne demande d'écrire aucune ligne de code. Son objet est ailleurs : **voir ce qui circule
réellement** entre un client et un serveur, et constater l'écart entre ce que le modèle affiche à
l'écran et ce qu'il a effectivement fait pour le produire.

C'est le seul lab du parcours où l'on observe sans construire. Tous les suivants ajouteront quelque
chose au fil rouge ; celui-ci installe le réflexe qui permettra de les déboguer.

**Répartition indicative du temps** : 10 min de branchement · 10 min d'interrogation · 20 min de
lecture de trace · 5 min de mise en commun.

---

## Prérequis

| | |
|---|---|
| **Modules** | FA1, FA2 (blocs 2.1 à 2.3) |
| **Pré-travail** | P1 — environnement conteneurisé vérifié. **Bloquant.** |
| **Artefacts consommés** | A0 (environnement) |
| **Fourni** | serveur `pharos-docs-demo`, jeu de documents d'escale, Inspector (observateur de trafic mitmproxy), client graphique VS Code préconfiguré |

Vérification préalable, dans le terminal (Linux ou Ubuntu sous WSL), à la racine du dépôt :

```bash
make lab0-up          # démarre le serveur de démonstration
make doctor           # doit afficher trois lignes OK
```

Si `make doctor` échoue, ne pas poursuivre : le problème est dans l'environnement, pas dans le lab.
Signaler au formateur immédiatement — c'est le seul point du parcours qui ne se rattrape pas en
avançant.

---

## SOCLE — pour tous

### Étape 1 — Brancher le serveur sur le client

Le fichier de configuration du client est fourni pré-rempli dans `labs/lab0/client.config.json`.
Le copier à l'emplacement attendu par le client graphique (la commande exacte est affichée par
`make lab0-up`), puis redémarrer le client.

Vérifier dans l'interface que le serveur `pharos-docs-demo` est bien listé, et que ses **trois
outils** apparaissent :

| Outil | Rôle |
|---|---|
| `lister_documents` | Documents rattachés à une escale |
| `lire_document` | Contenu d'un document, par plage de pages |
| `rechercher_clause` | Clause d'un contrat de manutention, par sujet |

### Étape 2 — Poser la question de référence

Dans le chat de VS Code, sélectionner le mode **PHAROS** (et non Agent ou Ask) : il ne donne au modèle que les outils du serveur.

Poser au client, mot pour mot :

> Résume les obligations de l'opérateur portuaire dans le contrat de manutention de l'escale
> ESC-2026-0412.

Lire la réponse. Ne pas encore chercher à savoir comment elle a été produite.

### Étape 3 — Ouvrir l'Inspector et retrouver les appels

```bash
make inspector        # ouvre l'Inspector sur le trafic du serveur
```

Reconstituer, **sans relire la réponse du modèle**, ce qui s'est passé. Remplir la fiche de trace
`labs/lab0/trace.md`, dont le squelette est fourni :

| Ordre | Outil appelé | Arguments | Taille du résultat | Utile ? |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

La colonne « Utile ? » est un jugement : l'appel a-t-il contribué à la réponse finale, ou le modèle
a-t-il tâtonné ?

### Étape 4 — Poser une seconde question, plus vague

> Est-ce que cette escale pose un problème ?

Remplir une seconde fiche de trace. Comparer le nombre d'appels avec la première.

### Critères de réussite

- [ ] Le serveur `pharos-docs-demo` est listé dans le client, avec ses trois outils.
- [ ] Une réponse a été produite pour la question de référence.
- [ ] L'Inspector affiche au moins un appel d'outil pour cette question.
- [ ] La fiche de trace de l'étape 3 est remplie : ordre, nom, arguments, taille de chaque résultat.
- [ ] La fiche de trace de l'étape 4 est remplie, et l'écart de nombre d'appels entre les deux
      questions est constaté.
- [ ] **Critère décisif** — être capable de dire, à voix haute et sans relire la réponse du modèle,
      quels outils ont été appelés, dans quel ordre, et avec quels arguments.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due. À prendre uniquement si le socle est terminé.*

### A — Mesurer le coût du catalogue

```bash
make tokens-catalogue
```

Le script compte les tokens consommés par les seules définitions d'outils, avant toute question.

Comparer au chiffre annoncé en FA1 (150 à 400 tokens par outil) et répondre par écrit à une
question : **d'où vient l'écart ?** Trois pistes, à vérifier dans le code source du serveur fourni,
sous `labs/lab0/serveur/` :

- la longueur des descriptions ;
- la présence d'une `description` par propriété du schéma, et pas seulement au niveau de l'outil ;
- les valeurs d'`enum`, qui sont transmises intégralement ;
- le prompt système que le fournisseur ajoute lui-même pour l'usage des outils.

### B — Provoquer le premier mode d'échec

Le serveur fourni contient un quatrième outil, désactivé, dont le nom et la description sont
volontairement proches de `rechercher_clause`. L'activer :

```bash
make lab0-outil-jumeau
```

Reposer la question de référence trois fois de suite, en repartant d'une conversation vierge à
chaque fois. Noter quel outil est choisi à chaque essai.

Revenir ensuite à trois outils : `make lab0-up`.

Ce que l'on cherche à constater : **le choix devient instable**. C'est le premier des quatre modes
d'échec vus au bloc 2.3, et c'est le problème que le module SR1 traitera pour de bon.

### C — Lire le trafic à la main

Sans l'Inspector, en activant la journalisation brute :

```bash
make lab0-up VERBEUX=1
tail -F logs/pharos-docs-demo.jsonl
```

Retrouver dans le flux les mêmes informations que dans l'Inspector. L'intérêt n'est pas
l'ergonomie : c'est de constater qu'il n'y a rien de magique dans l'outil d'inspection, et de
savoir déboguer un serveur sur une machine où il n'est pas installé.

---

## Pièges & indices

**Le client met en cache la liste des outils.** Après toute modification de la configuration ou
activation d'un outil, redémarrer le client. Un outil qui n'apparaît pas n'est pas forcément un
outil qui plante. Dans VS Code : palette > « MCP: List Servers » > pharos-docs-demo > Restart.

**VS Code demande une confirmation avant chaque appel d'outil : l'accepter — c'est l'occasion de lire les arguments.**

**Une réponse correcte n'implique pas qu'un outil ait été appelé.** C'est le piège central de ce
lab, et il est délibéré. Le modèle peut produire un résumé parfaitement plausible d'un contrat
qu'il n'a jamais lu. Si l'Inspector n'affiche aucun appel, la réponse est une invention — et elle
est présentable. C'est exactement ce qui rend ce mode d'échec dangereux en production.

**L'Inspector montre le trafic MCP, pas les échanges avec le modèle.** Les blocs `tool_use` et
`tool_result` vus au bloc 2.2 circulent entre le client et le modèle ; ils n'apparaissent pas ici.
Ce que l'on voit dans l'Inspector, ce sont les `tools/call` qui en découlent. Ne pas confondre les
deux traces : elles se correspondent, mais elles ne sont pas au même endroit.

**Un résultat vide n'est pas une erreur.** `lister_documents` sur une escale inconnue renvoie une
liste vide, avec succès. Vérifier ce que le modèle en fait — le quatrième mode d'échec du bloc 2.3
se manifeste précisément là.

**Ne pas juger la qualité du résumé.** Ce n'est pas l'objet du lab et cela consomme le temps de
l'étape 3, qui est la seule qui compte. La qualité des réponses est traitée à partir du module SR1,
avec une mesure et non une impression.

**Question 2 plus vague, plus d'appels — ce n'est pas une règle.** Le constat vaut pour cette
exécution-là. Le formateur relèvera les résultats de la salle en mise en commun : ils ne seront pas
identiques d'un poste à l'autre, et c'est le premier contact concret avec le non-déterminisme.

---

## Livrable

| | |
|---|---|
| **Produit** | `labs/lab0/trace.md` — deux fiches de trace remplies |
| **Extension éventuelle** | le chiffre de la mesure A, et la justification de l'écart |
| **Artefact du fil rouge** | aucun — ce lab n'ajoute pas de code à PHAROS |
| **Checkpoint** | `etat/fa2-fin` |

Commiter la fiche de trace sur la branche du binôme, puis se resynchroniser :

```bash
git add labs/lab0/trace.md && git commit -m "LAB 0 — fiches de trace"
git fetch && git checkout etat/fa2-fin
```

**Suite.** Le module **PR1** part de ce constat : ce serveur de démonstration a été écrit une fois
et fonctionne avec n'importe quel client conforme, sans que son auteur sache lequel. C'est ce que le
protocole achète — et le module PR1 dit à quel prix, et qui le gouverne.
