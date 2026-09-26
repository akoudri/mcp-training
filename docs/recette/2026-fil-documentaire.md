# Recette — fil documentaire (LAB 1, 4, 5, 7)

Complète `2026-socle-lab0.md`. ✅ = vérifié par la CI (job `solutions`) ; 👁 = à constater par le formateur.

## Parcours de bout en bout (formateur, une fois, ~1 h)

1. Clone neuf du dépôt, `.env` d'un binôme de test (`PHAROS_BINOME=9`), `make construire && make up`.
2. Pour N = 1, 4, 5, 7 : `make depart LAB=N` → la branche `binome-9-labNN` est créée ; `make labN-verifier SANS_MODELE=1` sur le **squelette** affiche des ❌ qui disent quoi faire.
3. Rattrapage : `git switch --detach origin/etat/<sortie de N>` puis `make labN-verifier` → aucun ❌.

## Critères à constater (👁)

| Lab | Critère | Comment le constater |
|---|---|---|
| 1 | Q5 : le modèle reformule | VS Code, mode PHAROS, question 5 |
| 1 | Q2 consignée telle quelle | `labs/lab1/resultats.md` du binôme |
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
| 1 | google/gemini-3.6-flash | banc 5 × 3 sur la solution | à remplir (Task 15) | |

## Vérifications du §16 de la spec

- `extends` entre fichiers Compose : ✅ (Task 1).
- Client fastmcp `mode="legacy"` : vérifié contre un serveur fastmcp en `json_response` (Task 4),
  fonctionne ; contre un serveur écrit à la main : plan 2.
- mitmweb relaie `X-Pharos-Instance` : constaté à la Task 12 (4 requêtes curl sur
  `localhost:8201`, alternance a/b).
- VS Code affiche un prompt MCP : 👁 LAB 7.
