# Recette — assemblage, sécurité, évaluation (LAB 13 à 15)

Complète `2026-donnees-externes.md`. Sous-projet 4, plans 1 à 3.
✅ = vérifié par la CI (job `solutions`) ; 👁 = à constater par le formateur.

## L'agent complet en salle (LAB 13)

- `make lab13-tout` démarre la base, les mocks et les trois serveurs derrière l'observateur (8101, 8102, 8103).
  La base n'est pas rechargée : `make lab8-base` d'abord si elle est vide (le départ du lab le fait).
- La boucle lit `labs/lab13/serveurs.json` : trois serveurs, le jeton `jeton-exploitation` pour pharos-data et
  pharos-ops. `PHAROS_JETON`, s'il est posé, prime sur la configuration (le LAB 14 change ainsi d'identité).
- La collision de départ : le module navires (`serveurs/pharos_data/navires.py`, fourni) s'enregistre par défaut
  sous `navire_par_nom`, que pharos-ops expose déjà. Elle n'apparaît qu'au catalogue agrégé
  (`make lab13-catalogue`) ; la boucle de référence refuse un catalogue ambigu (`CollisionDeNoms`). Correction
  attendue : `navires.enregistrer(mcp, emprunter, nom_outil="data_navire_par_nom")`. L'extension B mesure la
  collision avant de la corriger (`make lab13-banc` : un client naïf, où le dernier serveur écrase l'autre).
- `make lab13-question` pose la question avec le vrai modèle et garde l'exécution dans `labs/lab13/execution.json`
  (question, plan, réponse, trace — secrets masqués) : c'est ce fichier, commité, que relisent
  `make lab13-verifier-note`, `make lab13-derive` et le critère décisif du vérificateur.
- Le vérificateur de note accepte un nombre obtenu par une seule opération sur deux nombres d'un **même** appel
  (la marge 13,5 − 12,9) ; il refuse une combinaison entre deux appels (une coïncidence probable) et ne vérifie
  pas les noms hors de la liste du kit (navires, armateurs, agents).

## La vue du plan de quai (LAB 13, étape 4) 👁

1. `make lab13-tout`, puis `mkdir -p .vscode && cp labs/lab13/client.config.json .vscode/mcp.json`.
2. VS Code (`make client`), chat en mode agent **PHAROS** (`.github/agents/pharos.agent.md` : les outils des
   quatre serveurs PHAROS, rien d'autre) ; réglage `chat.mcp.apps.enabled` actif (valeur par défaut).
3. Demander : « Recalcule le plan de placement à quai de jeudi 8 octobre pour le quai 3. »
4. Attendu : la réponse texte, et sous elle le diagramme des sept quais — le *Vent d'Autan* en rouge (à décaler :
   coup de vent de 34 kt), hachures sur le quai 3.

La vue reçoit le résultat de l'outil par `postMessage` (JSON-RPC, spécification MCP Apps 2026-01-26 :
`ui/initialize`, puis `ui/notifications/tool-result`). Si elle ne s'affiche pas, le socle reste atteignable par la
réponse texte (brief, étape 4) ; noter la version de VS Code dans cette recette.
