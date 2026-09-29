# LAB 9 — `pharos-data` v1

**Modules DA2 et DA3** · durée 1 h 30
**Artefact produit** : **A9** — `pharos-data v1` : outils métier, cloisonnement, test automatisé
**Checkpoint de sortie** : `etat/da3-fin`

---

## Contexte

`pharos-data v0` répond à des questions formulées en colonnes, et il répond à tout le monde de la
même façon. Deux choses manquent avant qu'il puisse toucher une base réelle.

D'abord un vocabulaire : l'exploitant demande si une escale est « à risque », un concept qui
n'existe dans aucune table. Ensuite un périmètre : un agent maritime n'a rien à faire dans les
escales de ses concurrents.

Ce lab est le premier où l'on écrit du code contre **quelqu'un**, et non contre une erreur. Les
trois contournements fournis ont été écrits pour passer.

**Répartition indicative du temps** : 25 min pour `escales_a_risque` · 10 min pour le second outil ·
25 min pour le cloisonnement · 20 min pour les contournements · 10 min pour le test.

---

## Prérequis

| | |
|---|---|
| **Modules** | DA1, DA2 (14.1 à 14.3), DA3 (15.1 à 15.5) |
| **Labs** | LAB 8 |
| **Artefacts consommés** | **A8** — `pharos-data v0` · **A4** — `pharos-client` |
| **Fourni** | trois identités par jeton (exploitation et deux agents maritimes, `PHAROS_JETON`), adaptateur d'autorisation, squelette de politique RLS (`make lab9-politique`), outil `requete_sql` en squelette, trois contournements |

```bash
make depart LAB=9         # branche binome-<B>-lab09 depuis etat/da1-fin, et les gabarits
make lab8-base            # recharge la base (et réapplique labs/lab9/politique.sql s'il existe)
make lab8-up
make lab9-identites       # les trois identités, leurs navires, et le jeton de chacune
```

### D'où vient l'identité, aujourd'hui

Le mécanisme réel — jeton, vérification, périmètre — est traité au module **SG2**. Ici, un
adaptateur d'autorisation factice injecte l'identité dans le contexte de la requête, à partir du
jeton porteur du client : `PHAROS_JETON=jeton-rance make lab8-question QUESTION="…"`.

Ce qui compte dans ce lab n'est pas la façon dont elle est obtenue, mais le fait qu'elle **ne
transite par aucun argument d'outil**. Le jour où SG2 remplacera l'adaptateur, aucun outil ne devra
changer.

---

## SOCLE — pour tous

### Étape 1 — `escales_a_risque`

Implémenter la définition 2.0 retenue au bloc 14.1, fournie dans `serveurs/pharos_data/definition.py` :
deux critères nommés parmi les quatre (tirant d'eau, conflit de créneau, météo, retard cumulé) —
`tirant_eau` (tirant d'eau au-delà du maximum du quai, marge de 1,0 m déduite) et `conflit_creneau`.
La météo n'est pas encore disponible — `pharos-ops` arrive au module IS2.

La réponse doit porter :

- les **critères déclenchés** pour chaque escale, jamais un simple booléen ;
- le **détail chiffré** de chaque critère, pour que l'exploitant puisse contester ;
- `definition_version` : `"2.0"` ;
- `criteres_non_evalues` : `["meteo"]` — la météo n'est pas dans cette base, la réponse le dit
  explicitement plutôt que de la taire.

### Étape 2 — Un second outil métier

`conflits_de_creneau(date)` : les paires d'escales dont les créneaux se chevauchent sur un même
quai, avec la durée du chevauchement.

Il sera réutilisé au LAB 13, quand l'agent assemblera les trois serveurs.

### Étape 3 — Le cloisonnement

Un agent maritime ne voit que les escales de ses navires.

- La politique vit **dans la base** — sécurité au niveau ligne — et non dans un `WHERE` ajouté par
  l'outil. Elle s'écrit dans `labs/lab9/politique.sql`, s'applique par `make lab9-politique`, et lit
  l'agent de la requête dans la variable de session `pharos.agent`, que le serveur pose avant chaque
  requête.
- L'identité vient du contexte d'autorisation, jamais d'un paramètre.
- Vérifier avec les **deux** identités fournies : ce que voit l'agent A, ce que voit l'agent B, et
  ce que voit l'exploitation.

Vérifier aussi la question détournée :

> Combien d'escales sont prévues au quai 3 jeudi, toutes compagnies confondues ?

Elle passe par `escales_du_jour` (construit au LAB 8). L'agent A doit obtenir un compte qui ne porte
que sur son périmètre — sans que rien n'indique qu'il existe autre chose.

### Étape 4 — Les trois contournements

Fournis dans `labs/lab9/contournements.md`, et envoyés par `make lab9-contourner N=1` (2, 3) à
`requete_sql` — l'outil de lecture libre fourni en squelette, qui exécute sous le rôle de l'appelant.
Ils ont été écrits pour passer.

| | Contournement | Ce qui doit l'arrêter |
|---|---|---|
| 1 | Écriture déguisée dans une expression de table commune | Liste blanche d'instructions **et** rôle en lecture seule — « SELECT et rien d'autre » ne bloque pas les fonctions à effet de bord appelables depuis un SELECT (`set_config`, `dblink`, `lo_export`, `pg_sleep`…) : il faut en plus une liste blanche de fonctions, ou un rôle sans droit EXECUTE |
| 2 | Jointure vers une table hors périmètre (`tarifs`) | Liste blanche de tables, avant exécution |
| 3 | Énumération du schéma par messages d'erreur successifs | Message uniforme, ne portant que la liste blanche |

### Étape 5 — Le test automatisé

Ajouter le cloisonnement à la suite du LAB 7 : deux identités, une question, deux résultats
attendus. Sans modèle, dans le seuil des dix secondes : `make lab9-tests CHRONO=1`.

Le cloisonnement, déjà listé au bloc 12.1, entre dans la suite.

### Critères de réussite

- [ ] `escales_a_risque` renvoie critères, détail chiffré et `definition_version`.
- [ ] `conflits_de_creneau` répond, avec la durée du chevauchement.
- [ ] Aucun outil ne prend l'identité en paramètre.
- [ ] L'agent B ne voit aucune escale de l'agent A, y compris sur une question formulée pour cela.
- [ ] Les trois contournements échouent, avec un message interprétable par le modèle et qui ne
      révèle rien du schéma réel.
- [ ] Le test de cloisonnement tourne dans la suite, sans modèle.
- [ ] **Critère décisif** — retirer le filtre de cloisonnement d'un outil **ne change rien au
      résultat**. C'est la preuve que la protection vit dans la base.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Votre propre contournement

Écrire un quatrième contournement, et le soumettre au binôme voisin.

S'il passe, c'est une information utile pour lui, et pour vous. Les meilleurs viendront de ceux qui
connaissent bien PostgreSQL, ou bien le domaine — les deux angles produisent des attaques
différentes.

### B — Le masquage de colonne

`tarif_negocie` est visible pour l'exploitation, masqué pour les agents maritimes.

Deux façons : une vue par profil, ou un masquage au niveau colonne. Mettre en œuvre l'une des deux,
et vérifier que la colonne masquée **n'apparaît pas non plus** dans la ressource de schéma servie à
un agent maritime.

*Ce second point est celui qu'on oublie : une colonne masquée mais documentée reste une invitation.*

### C — Faire changer la définition

Passer `escales_a_risque` en version 2.1, en ajoutant le critère « retard cumulé ».

Puis vérifier trois choses : que `definition_version` a bien changé dans la réponse, que la version
2.0 reste appelable, et que votre test de non-régression **le remarque**.

C'est le bloc 14.2 rendu exécutable.

---

## Pièges & indices

**La RLS ne s'applique ni au propriétaire de la table, ni à un rôle qui la contourne.** C'est le
piège classique de PostgreSQL, et il est redoutable ici : tout fonctionne parfaitement en test parce
que la suite tourne avec un rôle privilégié, et le cloisonnement n'a en réalité jamais été vérifié.
Le test doit utiliser les rôles applicatifs, exactement comme le serveur en production.

**Le `WHERE` dans l'outil « en attendant » masque l'absence de politique.** Il fonctionne, il est
rapide à écrire, et il rend le critère décisif faux. Si retirer ce filtre change le résultat, la
protection n'est pas au bon endroit.

**L'identité en paramètre est tentante parce qu'elle est plus simple à tester.** C'est exactement
pour cela qu'elle se glisse dans le code. Le slide 14 du module DA3 en fait une règle sans
exception, et le critère de réussite la vérifie.

**Les trois refus doivent se ressembler.** Un attaquant qui énumère apprend autant des différences
entre messages que de leur contenu. Les trois renvoient la même forme, et ne révèlent que la liste
blanche — laquelle est déjà publique dans la ressource de schéma. Le modèle, lui, a de quoi se
corriger dans les trois cas.

**Ne pas tester le cloisonnement avec une seule identité.** Un serveur qui ne renvoie rien à
personne passe tous les tests à identité unique. Il en faut deux, et un troisième profil —
l'exploitation — qui voit tout.

**Ne pas oublier `definition_version`.** Elle paraît superflue aujourd'hui. Elle est ce qui
permettra au module EX2 de savoir si une régression vient du modèle, du catalogue, ou de vous.

**Le test de cloisonnement n'a pas besoin d'un modèle.** Deux appels d'outil directs, deux
identités, deux résultats attendus. S'il prend plus d'une seconde, c'est qu'il passe par quelque
chose qu'il ne devrait pas.

**La météo n'est pas dans cette base : la réponse le dit explicitement
(`criteres_non_evalues`).** Ne pas l'implémenter en dur pour compléter les quatre critères. Le
critère météo est combiné au LAB 13.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_data/` — deux outils métier, politique RLS, refus uniformes |
| **Consigné** | `labs/lab9/contournements.md` complété : ce qui les a arrêtés, et à quel étage |
| **Artefact du fil rouge** | **A9**, consommé par OR3, SG1 et EX2 |
| **Checkpoint** | `etat/da3-fin` |

```bash
make lab9-verifier
git add serveurs/pharos_data/ tests/ labs/lab9/ && git commit -m "LAB 9 — pharos-data v1"
```

**Mise en commun (5 min).** Une question par binôme : à quel étage chacun des trois contournements
a-t-il été arrêté ? Les réponses ne seront pas identiques, et c'est le point — un même contournement
arrêté par la liste blanche chez l'un et par le rôle en lecture seule chez l'autre indique que l'un
des deux a une défense de moins.

**Suite.** La famille données est close. Le module **IS1** ouvre la journée des systèmes externes :
jusqu'ici, tout ce que PHAROS interroge vous appartient — la base, les documents, le schéma. À
partir de demain, il faudra composer avec une API que vous ne contrôlez pas, qui tombe, qui est
lente, et dont la documentation ment parfois.
