# Recette — fil documentaire et fil protocole (LAB 1 à 5, 7)

Complète `2026-socle-lab0.md`. ✅ = vérifié par la CI (job `solutions`) ; 👁 = à constater par le formateur.

## Parcours de bout en bout (formateur, une fois, ~1 h)

1. Clone neuf du dépôt, `.env` d'un binôme de test (`PHAROS_BINOME=9`), `make construire && make up`.
2. Pour N = 1, 2, 3, 4, 5, 7 : `make depart LAB=N` → la branche `binome-9-labNN` est créée ; `make labN-verifier SANS_MODELE=1` sur le **squelette** affiche des ❌ qui disent quoi faire.
3. Rattrapage : `git switch --detach origin/etat/<sortie de N>` puis `make labN-verifier` → aucun ❌.

## Critères à constater (👁)

| Lab | Critère | Comment le constater |
|---|---|---|
| 1 | Q5 : le modèle reformule | VS Code, mode PHAROS, question 5 |
| 1 | Q2 consignée telle quelle | `labs/lab1/resultats.md` du binôme |
| 2 | Grille des cinq ruptures remplie | `labs/lab2/inventaire.md` (référence : `etat/pr3-fin`) |
| 3 | Constat de l'étape 1 : point de rupture exact du client ancien | `labs/lab3/constat.md` (référence : `etat/pr5-fin`) |
| 3 | Le code métier n'existe qu'une fois | le vérificateur affiche le nombre de lectures des mouvements (attendu 1) |
| 3 | Deux traces Inspector, même processus | Inspector, port 8204 : mêmes `X-Pharos-Instance` pour les deux clients |
| 3 | Sans affinité, ce qui casse | dernier 👁 de `make lab3-verifier` ; le binôme le consigne dans `constat.md` |
| 4 | Mesures consignées | `labs/lab4/mesures.md` |
| 4 | Critère décisif : trace lisible par le voisin | échange de traces en salle |
| 5 | Charge justifiée | `labs/lab5/charge.md` (référence : `etat/or2-fin`) |
| 5 | Contexte mesuré | `labs/lab5/mesures.md` |
| 7 | Prompt proposé et déclenchable dans VS Code | taper « / » dans le chat |
| 7 | Six familles couvertes | relecture de `tests/pharos_docs/` |

Pour le LAB 7, le critère « l'empreinte échoue si l'on renomme un outil » n'est **pas** à constater
par le formateur : il est automatique (vérifié par la CI). Le vérificateur contrôle la suite de
référence sur une copie intacte du dépôt, puis modifie le nom d'un outil dans une copie **séparée**
de l'empreinte et vérifie que cette mutation la fait échouer.

## Étalonnage avec le modèle

| Lab | Modèle | Protocole | Résultat | Date |
|---|---|---|---|---|
| 1 | google/gemini-3.6-flash | banc 5 × 3 sur la solution | Q1 3/3 · Q2 consignée (cf. Détail) · Q3 3/3 · Q4 0/3 hors contexte → 3/3 dans la conversation de Q3 (réétalonnage) · Q5 3/3 (isError) · coût 0,0259 $ | 2026-09-26 |

Décision (2026-09-27, validée par le formateur) : la question 4 se pose **dans la même conversation
que la question 3** — le brief du LAB 1 et `labs/lab1/questions.md` le disent ; le banc rejoue ce tour
(`contexte:` dans `outils/questions/lab1.yaml`) et le critère juge de nouveau les questions 1, 3 et 4.
Réétalonnage de Q4 dans ce protocole (banc 1 × 3 sur la solution, 2026-09-27) : **3/3**,
`rechercher_clause(escale_id=ESC-2026-0412, sujet=assurance)` → Article 8 — Assurance ; coût 0,0027 $.
Le premier passage ci-dessous (Q4 0/3, question posée hors contexte) est conservé pour mémoire.

### Détail — banc LAB 1 (google/gemini-3.6-flash)

Q4 (« Y a-t-il une clause d'assurance dans ce contrat ? ») échoue systématiquement (0/3, aucun appel
d'outil) : le banc du premier appel interroge chaque question dans une conversation neuve, sans le
contexte des questions précédentes ; « ce contrat » ne désigne donc aucune escale connue du modèle,
qui ne peut pas fournir l'`escale_id` obligatoire de `rechercher_clause`. Ce n'est pas un défaut des
descriptions d'outils ni du serveur — c'est la limite du protocole mono-tour du banc face à une
question qui suppose un fil de conversation. Aucune itération (Step 3) n'a donc été tentée sur cette
question.

```
## Étalonnage LAB 1

Modèle : google/gemini-3.6-flash · 3 exécution(s) par question

| # | Question | Attendu | Exécution 1 | Exécution 2 | Exécution 3 | Taux |
|---|---|---|---|---|---|---|
| 1 | Quels documents sont rattachés à l'escale ESC-2026-0412 ? | lister_documents | ✅ lister_documents(escale_id=ESC-2026-0412) | ✅ lister_documents(escale_id=ESC-2026-0412) | ✅ lister_documents(escale_id=ESC-2026-0412) | 3/3 |
| 2 | Quelle est la pénalité de retard au contrat de manutention du Vent d'Autan ? | rechercher_clause | 👁 lister_documents(escale_id=ESC-2026-0412) | 👁 lister_documents(escale_id=ESC-2026-0412) | 👁 rechercher_clause(sujet=penalites, escale_id=ESC-2026-0412) | consignée |
| 3 | À quelle date expire le contrat de l'escale ESC-2026-0412 ? | extraire_dates_contractuelles | ✅ extraire_dates_contractuelles(escale_id=ESC-2026-0412) | ✅ extraire_dates_contractuelles(escale_id=ESC-2026-0412) | ✅ extraire_dates_contractuelles(escale_id=ESC-2026-0412) | 3/3 |
| 4 | Y a-t-il une clause d'assurance dans ce contrat ? | rechercher_clause | ❌ aucun appel | ❌ aucun appel | ❌ aucun appel | 0/3 |
| 5 | Quelle est la pénalité pour l'escale ESC-2026-9999 ? | rechercher_clause | ✅ rechercher_clause(sujet=penalites, escale_id=ESC-2026-9999) | ✅ rechercher_clause(sujet=penalites, escale_id=ESC-2026-9999) | ✅ rechercher_clause(escale_id=ESC-2026-9999, sujet=penalites) | 3/3 |

Premier appel exécuté :
- Q1 : succès — {"escale_id":"ESC-2026-0412","documents":[{"document_id":"AE-0412","type":"avis_escale","nb_pages":1},{"document_id":"BL-0412-1","type":"connaissement","nb_pages":2},{"document_id":"BL-0412-2","type":
- Q1 : succès — {"escale_id":"ESC-2026-0412","documents":[{"document_id":"AE-0412","type":"avis_escale","nb_pages":1},{"document_id":"BL-0412-1","type":"connaissement","nb_pages":2},{"document_id":"BL-0412-2","type":
- Q1 : succès — {"escale_id":"ESC-2026-0412","documents":[{"document_id":"AE-0412","type":"avis_escale","nb_pages":1},{"document_id":"BL-0412-1","type":"connaissement","nb_pages":2},{"document_id":"BL-0412-2","type":
- Q2 : succès — {"escale_id":"ESC-2026-0412","documents":[{"document_id":"AE-0412","type":"avis_escale","nb_pages":1},{"document_id":"BL-0412-1","type":"connaissement","nb_pages":2},{"document_id":"BL-0412-2","type":
- Q2 : succès — {"escale_id":"ESC-2026-0412","documents":[{"document_id":"AE-0412","type":"avis_escale","nb_pages":1},{"document_id":"BL-0412-1","type":"connaissement","nb_pages":2},{"document_id":"BL-0412-2","type":
- Q2 : succès — {"document_id":"CM-0412","article":"Article 7 — Pénalités de retard","page":7,"texte":"Tout retard imputable à l'opérateur portuaire au-delà d'une franchise de 6 heures donne lieu au versement\nà l'ar
- Q3 : succès — {"document_id":"CM-0412","page":11,"signature":"2026-03-02","prise_effet":"2026-04-01","echeance":"2027-03-31"}
- Q3 : succès — {"document_id":"CM-0412","page":11,"signature":"2026-03-02","prise_effet":"2026-04-01","echeance":"2027-03-31"}
- Q3 : succès — {"document_id":"CM-0412","page":11,"signature":"2026-03-02","prise_effet":"2026-04-01","echeance":"2027-03-31"}
- Q5 : isError — Escale inconnue : ESC-2026-9999. Le format attendu est ESC-AAAA-NNNN (par exemple ESC-2026-0412). Vérifier l'identifiant auprès de l'utilisateur ; lister_documents donne les documents d'une escale exi
- Q5 : isError — Escale inconnue : ESC-2026-9999. Le format attendu est ESC-AAAA-NNNN (par exemple ESC-2026-0412). Vérifier l'identifiant auprès de l'utilisateur ; lister_documents donne les documents d'une escale exi
- Q5 : isError — Escale inconnue : ESC-2026-9999. Le format attendu est ESC-AAAA-NNNN (par exemple ESC-2026-0412). Vérifier l'identifiant auprès de l'utilisateur ; lister_documents donne les documents d'une escale exi

Questions réussies (majorité des exécutions) : 3/4
Tokens : 5226 en entrée, 5865 en sortie · coût : 0.0259 $
```

## Vérifications du §16 de la spec

- `extends` entre fichiers Compose : ✅ (Task 1).
- Client fastmcp `mode="legacy"` contre un serveur écrit à la main : ✅ (plan 2, Task 2 : poignée de
  main, session, `GET` → 405, `DELETE` ; `mode="auto"` se replie après un 400 sur `server/discover`).
- mitmweb relaie `X-Pharos-Instance` : constaté sur `localhost:8201` (plan 1, Task 12) et sur
  `localhost:8204` (plan 2, Task 8).
- VS Code affiche un prompt MCP : 👁 LAB 7.
