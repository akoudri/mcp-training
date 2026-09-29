# LAB 11 — Recalcul de plan de quai

**Module IS3** · durée 1 h 30
**Artefact produit** : **A11** — le recalcul de plan de quai en tâche
**Checkpoint de sortie** : `etat/is3-fin`

---

## Contexte

Quand une escale est décalée, tout le plan de placement de la journée est à revoir : les créneaux
se déplacent, les contraintes de tirant d'eau changent, et la météo peut fermer un quai.

Le calcul complet prend deux à cinq minutes selon le nombre d'escales. C'est le cas type du bloc
18.1 : requête et réponse ne suffisent plus.

**Où vit ce calcul.** Dans `pharos-ops`. C'est une opération d'exploitation, et le serveur
d'exploitation est le bon endroit. Il lira la base directement, avec un rôle en lecture seule —
**un serveur MCP n'appelle pas un autre serveur MCP**, et ce point mérite d'être dit en salle avant
que quelqu'un ne l'essaie.

**Répartition indicative du temps** : 10 min de prise en main du calcul fourni · 20 min pour la
décision côté serveur · 30 min pour le cycle · 15 min pour le plan B · 15 min de vérification par la
boucle.

---

## Prérequis

| | |
|---|---|
| **Modules** | IS3 (18.1 à 18.6), PR3 (cœur sans état) |
| **Labs** | LAB 9, LAB 10 |
| **Artefacts consommés** | **A9**, **A10**, **A4** |
| **Fourni** | le moteur de planification, deux clients de test (avec et sans l'extension), squelette |

```bash
make depart LAB=11        # branche binome-<B>-lab11 depuis etat/is2-fin, et les gabarits
make lab8-base            # le moteur lit la base
make lab11-scaffold       # (re)démarre pharos-ops ; VITESSE=rapide divise les durées par dix
make lab11-clients        # un client qui déclare Tasks ; SANS_TASKS=1 : un qui ne le déclare pas
```

### Le calcul est fourni

```python
from pharos_ops.planification import recalculer
plan = await recalculer(date, quais, rappel_progression)   # une coroutine : sans await, rien
                                                           # n'est calculé
# rappel_progression(traitees: int, total: int) est appelé à chaque escale
# lit la base (rôle en lecture seule) et la météo ; une panne en cours de calcul
# lève MeteoIndisponible
return plan.en_dict()                                      # ce que rend l'outil
```

Le moteur est lent par construction. `make lab11-scaffold VITESSE=rapide` divise les durées par dix
pour itérer, mais **la vérification finale se fait à vitesse réelle**.

Le point important : `recalculer` vous rend la main à chaque escale traitée. La progression que
vous afficherez viendra donc du calcul lui-même, et pas d'un minuteur.

---

## SOCLE — pour tous

### Étape 1 — La décision, côté serveur

Un seul outil : `recalculer_plan_quai(date, quai=None)`.

| Appel | Comportement attendu |
|---|---|
| `quai=3` | Quelques secondes. Réponse immédiate. |
| `quai=None` (la journée) | Deux à cinq minutes. Réponse en tâche. |

La décision est prise par le serveur, à partir des arguments. **Aucun paramètre `async`, aucun
second outil.**

Le serveur doit également lire, dans les capacités portées par `_meta`, si le client sait gérer
l'extension. La décision s'écrit dans `decider(nom, arguments, client_declare)`, dans
`serveurs/pharos_ops/taches.py` — l'extension qui l'appelle est fournie.

### Étape 2 — Le cycle

Mettre en œuvre la soumission, l'interrogation, la progression et la récupération du résultat. Côté
client, `client/pharos_client/taches.py` (fourni) suit une tâche : la boucle du LAB 4 s'en sert pour
afficher la progression et ne réinjecter au modèle que le résultat final.

Les méthodes du protocole sont `tasks/get`, `tasks/update` et `tasks/cancel` — pas de `tasks/result`,
pas de `tasks/list`. Note : `tasks/update` sert quand une tâche attend une entrée ; c'est MRTR
appliqué à une tâche.

La progression est un **compte réel** : « 9 escales sur 24 ». Elle vient du rappel fourni par le
moteur, pas d'une estimation de durée. Le vérificateur lit ce format exact, « N escales sur M » :
« 9 escales traitées sur 24 » ou « 9/24 » ne sont pas reconnus.

Suggérer un intervalle d'interrogation. Trop court, il charge le serveur pour rien ; trop long,
l'utilisateur croit que c'est bloqué.

### Étape 3 — Le plan B

Avec le client qui **ne déclare pas** l'extension :

```bash
make lab11-clients SANS_TASKS=1
```

Deux réponses sont légitimes, au choix du serveur :

- **Conforme** : renvoyer l'erreur JSON-RPC **-32021** (*Missing Required Client Capability*), avec
  `requiredCapabilities` — l'erreur va au client, pas au modèle ; c'est à l'hôte de la traduire.
- **Dégradation** : servir en synchrone, en résultat normal, une version réduite — le recalcul quai
  par quai.

Ce qui est interdit dans tous les cas : une exécution lancée dans le vide, ou un blocage.

### Étape 4 — La vérification par la boucle

À vitesse réelle, poser :

> Le plan de placement de jeudi est à revoir, l'escale du *Vent d'Autan* a été décalée.

Puis observer les deux minutes qui suivent, du point de vue de l'utilisateur.

### Critères de réussite

- [ ] `recalculer_plan_quai(quai=3)` répond immédiatement ; sur la journée entière, il rend une
      tâche.
- [ ] La décision vient du serveur : aucun argument ne la commande.
- [ ] La progression est un compte réel, issu du moteur, et elle avance.
- [ ] Le **client** traite les trois statuts : `completed`, `failed`, `cancelled` (l'implémentation
      de `tasks/cancel` côté serveur reste en extension).
- [ ] Un client sans l'extension obtient soit l'erreur **-32021** (`requiredCapabilities`), soit une
      version dégradée servie en synchrone — jamais une exécution lancée dans le vide, ni un blocage.
- [ ] Le client conserve les identifiants de tâche durablement, pour reprendre après un redémarrage.
- [ ] **Critère décisif** — pendant les deux minutes, l'utilisateur voit une progression qui
      avance réellement, et l'agent n'invente à aucun moment un résultat qu'il n'a pas reçu.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Annuler proprement

Le socle demande que le **client** sache traiter le statut `cancelled` ; ceci va plus loin :
implémenter `tasks/cancel` **côté serveur**. Annuler à mi-parcours et vérifier qu'aucun travail
orphelin ne subsiste : pas de plan partiel écrit, pas de verrou tenu, pas de tâche fantôme dans l'état du
serveur.

Puis provoquer le troisième cas du bloc 18.3 : annuler après que le plan a commencé à être écrit.
Compenser, ou refuser l'annulation en le disant. Documenter le choix.

### B — Couper la météo pendant l'exécution

```bash
make lab10-mocks PANNE=meteo    # pendant que la tâche tourne
```

Que devient la tâche ? Le statut doit passer à échec, et le message doit porter les trois parties du
bloc 17.3 — ce qui est tombé, ce qui reste, ce qu'il ne faut pas conclure.

Vérifier ensuite ce que l'agent en fait : il ne doit ni relancer indéfiniment, ni conclure sur un
plan qu'il n'a pas.

### C — Isoler la dépendance

C'est la recommandation du bloc 18.6, rendue exécutable.

Définir une interface à vous — `TravailLong`, avec `soumettre`, `etat`, `annuler` — et faire de
Tasks une implémentation parmi d'autres. Puis écrire une seconde implémentation, avec un
identifiant maison et un outil de suivi, et vérifier qu'on bascule de l'une à l'autre sans toucher
au moteur de planification.

Chronométrer. Si cela prend plus d'une demi-journée, c'est que l'interface est trop large.

---

## Pièges & indices

**Un serveur MCP n'appelle pas un autre serveur MCP.** La tentation est forte ici : `pharos-ops` a
besoin des escales, et `pharos-data` les expose déjà. C'est un anti-patron — il crée un couplage
invisible, double la latence, et rend le cloisonnement du LAB 9 impossible à raisonner. Le recalcul
lit la base directement, avec son propre rôle en lecture seule.

**Une progression pilotée par un minuteur est un mensonge.** Le moteur fourni vous rappelle à chaque
escale précisément pour éviter cela. Une barre qui avance de 10 % toutes les quinze secondes pendant
que le calcul patine est pire que pas de barre : elle fait attendre au lieu d'alerter.

**Le timeout de l'outil s'applique à la soumission, pas au travail.** C'est une confusion fréquente.
La soumission doit répondre en quelques centaines de millisecondes ; le travail, lui, dure ce qu'il
dure et n'est plus soumis à ce budget.

**L'état de la tâche est un état côté serveur, et c'est assumé.** Cela semble contredire le cœur
sans état du module PR3. Ce n'en est pas une contradiction mais une exception, portée par
l'extension — et c'est l'une des raisons pour lesquelles Tasks n'est pas dans le cœur (bloc 18.6).
Conséquence pratique : si l'état vit en mémoire, un redémarrage du serveur perd les tâches en cours.
C'est acceptable pour ce lab, à condition de le savoir et de le dire à l'utilisateur.

**Trois issues, pas deux.** Terminé et échoué viennent naturellement ; annulé s'oublie. Un client
qui ne gère pas le troisième cas affiche une tâche éternellement « en cours ». Le socle attend que
le **client** sache traiter les trois statuts, `cancelled` compris ; que le serveur sache lui-même
annuler (`tasks/cancel`) reste une extension (voir Extension A).

**L'erreur -32021.** *Missing Required Client Capability* : le serveur la renvoie quand il ne peut
pas honorer la requête sans l'extension Tasks, avec `requiredCapabilities`. C'est une erreur
JSON-RPC — elle va au client, pas au modèle.

**Ne pas ajouter de paramètre `async`.** C'est exactement la faute que le bloc 18.2 vient de
traiter, et elle réapparaît dans la moitié des implémentations spontanées.

**Vérifier à vitesse réelle.** Le mode rapide sert à itérer. Un cycle qui fonctionne en douze
secondes ne prouve rien sur ce que voit un utilisateur pendant deux minutes — et c'est précisément
ce que mesure le critère décisif.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_ops/` — recalcul en tâche, progression réelle, plan B |
| **Consigné** | `labs/lab11/observations.md` — ce que voit l'utilisateur, minute par minute |
| **Artefact du fil rouge** | **A11**, consommé par OR3 |
| **Checkpoint** | `etat/is3-fin` |

```bash
make lab11-verifier
git add serveurs/pharos_ops/ client/ labs/lab11/ && git commit -m "LAB 11 — recalcul en Tasks"
```

**Mise en commun (5 min).** Une seule question : qu'a vu l'utilisateur à la quatre-vingt-dixième
seconde ? Les réponses iront de « rien » à « 18 escales sur 24, quai 5 en cours », et l'écart
n'est pas technique — il tient entièrement à ce qui a été décidé à l'étape 2.

**Suite.** Le module **SR3** traite l'autre interruption : non plus un appel qui dure, mais un appel
qui **ne peut pas se terminer** parce qu'il manque une décision humaine. Publier une alerte à
l'exploitant est irréversible — cran 4 du curseur d'autonomie posé au module FA1 — et c'est
l'élicitation via MRTR qui permet de la demander sans session ni connexion tenue.
