# LAB 2 — Autopsie protocolaire et migration

**Module PR3** · durée 1 h 15
**Artefact produit** : **A2** — `pharos-legacy` migré vers 2026-07-28
**Checkpoint de sortie** : `etat/pr3-fin`

---

## Contexte

PHAROS n'a pas commencé cette semaine. L'équipe d'exploitation dispose déjà d'un serveur MCP écrit
il y a un an, `pharos-legacy`, qui expose les mouvements de conteneurs. Il fonctionne, il est en
production, et il parle la révision **2025-11-25**.

Ce lab le fait basculer vers 2026-07-28. Le travail n'est pas cosmétique : ce serveur conserve un
curseur de pagination **dans la session**. Retirer la session sans réfléchir le casse. C'est
précisément le cas que le bloc 5.5 prépare.

**Ce que ce lab n'est pas.** On ne cherche pas ici à servir les deux révisions depuis un même
déploiement : c'est le sujet du LAB 3, au module PR5. Ici, on migre, franchement, sans compatibilité
ascendante.

**Répartition indicative du temps** : 15 min d'inventaire · 25 min de migration mécanique ·
20 min pour le curseur · 15 min de preuve et mise en commun.

---

## Prérequis

| | |
|---|---|
| **Modules** | PR3 (blocs 5.1 à 5.5) |
| **Labs** | LAB 0, LAB 1 |
| **Artefacts consommés** | A0 (environnement) |
| **Fourni** | `pharos-legacy` en 2025-11-25, grille d'inventaire, répartiteur à deux instances |

```bash
make depart LAB=2         # branche binome-<B>-lab02 depuis etat/pr2-fin, et la grille d'inventaire
make lab2-legacy          # démarre pharos-legacy tel quel, en 2025-11-25
make lab2-fixtures
```

### Ce que fait `pharos-legacy`

| Outil | Rôle |
|---|---|
| `etat_escale(escale_id)` | Quai, créneau, tirant d'eau, statut |
| `lister_mouvements(escale_id)` | Première page des mouvements de conteneurs |
| `page_suivante()` | **Page suivante, à partir du curseur conservé dans la session** |

Le troisième outil est le nœud du lab. Prendre le temps de lire son implémentation avant de
toucher à quoi que ce soit.

---

## SOCLE — pour tous

### Étape 1 — L'inventaire des ruptures

Sans rien modifier, lire le code et le trafic, puis remplir `labs/lab2/inventaire.md` (grille
fournie) :

| Rupture | Où elle se manifeste | Ce qu'il faut faire |
|---|---|---|
| Poignée de main `initialize` / `initialized` | | |
| En-tête `Mcp-Session-Id` | | |
| `server/discover` absent | | |
| État conservé côté serveur | | |
| Code d'erreur `-32002` | | |

Le code `-32002` est à consigner, pas à traiter aujourd'hui : il est repris au module PR5 avec le
reste de la liste de migration.

### Étape 2 — La migration mécanique

1. Retirer la poignée de main. Le serveur ne doit plus attendre d'échange préalable.
2. Supprimer toute lecture de `Mcp-Session-Id`. Lire la révision et les capacités du client dans
   `_meta`, requête par requête.
3. Implémenter `server/discover`, même minimalement : identité, révision servie, capacités.
4. Contrôler que les en-têtes `Mcp-Method` et `Mcp-Name` disent la même chose que le corps, et
   sinon refuser la requête (HTTP 400, erreur `HeaderMismatchError`, code -32020) : ils servent au
   routage, ils ne prouvent rien.

Après cette étape, `etat_escale` doit fonctionner. `page_suivante` sera cassé — c'est attendu.

### Étape 3 — Le curseur qui n'a plus de session où vivre

Remplacer le curseur de session par un **handle explicite**, selon le bloc 5.5 :

- `lister_mouvements` renvoie la première page **et** un handle.
- `page_suivante(handle)` prend le handle en argument ordinaire et renvoie la page suivante avec un
  nouveau handle.
- Le handle est **opaque, signé, daté, expirant**, et porte la portée : il vaut pour une escale et
  pour un appelant, pas au-delà.

### Étape 4 — La preuve

```bash
make lab2-deux-instances     # deux instances derrière un répartiteur, sans stockage partagé
make lab2-verifier
```

Enchaîner `lister_mouvements` puis `page_suivante` à travers le répartiteur. Les deux requêtes
atterrissent sur des instances différentes. Ouvrir l'Inspector et vérifier le trafic.

### Critères de réussite

- [ ] La grille d'inventaire est remplie, les cinq ruptures identifiées.
- [ ] Aucun `Mcp-Session-Id` ne circule dans le trafic, dans aucun sens.
- [ ] Aucun échange `initialize` / `initialized` ne précède le premier appel utile.
- [ ] `server/discover` répond, et annonce la révision `2026-07-28`.
- [ ] `Mcp-Method` et `Mcp-Name` sont présents sur chaque requête et portent les bonnes valeurs.
- [ ] Un handle expiré ou altéré d'un caractère est refusé, avec une erreur métier.
- [ ] **Critère décisif** — `lister_mouvements` puis `page_suivante` fonctionnent à travers le
      répartiteur à deux instances, sans stockage partagé.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Filtrer en périphérie, sans ouvrir le corps

Écrire un proxy minimal placé devant `pharos-legacy`, qui refuse tout appel à un outil absent d'une
liste d'autorisation.

**Contrainte** : la décision se prend sur le seul en-tête `Mcp-Name`. Le proxy ne doit jamais
désérialiser le corps JSON — le vérifier en le faisant échouer volontairement sur une requête au
corps illisible mais aux en-têtes corrects.

Puis, la question qui compte : forger une requête dont l'en-tête `Mcp-Name` annonce `etat_escale`
et dont le corps appelle `page_suivante`. Que fait le proxy ? Que devrait faire le serveur ?

*C'est la démonstration de la mise en garde du bloc 5.4 : ces en-têtes déclarent, ils ne prouvent
pas.*

### B — Mesurer la contrepartie

Le bloc 5.1 annonce que les requêtes grossissent. Le mesurer plutôt que le croire :

```bash
make lab2-taille-requetes    # avant / après, en octets
```

Comparer sur une conversation de dix tours. Estimer ce que la mise en cache du catalogue (bloc 4.4)
récupérerait sur ce même échantillon.

### C — Faire tomber une instance

Pendant qu'une pagination est en cours, arrêter l'instance qui a servi la première page. Vérifier
que `page_suivante` continue de fonctionner.

C'est la démonstration la plus directe de ce que le cœur sans état achète.

---

## Pièges & indices

**Le dictionnaire en mémoire est le piège central.** Le réflexe, en retirant la session, est de
garder côté serveur un dictionnaire indexé par client ou par escale. Cela marche parfaitement sur
une instance, et casse à la seconde. Si l'étape 4 échoue, c'est presque toujours là. Le protocole
n'interdit pas de stocker : il interdit d'en dépendre pour répondre.

**Un handle non signé n'est pas un handle, c'est un identifiant.** Le vérifier en incrémentant la
valeur reçue : si l'on obtient les mouvements d'une autre escale, le travail n'est pas fini.
Signer, dater, et refuser tout ce qui ne se vérifie pas.

**Un handle lisible est un handle qui fuit.** Signé, il ne se forge pas ; lisible, il se lit. Tout
ce qu'il contient finit dans le contexte, les journaux et les tickets. Pour l'opacité, chiffrer
(AEAD) ou n'y mettre que du non sensible.

**`server/discover` s'oublie parce que tout marche sans lui.** Aucun des clients utilisés en salle
ne l'appelle. Le serveur reste pourtant non conforme, et c'est le premier point que relèvera un
test de conformité. C'est la moitié de la règle qu'on oublie, vue au bloc 5.3.

**Le client met en cache la liste des outils.** Après modification de la signature de
`page_suivante`, redémarrer le client, sinon il enverra l'ancienne forme.

**Ne pas chercher la compatibilité ascendante ici.** Faire répondre le serveur aux deux révisions
est un travail réel, et c'est le LAB 3. Le tenter maintenant coûte vingt minutes et brouille le
critère de réussite.

**L'inventaire avant le clavier.** L'étape 1 semble être du temps perdu ; elle est ce qui distingue
une migration d'un bricolage. Les binômes qui ouvrent l'éditeur en premier repassent
systématiquement par l'inventaire à mi-parcours, après avoir cassé `page_suivante` sans comprendre
pourquoi.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_legacy/` migré, avec handle signé |
| **Consigné** | `labs/lab2/inventaire.md` — la grille des cinq ruptures |
| **Artefact du fil rouge** | **A2**, consommé par PR5 |
| **Checkpoint** | `etat/pr3-fin` |

```bash
make lab2-verifier
git add serveurs/pharos_legacy/ labs/lab2/ && git commit -m "LAB 2 — migration 2026-07-28"
```

**Suite.** Le module **PR4** complète le tableau : les transports, les notifications, et la liste
datée de ce qui est déprécié. Puis **PR5** reprendra ce même serveur pour lui poser la question que
ce lab a délibérément écartée — comment continuer à servir les clients qui, eux, n'ont pas migré.
