# LAB 12 — Confirmation avant publication

**Module SR3** · durée 1 h 15
**Artefact produit** : **A12** — la confirmation obligatoire avant publication d'alerte
**Checkpoint de sortie** : `etat/sr3-fin`

---

## Contexte

Depuis le premier jour, PHAROS lit. Il lit des contrats, des escales, des mouvements, une météo. Il
n'a jamais rien écrit à l'extérieur.

Ce lab ajoute la première action irréversible du fil rouge : publier une alerte de retard à
l'exploitant. Cran 4 du curseur d'autonomie posé au module FA1 — une fois partie, elle ne se
rattrape pas.

Vous allez la construire **d'abord sans garde-fou**, et regarder ce qui se passe. C'est la seule
façon de voir le problème avant de le résoudre.

**Répartition indicative du temps** : 10 min sans garde-fou · 20 min pour la demande · 20 min pour
le rejeu côté client · 10 min pour le repli · 15 min pour les deux instances et l'altération ·
15 min pour l'usage unique.

---

## Prérequis

| | |
|---|---|
| **Modules** | SR3 (19.1 à 19.6), PR3 (bloc 5.6) |
| **Labs** | LAB 4, LAB 5, LAB 10 |
| **Artefacts consommés** | **A10** — `pharos-ops` · **A4** — `pharos-client` |
| **Fourni** | canal de publication avec compteur, `client/pharos_client/entrees.py` (session qui déclare l'élicitation, demandes d'entrée : appel brut, rejeu, question à l'utilisateur), clients de test, répartiteur à deux instances |

```bash
make depart LAB=12        # branche binome-<B>-lab12 depuis etat/is3-fin, et les gabarits
make lab8-base            # la base, que lit pharos-ops
make lab10-up             # pharos-ops, une instance (8103) : étapes 1 à 4
make lab12-canal          # boîte de dépôt observable, avec compteur
make lab12-clients        # un client qui déclare l'élicitation, sur 8103 ;
                          # SANS_ELICITATION=1 : un qui ne la déclare pas
```

Le canal de publication est un mock, mais il **compte**. `make lab12-compteur` affiche le nombre
d'alertes réellement parties. C'est la seule vérité du lab.

---

## SOCLE — pour tous

### Étape 1 — L'action irréversible, sans garde-fou

Exposer `publier_alerte(escale_id, niveau, destinataire="exploitation", note="")` qui publie
réellement (`pharos.canal.publier`), sans rien demander.

Puis poser, via la boucle du LAB 4 (`make lab10-question QUESTION="…"`) :

> L'escale du *Vent d'Autan* de jeudi est à risque. Préviens l'exploitant.

Relever `make lab12-compteur`, et **consigner le chiffre**. Recommencer trois fois, en repartant
d'une conversation vierge.

Ne pas corriger. C'est l'état des lieux.

### Étape 2 — La demande de confirmation

Faire de `publier_alerte` un appel qui rend la main, selon le bloc 19.2 :

- `resultType: "input_required"`, avec une **élicitation `form`** : un booléen dans le
  `requestedSchema`, `default: false` ;
- un `message` qui porte le contexte — l'escale, le niveau, et **le destinataire**, à afficher
  systématiquement (voir les pièges) ;
- un `requestState` qui porte ce qu'il faudra retrouver au rejeu. Le SDK le **scelle, le date et le
  lie aux arguments** de l'appel — on ne signe rien soi-même : c'est vous qui choisissez ce qu'il
  contient.

### Étape 3 — Le rejeu, côté client

La boucle du LAB 4 doit ouvrir sa session par `entrees.SessionElicitation(url)` : c'est elle qui
déclare l'élicitation. Une `transport.Session` ordinaire reçoit le repli de l'étape 4, et la boucle
n'a alors rien à rejouer. Puis elle doit :

1. reconnaître ce troisième type de résultat — ni succès, ni erreur ;
2. présenter la demande à l'utilisateur ;
3. reposer **le même appel**, augmenté de `inputResponses` et du `requestState` reçu, avec un
   nouvel identifiant JSON-RPC.

C'est le point où la moitié des implémentations dérapent. Voir les pièges.

### Étape 4 — Le repli

```bash
make lab12-clients SANS_ELICITATION=1
```

Le serveur lit les capacités déclarées dans `_meta`. Si l'élicitation n'est pas déclarée, il
**refuse explicitement** la publication, en disant pourquoi et en proposant l'alternative que
le vérificateur attend : préparer la note sans la publier.

Vérifier que le compteur reste à zéro.

### Étape 5 — Deux instances, et l'altération

```bash
make lab12-deux-instances
make lab12-clients URL=http://observateur:8203/mcp    # les clients de test, sur le répartiteur
```

- Le rejeu doit fonctionner quand il atterrit sur une autre instance que la demande : configurer
  `RequestStateSecurity` (la clé partagée `CLE_ETAT`, une audience) — sinon chaque instance scelle
  avec sa propre clé, éphémère.
- Un `requestState` altéré d'un seul caractère, au milieu de la chaîne, doit être refusé — par le
  protocole, sans publication, et journalisé.

### Étape 6 — Usage unique

Rejouer, avec le **même** `requestState` confirmé, une seconde fois.

Enregistrer, au moment de la publication, une clé d'idempotence : l'empreinte de `escale_id` +
`niveau` + `destinataire` + une fenêtre de temps. Refuser toute seconde publication qui présente
la même clé.

C'est un état côté serveur — comme pour Tasks (LAB 11), assumé — mais ici la spec MRTR l'**exige**
(MUST) pour une action irréversible, à la différence de Tasks où ce n'était qu'une exception admise.

### Critères de réussite

- [ ] Le chiffre de l'étape 1 est consigné, avant toute correction.
- [ ] Aucun chemin de code ne publie sans être passé par le rejeu.
- [ ] Le `requestState` est scellé par le SDK (clé partagée, audience) et porte ce qui a été confirmé.
- [ ] La boucle repose le **même** appel augmenté (même méthode, mêmes arguments), et non un
      nouvel appel.
- [ ] Un client sans élicitation obtient un refus explicite, et le compteur reste à zéro.
- [ ] Le rejeu fonctionne sur une autre instance ; un `requestState` altéré est refusé par le
      protocole, sans publication, et journalisé.
- [ ] Rejouer deux fois le même `requestState` confirmé ne publie qu'une fois.
- [ ] **Critère décisif** — un refus laisse le système propre : rien d'écrit, rien de partiellement
      envoyé, et le compteur inchangé.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Regrouper deux demandes

Deux élicitations dans une même map `inputRequests` : confirmation et choix du destinataire —
exploitation, agent maritime, ou les deux.

Comparer le nombre d'interruptions vues par l'utilisateur, avant et après. C'est l'argument
ergonomique du bloc 19.4, chiffré.

### B — Fenêtre courte ou clé consommée : arbitrer

Le socle (étape 6) impose une clé d'idempotence enregistrée à la publication. Une autre parade
existe, sans état supplémentaire : une fenêtre d'expiration très courte
(`RequestStateSecurity(ttl=…)`).

Comparer les deux : robustesse, complexité, ce qui se passe si le rejeu arrive juste après
l'expiration de la fenêtre. Écrire l'arbitrage retenu et pourquoi.

### C — La valeur par défaut, en conditions réelles

Passer `default` à `true`, puis utiliser le client qui **applique le défaut sans demander** (`make lab12-clients DEFAUT=1`).

Relever le compteur. L'alerte est partie sans que personne n'ait rien confirmé — et le code du
serveur est pourtant correct.

Remettre `false`. C'est la quatrième règle du bloc 19.5, et c'est la seule qui se paie en incidents.

---

## Pièges & indices

**Ne pas sauter l'étape 1.** C'est le seul moment du parcours où l'on voit un agent déclencher une
action irréversible sans qu'on le lui ait demandé. Le chiffre relevé — au moins une publication
partie sans que personne ne l'ait confirmée, parfois davantage pour une seule question — est ce qui
rend le reste du lab évident.

**Le rejeu n'est pas un nouvel appel.** Si la boucle rappelle `publier_alerte` sans transmettre le
`requestState`, le serveur repart de zéro et redemande une confirmation. Symptôme : une boucle de
confirmation infinie, et l'utilisateur qui clique « oui » trois fois de suite. C'est l'erreur la
plus fréquente sur ce lab.

**Le `requestState` doit porter les arguments de l'appel.** Sinon un client peut faire confirmer la
publication pour l'escale A, puis rejouer avec les arguments de l'escale B — et le serveur exécutera,
puisque la confirmation est valide. La confirmation doit être liée à **ce qui a été confirmé**.

**Ne pas conserver l'appel en attente côté serveur.** C'est le piège du LAB 2 qui se retend : garder
un dictionnaire des appels en cours fonctionne parfaitement sur une instance, et casse à la seconde.
Tout doit voyager dans le `requestState`.

**Le compteur est la seule vérité.** La trace peut être trompeuse si un chemin de code publie sans
passer par l'outil — un rappel, une tâche de fond, un test resté branché. Vérifier le compteur, pas
la trace.

**Un refus doit laisser propre.** Si vous écrivez le brouillon de la note avant de demander la
confirmation, un refus laisse un brouillon orphelin. L'ordre est : demander, puis écrire.

**Ce qui s'affiche n'est pas toujours votre prompt.** Selon les clients, la demande est présentée
telle quelle, ou reformulée par le modèle. C'est précisément pourquoi la troisième règle du bloc
19.5 impose de mettre le contexte **dans** la question : si l'escale n'y figure pas, la reformulation
la perdra.

**Le `destinataire` libre est une surface d'exfiltration.** Rien ne le borne aujourd'hui : c'est
volontaire pour ce lab, et ce sera fermé au LAB 14 par une liste d'autorisation. En attendant, le
`message` de l'élicitation doit toujours **afficher le destinataire** — un utilisateur qui ne le
relit pas ne verra pas qu'il a changé.

**Un refus n'est pas une erreur.** Une réponse `decline` ou `cancel` de l'utilisateur laisse le
compteur **inchangé** : ce n'est ni un succès ni une panne, juste une confirmation qui n'a pas eu
lieu.

**Ne pas exposer un outil `confirmer_publication`.** La tentation existe, et elle contourne tout le
mécanisme : le modèle appellerait alors la confirmation lui-même. C'est le contraire du but
recherché.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_ops/` — publication sous confirmation · `client/` — reconnaissance et rejeu |
| **Consigné** | `labs/lab12/mesures.md` — le chiffre de l'étape 1, et le comportement observé du repli |
| **Artefact du fil rouge** | **A12**, consommé par OR3 |
| **Checkpoint** | `etat/sr3-fin` |

```bash
make lab12-verifier
git add serveurs/ client/ labs/lab12/ && git commit -m "LAB 12 — confirmation avant publication"
```

**Mise en commun (5 min).** Deux chiffres par binôme : combien d'alertes sont parties à l'étape 1,
et combien sont parties **sans confirmation** à la fin. Le premier chiffre surprend toujours
quelqu'un ; le second doit être zéro partout.

**Suite.** Il reste deux modules avant l'assemblage. **OR4** traite les interfaces rendues par le
serveur — MCP Apps — et **OR3** réunit enfin les trois serveurs pour répondre à la question posée le
premier jour :

> L'escale du *Vent d'Autan* de jeudi est-elle à risque ? Si oui, prépare la note d'alerte pour
> l'exploitant.

Tout ce qui a été construit depuis lundi y passe, y compris la confirmation écrite aujourd'hui.
