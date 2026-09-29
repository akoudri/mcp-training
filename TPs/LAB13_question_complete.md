# LAB 13 — PHAROS répond à la question complète

**Module OR3** · durée 1 h 45
**Artefact produit** : **A13** — l'agent PHAROS complet
**Checkpoint de sortie** : `etat/or3-fin`

---

## Contexte

Le premier jour, une question a été posée :

> L'escale du *Vent d'Autan* de jeudi est-elle à risque ? Si oui, prépare la note d'alerte pour
> l'exploitant.

Depuis, chaque lab en a construit un morceau. `pharos-docs` lit les contrats, `pharos-data` connaît
les escales et sait dire ce qu'est un risque, `pharos-ops` interroge la météo et publie — sous
confirmation. La boucle du LAB 4 orchestre le tout.

Ce lab les branche ensemble. C'est le premier moment du parcours où l'agent fait quelque chose
d'utile de bout en bout — et le premier où l'on découvre ce que l'assemblage casse.

**Répartition indicative du temps** : 15 min de branchement et de mesure · 20 min pour le plan ·
35 min pour l'exécution complète · 20 min pour la vue · 15 min pour les signaux de dérive.

---

## Prérequis

| | |
|---|---|
| **Modules** | OR3 (21.1 à 21.4), OR4 |
| **Labs** | LAB 4, 5, 7, 9, 11, 12 |
| **Artefacts consommés** | **A4, A5, A7, A9, A10, A11, A12** — sept |
| **Fourni** | gabarit MCP App pour le plan de quai, vérificateur de note, jeu de trois questions |

```bash
git checkout etat/sr3-fin
make lab13-tout           # démarre les trois serveurs et les mocks
make lab13-scaffold
```

---

## SOCLE — pour tous

### Étape 1 — Brancher, et mesurer

Configurer la boucle du LAB 4 pour qu'elle liste les trois serveurs. Puis relever, dans
`labs/lab13/mesures.md` :

| | Valeur |
|---|---|
| Coût fixe du catalogue, un seul serveur (LAB 10) | |
| Coût fixe du catalogue agrégé | |
| Nombre d'outils exposés au total | |

Vérifier également qu'aucune collision de nom ne subsiste **sur le catalogue agrégé**.

### Étape 2 — Le plan visible

Faire produire un plan avant toute action, selon le bloc 21.3. Il doit porter, pour chaque étape :
le numéro, l'outil, **le serveur**, et la raison.

L'afficher avant le premier appel.

### Étape 3 — L'exécution complète

Poser la question cible. L'agent doit :

1. identifier l'escale à partir du nom du navire (`escales_du_jour`) ;
2. récupérer les clauses de pénalités du contrat ;
3. interroger la météo sur le créneau ;
4. évaluer le risque : critères de `escales_a_risque` + météo de `meteo_creneau` ; la note indique
   l'origine de chaque critère (calculé vs combiné) ;
5. **demander confirmation** avant de publier ;
6. produire la note.

Puis vérifier la note :

```bash
make lab13-verifier-note
```

Le vérificateur reprend chaque chiffre, chaque date et chaque nom de la note, et cherche son origine
dans la trace. Tout ce qu'il ne trouve pas est signalé.

### Étape 4 — La vue du plan de quai

À partir du gabarit fourni, produire une vue statique du plan de placement en MCP App.

**La réponse textuelle doit continuer d'exister en parallèle** : un client sans MCP Apps doit obtenir
une réponse utilisable. Le vérifier avec le client sans extension du LAB 12.

**Si le client déployé ne gère pas MCP Apps**, cette étape se réduit à la réponse textuelle : le
module OR4 est conditionné à la compatibilité client, et le socle reste atteignable sans la vue.

### Étape 5 — Les trois signaux de dérive

Calculer, à partir de la trace et du plan :

- les appels qui ne correspondent à aucune étape annoncée ;
- les étapes annoncées et jamais exécutées ;
- les enchaînements qui repartent en arrière.

Consigner les trois nombres. Ils serviront de référence au module EX2.

### Critères de réussite

- [ ] Les mesures de l'étape 1 sont consignées, y compris si le résultat est mauvais.
- [ ] Aucune collision de nom sur le catalogue agrégé.
- [ ] Le plan est affiché avant la première action, avec le serveur pour chaque étape.
- [ ] La confirmation du LAB 12 est effectivement déclenchée avant publication.
- [ ] La vue s'affiche (si le client gère MCP Apps), **et** la réponse texte existe pour un client sans MCP Apps.
- [ ] Les trois signaux de dérive sont calculés et consignés.
- [ ] **Critère décisif** — la trace montre au plus un appel superflu, et
      `make lab13-verifier-note` ne signale **aucune** donnée sans origine.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — La vue interactive

Ajouter un bouton de replanification dans la vue. Il déclenche `recalculer_plan_quai`, donc il passe
par le consentement du bloc 20.2 — **et** par la confirmation du LAB 12 si la replanification
entraîne une republication.

Compter les validations demandées à l'utilisateur. Si elles sont trois, se demander si c'est encore
utilisable.

### B — La collision de noms

Une collision a été introduite volontairement entre deux de vos serveurs. La trouver, mesurer son
effet sur le taux de bon choix, puis la corriger par préfixage.

L'intérêt est dans l'ordre : **mesurer avant de corriger**. Sinon on ne saura pas ce qu'elle coûtait.

### C — Le refus partiel

Poser la question, puis répondre au plan par :

> Fais tout, mais ne publie rien.

L'agent doit exécuter les cinq premières étapes et s'arrêter avant la sixième, en produisant la note
sans l'envoyer. C'est la deuxième capacité annoncée au bloc 21.3 — et elle ne fonctionne que si le
plan a été réellement utilisé, pas seulement affiché.

---

## Pièges & indices

**Le catalogue triple, et l'agent peut devenir plus mauvais.** C'est attendu, c'est mesurable, et
c'est le bloc 21.1. Ne pas corriger en salle : consigner. Le chiffre est plus utile que la
correction, et il justifiera au module EX2 qu'on n'active pas trois serveurs pour toutes les
questions. Certains hôtes et API proposent déjà une découverte progressive côté client (recherche
d'outils, chargement différé des définitions, exécution de code qui appelle les outils MCP) : c'est
un choix d'hôte, pas de serveur. Côté protocole, c'est un chantier annoncé (roadmap du 22 août
2026) : ne pas construire dessus.

**Le plan annoncé peut ne pas correspondre à ce que fait le modèle.** Ce n'est pas un bug. C'est un
contrat de lisibilité, pas d'exécution — bloc 21.3. L'écart se mesure à l'étape 5 ; il ne se corrige
pas en insistant dans le prompt.

**La note plausible mais inventée est le piège central.** Un chiffre de pénalité qui « sonne juste »,
une hauteur de houle vraisemblable, une date approximative. Le vérificateur existe pour cela, et il
attrapera ce que la relecture humaine laisse passer. C'est le mode d'échec n° 4 du bloc 2.3, à sa
dernière apparition avant le module EX2.

**Ne pas ajouter d'outil pour « aider » le modèle à enchaîner.** Si l'enchaînement rate, la réponse
est un outil métier qui porte la séquence — bloc 21.2 — et non une consigne supplémentaire dans le
prompt système.

**La vue ne remplace pas la réponse.** Un serveur qui ne produirait que l'interface est inutilisable
par la moitié des clients. Le test avec le client sans extension n'est pas une formalité.

**Six étapes, dont une météo lente.** Vérifier le budget de tour de la boucle : avec un timeout mal
réglé, c'est la boucle qui coupe au milieu du plan, et le diagnostic est déroutant. Le piège du
LAB 10 se retend, sur une chaîne plus longue.

**L'ordre des serveurs dans la configuration change le résultat.** Le noter en passant, sans y
consacrer de temps : c'est le bloc 21.1, et c'est un réglage fin, pas une architecture.

**Ne pas nettoyer la trace avant de la montrer.** Les appels superflus sont l'information la plus
utile de ce lab. Une trace propre parce qu'on a retiré ce qui gênait ne sert à personne.

---

## Livrable

| | |
|---|---|
| **Produit** | `client/` — agrégation, plan, signaux · `serveurs/pharos_ops/` — la vue de plan de quai |
| **Consigné** | `labs/lab13/mesures.md` — coûts, trois signaux, rapport du vérificateur de note |
| **Artefact du fil rouge** | **A13**, consommé par SG1, EX2 et EX3 |
| **Checkpoint** | `etat/or3-fin` |

```bash
make lab13-verifier
git add client/ serveurs/ labs/lab13/ && git commit -m "LAB 13 — agent PHAROS complet"
git fetch && git checkout etat/or3-fin
```

**Mise en commun (10 min).** Chaque binôme montre sa trace et lit sa note. Deux questions :
combien d'appels superflus, et le vérificateur a-t-il signalé quelque chose ? La seconde est la plus
intéressante — la donnée inventée est presque toujours celle qu'on aurait validée à la lecture.

**Suite.** L'agent existe et il fonctionne. À partir de demain, il ne s'agit plus de le faire
marcher mais de savoir s'il peut sortir.

Le module **SG1** ouvre la journée qui décide du passage en production. On commencera par glisser
une instruction dans un contrat de manutention, et par regarder ce que PHAROS en fait — celui que
vous venez de terminer.
