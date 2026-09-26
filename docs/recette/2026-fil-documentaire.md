# Recette — fil documentaire et fil protocole (LAB 1 à 7)

Complète `2026-socle-lab0.md`. ✅ = vérifié par la CI (job `solutions`) ; 👁 = à constater par le formateur.

## Parcours de bout en bout (formateur, une fois, ~1 h)

1. Clone neuf du dépôt, `.env` d'un binôme de test (`PHAROS_BINOME=9`), `make construire && make up`.
2. Pour N = 1 à 7 : `make depart LAB=N` → la branche `binome-9-labNN` est créée ; `make labN-verifier SANS_MODELE=1` sur le **squelette** affiche des ❌ qui disent quoi faire.
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
| 6 | Chaque échec initial rattaché à un anti-patron | `labs/lab6/diagnostic.md` ; le vérificateur rappelle les questions ratées (référence : `etat/sr1-fin`) |
| 6 | Chaque gain attribué à une modification nommée | `labs/lab6/attribution.md` ; le vérificateur rappelle les questions gagnées |
| 6 | Mise en commun : deux chiffres et une phrase par binôme | en salle ; comparer les taux de `avant.md` et `apres.md` |
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
| 6 | google/gemini-3.6-flash | banc 5 × 3 : catalogue fourni (spike : 3 passages ; recette : 2 passages), catalogue de référence | fourni : 3/5 · 3/5 · 3/5 (spike), 3/5 · 3/5 (recette) ; Q4 et Q5 ratées · référence : 5/5 (spike), 5/5 (recette) · coût recette 0,0595 $ | 2026-09-26 |

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

### Détail — mesure LAB 6 (google/gemini-3.6-flash)

Décision (2026-09-26, validée par le formateur) : les paramètres de `pharos-quai` sont opaques (`d`,
`f`, `x`, `id`, `q`, `h`). Avec des noms parlants, le catalogue fourni obtenait 4/5 sur Gemini 3.6
Flash comme sur GPT-5.4 mini : le critère décisif du brief (« au moins deux questions ») devenait
inatteignable. Seuil §12 amendé : au moins deux questions ratées au départ. La marge est nulle : le
binôme doit gagner les questions 4 et 5, les seules ratées.

Mesures de référence (consignées dans `solutions/lab06/labs/lab6/`) : `avant.md` 3/5, `apres.md`
5/5. Passages de la recette (2026-09-26) : ci-dessous, les tableaux de `sortie/lab6-fourni-1.md`,
`sortie/lab6-fourni-2.md` et `sortie/lab6-reference.md`.

Si un binôme plafonne à 4/5 avant réécriture (variance du modèle, cf. la décision I2 du 2026-09-26),
le vérificateur le signale au lieu de conseiller de reprendre le diagnostic : au formateur de décider,
sans remesurer `avant.md`.

```text
## Mesure LAB 6 — premier appel

Modèle : google/gemini-3.6-flash · 3 exécution(s) par question

| # | Question | Attendu | Exécution 1 | Exécution 2 | Exécution 3 | Taux |
|---|---|---|---|---|---|---|
| 1 | Quelles escales sont prévues aujourd'hui ? | get_data | ✅ get_data(d=2026-10-06) | ✅ get_data(d=2026-10-06) | ✅ get_data(d=2026-10-06) | 3/3 |
| 2 | Quel est le tirant d'eau maximal du quai 3 ? | info_quai | ✅ info_quai(id=3) | ✅ info_quai(id=3) | ✅ info_quai(id=3) | 3/3 |
| 3 | Le Vent d'Autan a-t-il un créneau jeudi matin ? | search | ✅ search(q=Vent d'Autan, d=2026-10-08) | ✅ search(d=2026-10-08, q=Vent d'Autan) | ✅ search(q=Vent d'Autan, d=2026-10-08) | 3/3 |
| 4 | Quelles escales sont prévues au quai 3 demain ? | get_data_2 | ❌ get_data(d=2026-10-07) | ❌ get_data(d=2026-10-07) | ❌ get_data(d=2026-10-07) | 0/3 |
| 5 | À quelle heure le Vent d'Autan peut-il accoster jeudi ? | process | ❌ search(d=2026-10-08, q=Vent d'Autan) | ❌ search(q=Vent d'Autan, d=2026-10-08) | ❌ search(d=2026-10-08, q=Vent d'Autan) | 0/3 |

Questions réussies (majorité des exécutions) : 3/5
Tokens : 3519 en entrée, 5162 en sortie · coût : 0.0220 $

Noms : catalogue d'origine (aucun outil renommé)
```

```text
## Mesure LAB 6 — premier appel

Modèle : google/gemini-3.6-flash · 3 exécution(s) par question

| # | Question | Attendu | Exécution 1 | Exécution 2 | Exécution 3 | Taux |
|---|---|---|---|---|---|---|
| 1 | Quelles escales sont prévues aujourd'hui ? | get_data | ✅ get_data(d=2026-10-06) | ✅ get_data(d=2026-10-06) | ✅ get_data(d=2026-10-06) | 3/3 |
| 2 | Quel est le tirant d'eau maximal du quai 3 ? | info_quai | ✅ info_quai(id=3) | ✅ info_quai(id=3) | ✅ info_quai(id=3) | 3/3 |
| 3 | Le Vent d'Autan a-t-il un créneau jeudi matin ? | search | ✅ search(d=2026-10-08, q=Vent d'Autan) | ✅ search(d=2026-10-08, q=Vent d'Autan) | ✅ search(q=Vent d'Autan, d=2026-10-08) | 3/3 |
| 4 | Quelles escales sont prévues au quai 3 demain ? | get_data_2 | ❌ get_data(d=2026-10-07) | ❌ get_data(d=2026-10-07) | ❌ get_data(d=2026-10-07) | 0/3 |
| 5 | À quelle heure le Vent d'Autan peut-il accoster jeudi ? | process | ❌ search(d=2026-10-08, q=Vent d'Autan) | ❌ search(q=Vent d'Autan, d=2026-10-08) | ❌ search(d=2026-10-08, q=Vent d'Autan) | 0/3 |

Questions réussies (majorité des exécutions) : 3/5
Tokens : 3519 en entrée, 4502 en sortie · coût : 0.0195 $

Noms : catalogue d'origine (aucun outil renommé)
```

```text
## Mesure LAB 6 — premier appel

Modèle : google/gemini-3.6-flash · 3 exécution(s) par question

| # | Question | Attendu | Exécution 1 | Exécution 2 | Exécution 3 | Taux |
|---|---|---|---|---|---|---|
| 1 | Quelles escales sont prévues aujourd'hui ? | escales_du_jour | ✅ escales_du_jour(d=2026-10-06) | ✅ escales_du_jour(d=2026-10-06) | ✅ escales_du_jour(d=2026-10-06) | 3/3 |
| 2 | Quel est le tirant d'eau maximal du quai 3 ? | caracteristiques_quai | ✅ caracteristiques_quai(id=3) | ✅ caracteristiques_quai(id=3) | ✅ caracteristiques_quai(id=3) | 3/3 |
| 3 | Le Vent d'Autan a-t-il un créneau jeudi matin ? | creneaux_du_navire | ✅ creneaux_du_navire(d=2026-10-08, q=Le Vent d'Autan) | ✅ creneaux_du_navire(d=2026-10-08, q=Le Vent d'Autan) | ✅ creneaux_du_navire(d=2026-10-08, q=Vent d'Autan) | 3/3 |
| 4 | Quelles escales sont prévues au quai 3 demain ? | escales_du_quai | ✅ escales_du_quai(f=3, d=2026-10-07) | ✅ escales_du_quai(f=3, d=2026-10-07) | ✅ escales_du_quai(f=3, d=2026-10-07) | 3/3 |
| 5 | À quelle heure le Vent d'Autan peut-il accoster jeudi ? | heure_accostage | ✅ heure_accostage(x=Vent d'Autan, d=2026-10-08) | ✅ heure_accostage(x=Vent d'Autan, d=2026-10-08) | ✅ heure_accostage(d=2026-10-08, x=Vent d'Autan) | 3/3 |

Questions réussies (majorité des exécutions) : 5/5
Tokens : 8964 en entrée, 2994 en sortie · coût : 0.0180 $

Noms : check → creneau_libre, get_data → escales_du_jour, get_data_2 → escales_du_quai, info_quai → caracteristiques_quai, process → heure_accostage, search → creneaux_du_navire
```

## Vérifications du §16 de la spec

- `extends` entre fichiers Compose : ✅ (Task 1).
- Client fastmcp `mode="legacy"` contre un serveur écrit à la main : ✅ (plan 2, Task 2 : poignée de
  main, session, `GET` → 405, `DELETE` ; `mode="auto"` se replie après un 400 sur `server/discover`).
- mitmweb relaie `X-Pharos-Instance` : constaté sur `localhost:8201` (plan 1, Task 12) et sur
  `localhost:8204` (plan 2, Task 8).
- VS Code affiche un prompt MCP : 👁 LAB 7.
