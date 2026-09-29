# LAB 7 — `pharos-docs` v1

**Modules SR2 et TQ1** · durée 1 h 45
**Artefact produit** : **A7** — `pharos-docs v1` : ressources, prompt serveur, suite de tests
**Checkpoint de sortie** : `etat/tq1-fin`

---

## Contexte

`pharos-docs` a beaucoup grandi : trois outils au LAB 1, une session d'analyse à handles au LAB 5,
un catalogue révisé au LAB 6. Il n'a toujours aucun test.

Ce lab produit sa version 1, en trois passes qui ne se séparent pas : convertir ce qui doit l'être
en **ressources**, sortir le gabarit de note d'alerte du client pour en faire un **prompt serveur**,
et écrire la **suite de tests** qui rend tout cela modifiable sans peur.

**Le point qui surprendra.** Le LAB 1 interdisait d'exposer le texte intégral d'un contrat. Ce lab
l'expose — en ressource. Ce n'est pas une contradiction : le contenu est identique, mais c'est
désormais l'hôte qui décide de l'attacher, et la taille est annoncée avant toute lecture. Même
contenu, autre primitive, autre profil de risque.

**Répartition indicative du temps** : 25 min pour les ressources · 20 min pour le prompt serveur ·
40 min pour la suite de tests · 10 min pour passer sous le seuil · 10 min de vérification par la
boucle.

---

## Prérequis

| | |
|---|---|
| **Modules** | SR1, SR2 (11.1 à 11.3), TQ1 (12.1 à 12.5) |
| **Labs** | LAB 1, LAB 4, LAB 5 |
| **Artefacts consommés** | **A1** + **A5** — `pharos-docs` et ses handles · **A4** — `pharos-client` |
| **Fourni** | squelette de tests avec les signatures justes du SDK épinglé, contrat de 80 pages, compteur de tokens |

```bash
make depart LAB=7         # branche binome-<B>-lab07 depuis etat/sr1-fin, squelette pytest du SDK épinglé
make lab7-fixtures        # dont un contrat de 80 pages, stable
```

> Le squelette donne la forme exacte de `Client(mcp)`, des assertions et des fixtures asynchrones
> pour la version de SDK épinglée. S'y fier, plutôt qu'au code du bloc 12.2 qui est illustratif.

---

## SOCLE — pour tous

### Étape 1 — Les documents deviennent des ressources

| Avant | Après |
|---|---|
| `lister_documents(escale_id)` — un outil | `resources/list` — les documents d'escale, avec URI, type et **taille** |
| — | `resources/read(uri)` — le contenu, quand l'hôte le demande |

URI retenu : `pharos://escales/{escale_id}/documents/{document_id}`.

Trois exigences :

- la **taille** annoncée dans `resources/list` doit être juste — c'est sur elle que l'hôte décide
  d'attacher ou de proposer ;
- le `mimeType` doit être juste, pour la même raison ;
- `lister_documents` **disparaît du catalogue**.

Relever le coût en tokens du catalogue avant et après, dans `labs/lab7/mesures.md`.

**Conséquence à traiter** : la boucle du LAB 4 appelait `lister_documents`. Elle doit maintenant
lister les ressources et décider lesquelles attacher. C'est du travail côté client, et il est dans
le socle.

### Étape 2 — Le prompt serveur

Sortir le gabarit de note d'alerte du code de l'agent, et l'exposer :

```
prompts/list  →  { "name": "note_alerte_escale",
                   "title": "Note d'alerte à l'exploitant",
                   "arguments": [ { "name": "escale_id", "required": true },
                                  { "name": "niveau",    "required": false } ] }
```

`prompts/get` renvoie les messages, et **y joint la ressource du contrat** plutôt que d'en recopier
le texte.

Vérifier depuis un client graphique réel : le prompt doit apparaître à l'utilisateur, et être
déclenchable par lui. Ce n'est pas un outil que le modèle appelle.

### Étape 3 — La suite de tests

En transport mémoire, sans modèle. Couvrir les six familles applicables à `pharos-docs` (le
cloisonnement vient au LAB 9, la double compatibilité a été traitée au LAB 3) :

| Famille | Cas attendus |
|---|---|
| Schémas | `sujet` hors énumération refusé avant le code métier |
| Erreurs métier | Escale inconnue, contrat absent, sujet absent — les trois du LAB 1 |
| Formes et bornes | `rechercher_clause` renvoie un extrait borné, jamais le contrat entier |
| Handles | Expiré, altéré d'un caractère, hors portée — les trois du LAB 5 |
| Ressources | `resources/list` annonce la bonne taille et le bon type ; `resources/read` répond |
| Empreinte | Le catalogue est comparé à `tests/empreinte_catalogue.json` |

### Étape 4 — Passer sous le seuil

```bash
make lab7-tests CHRONO=1
```

Objectif : **moins de dix secondes**, sans modèle, sans réseau, sans sous-processus. Si la suite est
plus lente, chercher d'abord une fixture qui se régénère, un `sleep`, ou un test qui est passé par
HTTP sans qu'on le veuille.

### Étape 5 — Vérifier par la boucle

Reposer, via `pharos-client`, la question de référence du LAB 1 :

> Quelles sont les pénalités de retard prévues au contrat de manutention de l'escale ESC-2026-0412 ?

Vérifier que la réponse reste correcte après tous ces changements, et relever le contexte consommé.

### Critères de réussite

- [ ] Les documents sont exposés en ressources ; `lister_documents` a disparu du catalogue.
- [ ] La taille et le `mimeType` annoncés sont justes.
- [ ] Le coût du catalogue est mesuré avant et après.
- [ ] Le prompt serveur est proposé à l'utilisateur par un client réel, et déclenchable par lui.
- [ ] La suite couvre les six familles applicables.
- [ ] L'empreinte de catalogue est en place — et **échoue** si l'on renomme un outil. Le vérifier une
      fois, puis remettre le nom.
- [ ] **Critère décisif** — la suite est verte et tourne en **moins de dix secondes**, sans appeler
      aucun modèle.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — La pagination sur un contrat de 80 pages

Ajouter la pagination à `resources/read`, puis vérifier via la boucle du LAB 4 que **le contexte
consommé cesse de croître linéairement** avec la taille du document.

Deux chiffres à comparer : le contexte final, et le nombre de tours. Si le second explose, la
pagination est trop fine — c'est le même arbitrage qu'à l'extension B du LAB 5.

### B — Le seul test de bout en bout

Le transport mémoire ne teste pas le transport. Écrire **un** test, un seul, qui démarre le serveur
en HTTP et effectue un appel complet.

Il sera lent, et c'est acceptable : il n'a pas à tourner à chaque enregistrement. Le placer dans une
cible séparée, pour qu'il ne contamine pas le seuil des dix secondes.

### C — Versionner le prompt

L'exploitant veut changer la structure de la note d'alerte, et deux clients utilisent encore
l'ancienne.

Publier `note_alerte_escale_v2`, garder l'ancien, et écrire son plan de dépréciation — les cinq
lignes du bloc 7.4 du module PR5. Une page maximum.

---

## Pièges & indices

**Convertir en ressource ne veut pas dire tout attacher.** Vérifier explicitement que l'hôte ne
colle pas quatre-vingts pages dans le contexte par défaut. C'est la faute n° 2 du bloc 8.2, et elle
devient plus facile à commettre après ce lab qu'avant.

**Retirer un outil casse le client.** La boucle du LAB 4 appelait `lister_documents`. Si elle n'est
pas adaptée, l'agent perd la capacité de savoir quels documents existent — et le symptôme est une
réponse plausible mais inventée, pas une erreur. C'est dans le socle pour cette raison.

**Une taille annoncée fausse est pire qu'une taille absente.** L'hôte décide sur elle. Si elle est
approximative, il attachera ce qu'il aurait dû proposer, ou l'inverse.

**Un `await` oublié donne un test vert qui ne teste rien.** C'est l'erreur la plus fréquente sur des
tests asynchrones, et elle ne se voit pas : le test passe. Vérifier au moins une fois qu'un test
censé échouer échoue réellement.

**Une fixture qui se régénère invalide l'empreinte.** Si le contrat de test est reconstruit à chaque
exécution, les tailles bougent et l'empreinte de catalogue devient rouge sans raison. Les fixtures
sont versionnées, pas générées.

**L'empreinte qui passe au rouge est un succès.** C'est ce qu'on lui demande. La bonne réaction est
de mettre à jour le fichier dans le même commit, pour que la revue de code voie le contrat changer.
La mauvaise est de la désactiver.

**Ne pas remettre le gabarit dans le client « pour aller plus vite ».** C'est exactement ce que le
bloc 11.3 décrit comme la dette qu'on paie au troisième client.

**Ne pas tester à travers HTTP.** C'est lent, non déterministe, et cela ne teste rien de plus — sauf
le transport lui-même, qui relève de l'extension B et d'un test unique.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_docs/` — ressources, prompt serveur · `tests/` — la suite |
| **Modifié** | `client/pharos_client/` — la boucle liste et attache les ressources |
| **Consigné** | `labs/lab7/mesures.md` — coût du catalogue avant/après, durée de la suite |
| **Artefact du fil rouge** | **A7**, consommé par OR3, SG1 et EX2 |
| **Checkpoint** | `etat/tq1-fin` |

```bash
make lab7-tests CHRONO=1
git add serveurs/ client/ tests/ labs/lab7/ && git commit -m "LAB 7 — pharos-docs v1"
```

**Mise en commun (5 min).** Deux chiffres par binôme : le gain sur le coût du catalogue, et la durée
de la suite. Le second est le plus intéressant — l'écart entre les postes dit presque toujours qu'un
test est resté branché sur quelque chose qu'il n'aurait pas dû toucher.

**Suite.** Le module **DA1** ouvre la journée des données. `pharos-data` est un serveur d'un autre
genre : ce qu'il expose n'est plus un corpus documentaire mais une base relationnelle, et la
question devient « comment donner accès à une base sans donner la base ».

Tout ce qui a été appris ici — bornes, ressources, tests sans modèle — s'y applique directement, et
le cloisonnement viendra compléter la liste des familles testables.
