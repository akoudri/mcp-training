# Ports de PHAROS

Tous les ports sont publiés sur 127.0.0.1 uniquement : un voisin de salle ne peut pas les joindre.

Tout serveur MCP écoute sur le port interne 8000 (`/mcp`) et n'est joint **qu'à travers l'observateur**.

| Port poste | Service | Depuis le réseau Compose |
|---|---|---|
| 7001 | Inspector — observateur de trafic (mot de passe `pharos`) | `observateur:8081` |
| 7002 | Inspector officiel (`make inspector-client`) | — |
| 8100 | pharos-docs-demo (LAB 0) — VS Code s'y connecte via `http://localhost:8100/mcp` | `observateur:8100` |
| 8101 | pharos-docs (réservé, LAB 1+) | `observateur:8101` |
| 8102 | pharos-data (réservé, LAB 8+) | `observateur:8102` |
| 8103 | pharos-ops (réservé, LAB 10+) | `observateur:8103` |
| 8104 | pharos-legacy (réservé, LAB 2+) | `observateur:8104` |
| 8105 | pharos-quai (réservé, LAB 6) | `observateur:8105` |
| 82xx | répartiteurs à deux instances (réservé) | `observateur:82xx` |
