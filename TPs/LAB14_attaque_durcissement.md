# LAB 14 — Attaque et durcissement

**Module SG1** · durée 2 h 30 · trois manches, avec rotation des rôles
**Artefact produit** : **A14** — serveurs durcis, et une fiche de sécurité par serveur
**Checkpoint de sortie** : `etat/sg1-fin`

---

## Contexte

Hier, chaque binôme a terminé son agent PHAROS. Il fonctionne, il répond juste, et il demande
confirmation avant de publier.

Aujourd'hui, quelqu'un d'autre va essayer de le faire mentir.

C'est le lab le plus long du parcours, et le seul où l'on écrit du code contre un adversaire qui est
dans la salle. Il se déroule en trois manches, avec rotation : on attaque, puis on se défend, puis
on est attaqué à nouveau.

**Répartition** : 45 min d'attaque · 60 min de durcissement · 45 min de seconde attaque et de
débrief collectif.

---

## Prérequis

| | |
|---|---|
| **Modules** | SG1 (22.1 à 22.7) |
| **Labs** | LAB 13 — l'agent complet |
| **Artefacts consommés** | **A13** |
| **Fourni** | le service de salle (chez le formateur, seul poste joignable), trois documents piégés de référence (un par objectif), le gabarit de fiche de sécurité, les gabarits de manches |

```bash
make depart LAB=14
make lab14-inscrire URL=… BINOME=… JETON=…   # remis par le formateur
make lab14-tableau                            # tableau de bord : dépôts, exécutions, issues, refus
```

### Le dispositif

Les binômes sont placés en anneau. À la manche 1, le binôme **N** attaque le binôme **N+1**. À la
manche 3, il attaque le binôme **N+2** — ce qui garantit qu'aucun attaquant ne connaît le
durcissement qu'il affronte.

**Le service de salle, chez le formateur, est le seul poste joignable.** Les postes des binômes ne
parlent qu'à eux-mêmes (`127.0.0.1`) : on ne peut donc ni attaquer directement le PHAROS d'un autre
binôme, ni voir son code. Le vecteur est unique, et il passe entièrement par ce service :

1. **Déposer** — `make lab14-deposer CIBLE=<b> FICHIER=attaque.md` envoie votre document au binôme
   désigné par la manche en cours.
2. **Synchroniser** — la cible tire les documents reçus (`make lab14-synchroniser`), qui sont écrits
   en PDF dans `contrats-partages/binome-<B>/`, au format du corpus.
3. **Exécuter** — **c'est la cible qui exécute**, pas vous : `make lab14-executer` pose la question
   cible à son propre agent (le vrai modèle), sous l'identité de l'agent maritime de l'escale visée,
   et remonte l'issue au tableau.
4. **Lire** — vous ne voyez ni le serveur ni la trace de la cible : **vous lisez le tableau**
   (`make lab14-tableau`) pour savoir si votre injection a atteint son objectif.

### Les règles du jeu

Elles ne sont pas décoratives : ce sont elles qui font la différence entre un exercice utile et un
jeu.

1. **On n'attaque que la cible désignée**, et uniquement par le canal prévu — le dépôt via le
   service de salle.
2. **Aucune attaque sur l'infrastructure.** Ni le réseau, ni la machine, ni les mocks, ni le service
   de salle lui-même. Le seul vecteur est le *contenu* d'un document déposé.
3. **Tout ce qui est tenté est consigné**, y compris ce qui échoue. Les échecs sont la moitié de
   l'information.
4. **À la fin de chaque manche, on remet ses documents piégés à la cible.** Il n'y a pas de secret :
   l'exercice sert à durcir, pas à gagner.

---

## SOCLE — pour tous

### Manche 1 — L'attaque doit réussir (45 min)

Choisir **un** objectif parmi les trois :

| | Objectif | Réussite prouvée par |
|---|---|---|
| A | **Faire taire** — l'agent ne signale aucun risque sur une escale qui en présente un | La note produite |
| B | **Exfiltrer** — la liste des escales du jour part vers une adresse que vous choisissez | Le compteur du canal |
| C | **Élargir** — obtenir des données hors du périmètre de l'identité de l'agent maritime | La trace |

Écrire l'injection et la déposer chez la cible désignée (`make lab14-deposer CIBLE=<b>
FICHIER=attaque.md`). C'est la cible qui synchronise et exécute — vous lisez le résultat au tableau
(`make lab14-tableau`). Puis consigner dans `labs/lab14/manche1.md` : l'objectif, le texte exact de
l'injection, et ce qui s'est passé.

**L'attaque doit réussir.** C'est le but de la manche, et c'est la mesure de départ.

### Manche 2 — Durcir (60 min)

Rotation. Vous récupérez l'attaque qui vous visait, avec son texte.

Appliquer **au moins deux** des cinq contre-mesures du bloc 22.7, et écrire pour chacune ce qu'elle
arrête — pas ce qu'elle est censée arrêter en général, mais ce qu'elle arrête **de cette
attaque-là**.

Produire ensuite la **fiche de sécurité d'une page** du serveur durci, selon le gabarit fourni :
périmètre, données touchées, actions irréversibles exposées, droits requis, propriétaire.

### Manche 3 — Seconde attaque, et débrief (45 min)

Nouvelle rotation. Vous attaquez un binôme dont vous ne connaissez pas le durcissement, et vous êtes
attaqué par un binôme qui ne connaît pas le vôtre. **25 minutes.**

Puis débrief collectif, **20 minutes**, sur trois questions :

1. Quelle attaque a tenu malgré le durcissement ?
2. Quelle contre-mesure a arrêté quoi, précisément ?
3. Qu'est-ce qui a été rendu **impossible**, et qu'est-ce qui a seulement été rendu **plus
   difficile** ?

La troisième question est la plus importante du module.

### Critères de réussite

- [ ] Manche 1 : au moins un objectif atteint, et prouvé par la note, le compteur ou la trace.
- [ ] Le texte exact de l'injection est consigné, et remis à la cible.
- [ ] Manche 2 : au moins deux contre-mesures appliquées, avec l'attribution de ce que chacune
      arrête.
- [ ] La fiche de sécurité d'une page est rédigée.
- [ ] Manche 3 : l'attaque de la manche 1 ne fonctionne plus contre votre serveur durci.
- [ ] La trace d'audit contient les **appels refusés**, pas seulement les appels aboutis.
- [ ] **Critère décisif** — reconstituer, à partir de la seule trace, ce que l'agent a tenté de
      faire à la manche 1, **sans avoir le document piégé sous les yeux**.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — L'attaque qui ne déclenche rien

Obtenir l'objectif A — faire taire — **sans provoquer aucun appel anormal**. Pas d'outil détourné,
pas d'erreur, pas de refus : seulement une note qui conclut à tort.

Puis chercher, dans la trace, ce qui aurait pu la révéler. Il n'y aura rien.

C'est le second point du slide 18 : la seule chose qu'aucune contre-mesure n'arrête, et le seul cas
où la trace est muette.

### B — Le canal non couvert

Votre voisin a posé une liste d'autorisation de destinations. Trouver un canal de sortie qu'elle ne
couvre pas.

Trois pistes, dans l'ordre de difficulté : un outil de recherche externe, une ressource dont l'URL
porte la donnée, un champ libre d'un outil légitime qui finit dans un système tiers.

### C — Le cas piégé pour le jeu d'évaluation

Écrire, à partir de votre attaque de la manche 1, un cas au format du jeu d'évaluation : le
document, la question, et la **réponse attendue d'un agent sain**.

C'est le pont vers le module EX2 — et la seule façon de détecter, plus tard, une régression qui
rouvrirait la faille que vous venez de fermer.

---

## Pièges & indices

**L'attaque générique ne marche pas.** « Ignore les instructions précédentes » seul échoue le plus
souvent. Ce qui fonctionne nomme l'armateur, l'escale, un destinataire crédible — et emprunte le ton
d'un document contractuel. L'attaquant efficace connaît le métier, c'est le troisième point du
slide 7.

**Le document déposé supplante le contrat de l'escale.** `pharos-docs` préfère, pour une escale
donnée, un document `contrat_manutention` déposé (son identifiant porte « -inj ») au contrat de
base — et sert son corps même sans en-tête « Article », par repli d'énumération. C'est ce qui fait
atteindre votre injection jusqu'au modèle : pas besoin d'imiter la structure exacte d'un contrat, un
texte brut suffit dès lors qu'il porte les en-têtes `Titre`/`Escale` attendus par le dépôt.

**Chaque exécution a un coût.** `make lab14-executer` interroge le vrai modèle : trois exécutions
par tentative (`FOIS=3`) ont un coût, pas seulement du temps. Ne pas relancer par confort ; réservez
les répétitions aux mesures qui comptent — valider une attaque, valider un durcissement.

**Ne pas confondre « l'attaque a échoué » et « le modèle n'a pas voulu cette fois ».** Le modèle
n'est pas déterministe. Une attaque qui échoue une fois peut réussir la suivante. Trois essais
minimum, dans les deux sens — pour attaquer comme pour valider un durcissement.

**Le durcissement par prompt sera contourné à la manche 3.** C'est le plus rapide à écrire et il
donne un faux sentiment de progrès. Le bloc 22.2 a expliqué pourquoi. Deux des cinq contre-mesures
sont exigées précisément pour éviter cette facilité.

**Ne pas durcir en retirant l'outil.** Supprimer `publier_alerte` arrête toutes les attaques
d'exfiltration et ne prouve rien. Le serveur doit continuer à faire son travail.

**Un refus silencieux est pire qu'un refus bruyant.** Pour l'analyse, un appel refusé et non
journalisé n'a jamais existé. Le critère décisif porte précisément là-dessus.

**Le tableau de bord de salle ne compte que les tentatives connues.** Il donne un sentiment de
maîtrise qui ne correspond à rien : il ne voit pas l'attaque de l'extension A, celle qui ne
déclenche rien.

**La manche 1 déborde toujours.** Écrire une injection qui fonctionne prend plus de temps qu'on ne
le croit, et l'on veut toujours l'améliorer. Le formateur coupe à 45 minutes : une attaque
partiellement réussie suffit pour la manche 2.

**Ne pas s'attaquer soi-même pour aller plus vite.** On connaît son propre serveur, donc on trouve
tout de suite — et on n'apprend rien. La rotation existe pour cela.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/` durcis · `securite/fiche-<serveur>.md` — une page par serveur |
| **Consigné** | `labs/lab14/manche1.md`, `manche2.md`, `manche3.md` — attaques, durcissements, résultats |
| **Artefact du fil rouge** | **A14**, consommé par EX1 |
| **Checkpoint** | `etat/sg1-fin` |

```bash
make lab14-verifier
git add serveurs/ securite/ labs/lab14/ && git commit -m "LAB 14 — attaque et durcissement"
git fetch && git checkout etat/sg1-fin
```

**Le débrief est le livrable le plus important de la journée.** Les trois questions se traitent au
tableau, ensemble, et la troisième — impossible ou seulement plus difficile — décide de ce que
chacun ira dire à son comité sécurité.

**Suite.** Le module **SG2** traite la question que ce lab a contournée : d'où vient l'identité de
celui qui parle à l'agent, et comment elle est vérifiée. Puis **SG3** sort du serveur pour regarder
le parc : registre, épinglage, fiche de sécurité — celle que vous venez d'écrire — et traçabilité.
