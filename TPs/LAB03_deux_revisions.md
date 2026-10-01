# LAB 3 — Un déploiement, deux révisions

**Module PR5** · durée 1 h 15
**Artefact produit** : **A3** — test de double compatibilité de révision
**Checkpoint de sortie** : `etat/pr5-fin`

---

## Contexte

Au LAB 2, `pharos-legacy` a été migré vers 2026-07-28. Franchement, sans compatibilité ascendante.

Sauf que le service d'exploitation portuaire n'a pas migré ses clients. Deux applications internes
continuent d'appeler ce serveur en 2025-11-25, et leurs équipes ont d'autres priorités jusqu'à la
fin du trimestre. Couper n'est pas une option ; attendre non plus.

Ce lab fait servir **les deux révisions depuis un seul déploiement**. C'est la mise en œuvre directe
du bloc 7.2 — et l'occasion d'appliquer, sur un cas réel, l'arbitrage entre sur-ensemble et
adaptation du même bloc.

**Répartition indicative du temps** : 10 min de repérage · 25 min d'aiguillage · 25 min pour les
deux divergences · 15 min de preuve et de compteur.

---

## Prérequis

| | |
|---|---|
| **Modules** | PR4, PR5 (blocs 7.1 à 7.4) |
| **Labs** | LAB 2 |
| **Artefacts consommés** | **A2** — `pharos-legacy` migré |
| **Fourni** | client de test 2025-11-25, module `compat` avec la poignée de main réactivable, répartiteur à deux instances |

```bash
make depart LAB=3        # branche binome-<B>-lab03 depuis etat/pr3-fin, module compat et constat
make lab3-clients        # démarre les deux clients de test, en 2025-11-25 et 2026-07-28
```

Le module `compat` fourni contient la **mécanique** de la poignée de main 2025-11-25 —
`initialize`, `initialized`, gestion d'un `Mcp-Session-Id`. Elle est fournie écrite : vous l'avez
démontée au LAB 2, la remonter n'apprendrait rien de neuf. Le travail porte sur l'aiguillage et sur
les deux divergences.

### Les deux divergences à traiter

| | 2025-11-25 | 2026-07-28 | Nature |
|---|---|---|---|
| `page_suivante` | sans argument, curseur en session | prend un handle en argument | **incompatible** |
| Résultat d'appel | contenu textuel seul | contenu textuel + `structuredContent` | **additive** |

C'est exactement la distinction du bloc 7.2. Chacune appelle une stratégie différente, et le lab
consiste largement à s'en apercevoir.

---

## SOCLE — pour tous

### Étape 1 — Repérer, avant de coder

Lancer les deux clients contre le serveur tel qu'il est. Consigner dans `labs/lab3/constat.md` :

- ce que reçoit le client 2025-11-25, et à quel moment exact il échoue ;
- ce que reçoit le client 2026-07-28 ;
- quelle information, dans la requête, permet de distinguer les deux ;
- ce qui se passe quand un client récent atteint un serveur ancien (le cas symétrique).

### Étape 2 — L'aiguillage

Faire en sorte que le serveur détermine, **requête par requête**, à quelle révision il répond, et
réactive la poignée de main fournie par `compat` pour les clients anciens.

Contrainte structurante : **une seule implémentation métier, deux adaptateurs**. Le code qui lit les
mouvements de conteneurs ne doit exister qu'une fois.

Après cette étape, `etat_escale` doit répondre aux deux clients.

### Étape 3 — Les deux divergences

**`page_suivante` — incompatible, donc adaptation.** Le client ancien appelle sans argument et
attend que le serveur retrouve son curseur ; le client récent passe un handle. Produire la forme qui
correspond à la révision demandée. Le curseur de session ne doit exister **que** pour les clients
anciens, et ne jamais fuiter dans une réponse 2026-07-28.

**Le résultat d'appel — additif, donc sur-ensemble.** Renvoyer les deux formes. Un client
2025-11-25 ignore ce qu'il ne connaît pas.

### Étape 4 — La preuve, et le compteur

```bash
make lab3-deux-instances
make lab3-verifier
```

Produire deux traces Inspector côte à côte, depuis **le même déploiement**, montrant les deux
clients servis. Ajouter la journalisation de la révision demandée, une ligne par requête.

Écrire le test qui garantit la double compatibilité : une exécution par révision, sur les trois
outils, sans intervention manuelle. C'est l'artefact **A3**, repris en intégration continue au
module EX1.

### Critères de réussite

- [ ] Le constat de l'étape 1 est écrit, et nomme le point de rupture exact du client ancien.
- [ ] Les deux clients obtiennent une réponse correcte à `etat_escale`.
- [ ] Les deux clients obtiennent une réponse correcte à `lister_mouvements` **puis**
      `page_suivante`.
- [ ] Le code métier de lecture des mouvements n'existe qu'en un seul exemplaire.
- [ ] Aucun handle n'apparaît dans une réponse servie à un client 2025-11-25.
- [ ] La révision demandée est journalisée à chaque requête.
- [ ] Le test de double compatibilité (artefact A3) s'exécute sur les trois outils, une fois par
      révision, sans intervention manuelle.
- [ ] **Critère décisif** — les deux traces Inspector proviennent du même processus, et le test
      passe également derrière le répartiteur à deux instances, configuré avec affinité de session
      (`make lab3-deux-instances`).

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — La mise en échec volontaire du test

Casser volontairement le test de double compatibilité écrit au socle (artefact A3) — par exemple en
supprimant la réactivation de la poignée de main — et vérifier que **le rapport d'échec désigne la
révision fautive**, et pas seulement « un test rouge ». Un test qui échoue sans dire lequel des deux
mondes est cassé ne sert à rien en astreinte.

### B — Le tableau de bord de migration

À partir de la journalisation de l'étape 4, produire le chiffre qui décide : combien de requêtes par
révision, sur les dernières 24 heures, et par client identifié.

C'est le compteur du bloc 7.3. Répondre à la question qu'il sert à trancher : **à quelle condition
aurait-on le droit de retirer le support 2025-11-25 ?**

### C — Le prix du sur-ensemble

Mesurer ce que coûte, en tokens, le fait de renvoyer les deux formes de résultat à tous les clients,
y compris ceux qui ont migré :

```bash
make lab3-cout-surensemble
```

Puis se poser la question honnêtement : à partir de quelle proportion de clients migrés
l'adaptation deviendrait-elle rentable, y compris sur ce cas additif ?

---

## Pièges & indices

**Le piège majeur : deux serveurs dans un fichier.** La tentation, en découvrant les divergences,
est de dupliquer le gestionnaire d'outil et d'aiguiller vers l'un ou l'autre. Cela fonctionne, et
double le coût de toute évolution métier ultérieure. Une implémentation, deux adaptateurs — la
divergence se traite au bord, jamais au centre.

**La détection par absence est une heuristique, pas une règle.** Un client 2025-11-25 n'envoie pas
`io.modelcontextprotocol/protocolVersion` dans `_meta`, et il est tentant d'en conclure « pas de
`_meta`, donc ancien ». Cela
marche en salle et se retourne en production le jour où un client récent malformé arrive. Quand la
poignée de main a eu lieu, c'est elle qui fait foi.

**Le handle ne doit pas fuiter vers un client ancien.** Il ne saurait qu'en faire, et surtout il
finirait dans le contexte du modèle sans raison. Vérifier explicitement l'absence de la chaîne
`hdl_` dans les réponses servies en 2025-11-25.

**Ne pas tester les deux révisions avec le même client.** Changer une variable d'environnement et
relancer, c'est tester sa propre configuration. Les deux clients fournis sont réellement distincts :
utiliser les deux.

**`server/discover` reste obligatoire.** Il n'existait pas en 2025-11-25, ce qui donne l'impression
qu'on peut le retirer « puisqu'on gère l'ancien monde ». Non : le serveur reste non conforme à
2026-07-28 sans lui. C'est la règle du bloc 5.3, et elle ne se négocie pas au nom de la
compatibilité.

**Le sur-ensemble n'est pas la solution par défaut.** Il ne casse rien, donc il rassure. Appliqué à
une divergence incompatible, il produit un résultat que ni l'un ni l'autre des clients ne comprend
correctement. Le tableau des deux divergences en haut de ce document est un arbitrage, pas une
description.

**Le test qui passe sur une instance.** L'erreur de fin de lab : tout est vert en local, et le
répartiteur du LAB 2 n'a pas été rebranché. Le curseur de session des clients anciens vit
forcément quelque part — vérifier ce qui se passe quand deux requêtes d'un même client ancien
atterrissent sur deux instances, et **écrire ce qu'on en conclut**, même si on ne le corrige pas
aujourd'hui.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_legacy/` servant les deux révisions, une seule implémentation métier |
| **Consigné** | `labs/lab3/constat.md`, et les deux traces Inspector |
| **Artefact du fil rouge** | **A3** — le test de double compatibilité, repris au module EX1 |
| **Checkpoint** | `etat/pr5-fin` |

```bash
make lab3-verifier
git add serveurs/ labs/lab3/ && git commit -m "LAB 3 — double compatibilité de révision"
```

**Suite.** La famille protocole est close. À partir du module **OR1**, le sujet change de côté :
jusqu'ici vous avez écrit et migré des serveurs, en laissant un client fourni les interroger. Vous
allez maintenant écrire ce client — la boucle agentique elle-même — et tous les serveurs des jours
suivants seront exercés par lui.

**Dernier point de vigilance.** Le curseur de session que ce lab réintroduit pour les clients
anciens est, littéralement, l'état que le module PR3 a expliqué comment supprimer. Ce n'est pas une
contradiction : c'est le prix de la compatibilité, il est temporaire, et le compteur de l'extension B
est ce qui dit quand on a le droit de le payer moins longtemps. Le répartiteur du LAB 3 est
d'ailleurs configuré avec affinité de session : sans elle, le client ancien casse dès sa première
requête servie par l'autre instance. C'est précisément le prix de l'état conservé.
