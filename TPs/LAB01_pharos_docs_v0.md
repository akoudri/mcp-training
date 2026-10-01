# LAB 1 — `pharos-docs` v0

**Module PR2** · durée 1 h 30 · premier serveur écrit par les participants
**Artefact produit** : **A1** — `pharos-docs` v0
**Checkpoint de sortie** : `etat/pr2-fin`

---

## Contexte

Les agents maritimes déposent chaque jour des documents rattachés aux escales : contrats de
manutention, connaissements, avis d'escale. Aujourd'hui, l'exploitant les ouvre à la main.

Ce lab produit le premier des trois serveurs de PHAROS : celui qui expose ces documents à un agent.
C'est aussi la première ligne de code du fil rouge — tout ce qui suit s'y raccrochera.

**Ce que ce lab n'est pas.** Ce n'est pas un exercice d'analyse documentaire. La couche
d'extraction PDF est fournie, écrite et testée. Le travail porte entièrement sur la frontière :
quels outils exposer, avec quels schémas, et que renvoyer quand ça ne marche pas.

**Répartition indicative du temps** : 15 min de prise en main · 45 min pour les trois outils ·
20 min pour les erreurs et les tests · 10 min de mise en commun.

---

## Prérequis

| | |
|---|---|
| **Modules** | PR1, PR2 (blocs 4.1 à 4.4) |
| **Labs** | LAB 0 |
| **Artefacts consommés** | A0 (environnement) |
| **Fourni** | couche d'extraction, squelette de serveur, jeu de documents, cinq questions de test |

```bash
make depart LAB=1         # branche binome-<B>-lab01 depuis etat/fa2-fin, et le squelette du SDK épinglé
make lab1-fixtures        # documents d'escale + base de test
```

### La couche d'extraction fournie

Module `pharos_docs.extraction`, à utiliser tel quel :

```python
documents_de_escale(escale_id: str) -> list[Document]
texte_du_document(document_id: str) -> list[Page]
rechercher_dans_texte(pages: list[Page], motif: str) -> list[Occurrence]
```

`Document` porte `document_id`, `type` (`contrat_manutention`, `connaissement`, `avis_escale`),
`escale_id`, `nb_pages`. `Occurrence` porte `page`, `texte`, `score`.

Les identifiants d'escale ont la forme `ESC-AAAA-NNNN`. Le jeu de test contient huit escales, dont
`ESC-2026-0412` (le *Vent d'Autan*, jeudi).

### Le squelette

```python
from fastmcp import FastMCP
from pharos_docs import extraction

mcp = FastMCP("pharos-docs")

@mcp.tool
def lister_documents(escale_id: str) -> dict:
    """..."""
    ...

if __name__ == "__main__":
    mcp.run()
```

Le décorateur exact et la signature de `run()` dépendent de la version de SDK épinglée : se fier au
squelette créé par `make depart LAB=1`, pas à ce qui est écrit ici.

---

## SOCLE — pour tous

### Étape 1 — Trois outils

Exposer exactement ces trois outils, et rien d'autre :

| Outil | Entrées | Ce qu'il renvoie |
|---|---|---|
| `lister_documents` | `escale_id` | Les documents rattachés à l'escale : identifiant, type, nombre de pages |
| `rechercher_clause` | `escale_id`, `sujet` | Le texte de la clause et son numéro de page |
| `extraire_dates_contractuelles` | `escale_id` | Les dates du contrat de manutention : signature, prise d'effet, échéance |

Contraintes :

- `sujet` est une **énumération** : `penalites`, `delais`, `manutention`, `assurance`. Pas une
  chaîne libre.
- `escale_id` porte une **description de format** dans le schéma. Le modèle ne devinera pas
  `ESC-AAAA-NNNN` tout seul.
- Chaque description d'outil tient en une ou deux phrases, et dit **à quoi l'outil sert**, pas
  comment il est écrit.

### Étape 2 — Des erreurs dont le modèle peut faire quelque chose

Trois situations à traiter, toutes en **erreur métier** (`isError`), jamais en exception qui
remonte :

| Situation | Ce que le message doit contenir |
|---|---|
| Escale inconnue | Le format attendu, et le nom de l'outil qui donne la liste |
| Aucun contrat de manutention pour cette escale | Ce qui existe à la place, d'après `lister_documents` |
| Sujet demandé absent du contrat | Les sujets effectivement présents dans ce contrat |

Le critère est celui du bloc 4.3 : un message d'erreur est un prompt. Écrire ce qu'on voudrait que
le modèle fasse au tour suivant.

### Étape 3 — Les cinq questions de test

Le fichier `labs/lab1/questions.md` est fourni. Les poser au client, dans l'ordre, en repartant
d'une conversation vierge à chaque fois — sauf la question 4, posée dans la même conversation que la
question 3. Consigner le résultat.

| | Question | Attendu |
|---|---|---|
| 1 | Quels documents sont rattachés à l'escale ESC-2026-0412 ? | `lister_documents` |
| 2 | Quelle est la pénalité de retard au contrat de manutention du *Vent d'Autan* ? | `rechercher_clause`, sujet `penalites` |
| 3 | À quelle date expire le contrat de l'escale ESC-2026-0412 ? | `extraire_dates_contractuelles` |
| 4 | *(à la suite de la question 3)* Y a-t-il une clause d'assurance dans ce contrat ? | `rechercher_clause`, sujet `assurance` |
| 5 | Quelle est la pénalité pour l'escale ESC-2026-9999 ? | **erreur métier**, et le modèle explique |

La question 2 ne mentionne pas l'identifiant d'escale mais le nom du navire. Elle est là exprès :
observer ce que fait le modèle, et ne pas corriger le serveur pour cela — le sujet est traité au
module SR1.

La question 4 ne nomme pas l'escale : « ce contrat » est celui de la question 3. Posée dans une
conversation vierge, elle n'a pas de réponse possible, et un bon modèle demande de quel contrat il
s'agit ; posée à la suite, elle vérifie que le modèle réutilise l'identifiant déjà connu.

### Critères de réussite

- [ ] Les trois outils apparaissent dans `tools/list`, avec leurs schémas.
- [ ] `sujet` est une énumération ; une valeur hors énumération est refusée avant d'atteindre le
      code métier — sous la forme d'un résultat `isError: true` (erreur métier, depuis SEP-1303 /
      2025-11-25), pas d'une erreur protocolaire.
- [ ] Les questions 1, 3 et 4 déclenchent le bon outil **sans reformulation humaine**.
- [ ] La question 5 produit une erreur métier exploitable : aucune trace de pile, aucun plantage du
      serveur, et le modèle reformule ou propose une alternative.
- [ ] Aucun outil ne renvoie le texte intégral d'un document.
- [ ] Le résultat de la question 2 est consigné tel quel, y compris s'il est mauvais.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Un quatrième outil qui rattrape le tour précédent

Ajouter `lister_escales(date)`, et faire en sorte que **le message d'erreur de la question 5 le
nomme explicitement**. Reposer la question 5 : le modèle doit enchaîner de lui-même sur
`lister_escales`, puis reformuler.

Deux tours, aucune intervention humaine. C'est la démonstration concrète de « un message d'erreur
est un prompt ».

### B — Une question volontairement ambiguë

> Donne-moi les délais.

Sans escale, sans contexte. Observer : le modèle invente-t-il un `escale_id`, demande-t-il une
précision, ou appelle-t-il l'outil avec un argument vide ?

Modifier ensuite la description de `rechercher_clause` pour rendre l'identifiant d'escale
manifestement obligatoire, et reposer la question. Noter la différence de comportement.

*C'est le premier contact avec le mécanisme d'élicitation, qui sera traité pour de bon au module
SR3.*

### C — Rendre le catalogue cacheable

Le bloc 4.4 pose une condition : l'ordre du listage doit être déterministe. Vérifier que dix appels
consécutifs à `tools/list` renvoient les outils dans le même ordre, et corriger si ce n'est pas le
cas.

Vérifier de même que `lister_documents` trie ses résultats de manière stable, et pas selon l'ordre
de parcours du système de fichiers.

---

## Pièges & indices

**Ne pas exposer `texte_du_document` en outil.** C'est la tentation immédiate, et elle coûte cher :
un contrat de manutention fait 40 à 80 pages. Un seul appel sature le contexte et rend tous les
tours suivants plus mauvais. Les outils renvoient des extraits, pas des documents.

**Un identifiant que le modèle ne peut pas connaître n'a rien à faire en paramètre d'entrée.**
`rechercher_clause(document_id, ...)` semble plus propre que `rechercher_clause(escale_id, ...)`,
mais le modèle n'a aucun moyen d'obtenir un `document_id` sans appeler d'abord `lister_documents`.
C'est le mode d'échec n° 2 du bloc 2.3, provoqué par une décision de conception.

**Une exception non rattrapée devient une erreur protocolaire.** Elle arrête la boucle au lieu de
laisser le modèle se corriger. Tout ce qui relève de la donnée absente se renvoie en résultat, avec
`isError`.

**La description n'est pas de la documentation d'API.** « Recherche une clause en utilisant
l'index inversé construit au démarrage » ne dit rien d'utile au modèle. « Recherche une clause dans
le contrat de manutention d'une escale » lui dit quand appeler l'outil.

**Le client met en cache la liste des outils.** Après ajout ou modification d'un outil, redémarrer
le client. Un outil invisible n'est pas nécessairement un outil cassé.

**Les énumérations coûtent des tokens et les valent.** Quatre valeurs de `sujet`, c'est une
vingtaine de tokens payés à chaque tour, contre un modèle qui invente `retards`, `penalty` ou
`late_fees` à chaque essai.

**Ne pas soigner la mise en forme du résultat.** Le réflexe de renvoyer une belle phrase française
est contre-productif : le modèle reformulera de toute façon, et une structure lui est plus utile
qu'une prose. La question est traitée au module OR2.

**La question 2 est un piège assumé.** Le modèle doit relier « *Vent d'Autan* » à `ESC-2026-0412`,
ce que rien dans le serveur ne lui permet de faire. Si elle échoue, c'est normal, et c'est le point
de départ du module SR1. Ne pas ajouter d'outil pour la sauver.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_docs/` — trois outils, schémas stricts, erreurs métier |
| **Consigné** | `labs/lab1/resultats.md` — les cinq questions et ce qui s'est réellement passé |
| **Artefact du fil rouge** | **A1**, consommé par PR3, OR1 et SR1 |
| **Checkpoint** | `etat/pr2-fin` |

```bash
make lab1-verifier            # relève le premier appel des cinq questions et contrôle les critères
git add serveurs/ labs/lab1/ && git commit -m "LAB 1 — pharos-docs v0"
```

**Suite.** Le module **PR3** prendra ce serveur et posera une question qu'il ne se pose pas encore :
que se passe-t-il si deux requêtes consécutives atterrissent sur deux instances différentes ?
Depuis la révision 2026-07-28, la réponse doit être « rien de particulier » — et le LAB 2 le
vérifiera sur un serveur écrit pour la révision précédente.
