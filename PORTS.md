# Ports de PHAROS

Tous les ports sont publiés sur 127.0.0.1 uniquement : un voisin de salle ne peut pas les joindre.

Tout serveur MCP écoute sur le port interne 8000 (`/mcp`) et n'est joint **qu'à travers l'observateur**.

L'observateur déclare dès le LAB 0 les ports 8100 à 8105, 8201 et 8204 : les ports 8101 à 8105, 8201 et 8204 sont réservés et répondent **502** tant que leur serveur n'est pas démarré (ou n'existe pas encore). Un 502 sur 8100 signifie donc « `make lab0-up` oublié », pas « observateur en panne ».

| Port poste | Service | Depuis le réseau Compose |
|---|---|---|
| 7001 | Inspector — observateur de trafic (mot de passe `pharos`) | `observateur:8081` |
| 7002 | Inspector officiel (`make inspector-client`) | — |
| 8100 | pharos-docs-demo (LAB 0) — VS Code s'y connecte via `http://localhost:8100/mcp` | `observateur:8100` |
| 8101 | pharos-docs (réservé, LAB 1+) | `observateur:8101` |
| 8102 | pharos-data (LAB 8, 9) | `observateur:8102` |
| 8103 | pharos-ops (réservé, LAB 10+) | `observateur:8103` |
| 8104 | pharos-legacy, une instance (LAB 2, 3) | `observateur:8104` |
| 8105 | pharos-quai (LAB 6) | `observateur:8105` |
| 8201 | répartiteur de pharos-docs, deux instances (LAB 5) | `observateur:8201` |
| 8204 | répartiteur de pharos-legacy, deux instances (LAB 2 sans affinité, LAB 3 avec) | `observateur:8204` |
| 5433 | pharos-db, base PHAROS (LAB 8 à 12) — PostgreSQL 17, utilisateur `postgres`, mot de passe de salle `pharos-salle-2026` ; jamais 5432, souvent pris sur le poste | `pharos-db:5432` |
