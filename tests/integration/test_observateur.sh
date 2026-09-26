#!/usr/bin/env bash
# Vérifie que le trafic MCP traverse l'observateur, dans les deux ordres de démarrage.
set -euo pipefail
cd "$(dirname "$0")/../.."
lister() {
  docker compose -f compose.yaml -f compose/lab0.yaml run --rm atelier python - <<'EOF'
import asyncio
from fastmcp import Client
async def main():
    async with Client("http://observateur:8100/mcp") as c:
        noms = sorted(o.name for o in await c.list_tools())
        assert noms == ["lire_document", "lister_documents", "rechercher_clause"], noms
        r = await c.call_tool("lister_documents", {"escale_id": "ESC-2026-0412"})
        assert len(r.data["documents"]) == 4
        print("OK", noms)
asyncio.run(main())
EOF
}
# 502 = observateur prêt mais serveur absent ; 4xx = le serveur répond (requête vide refusée) : prêt.
attendre() { for _ in $(seq 30); do curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8100/mcp | grep -qE '^4' && return 0; sleep 1; done; return 1; }

make down >/dev/null 2>&1 || true
make up && make lab0-up && attendre && lister
echo "--- ordre inverse : serveur d'abord, observateur ensuite (make lab0-up démarre les deux : on passe par compose)"
make down && docker compose -f compose.yaml -f compose/lab0.yaml up -d pharos-docs-demo && make up && attendre && lister
echo "--- ports réservés : 502 tant que leur serveur n'existe pas"
for p in 8101 8102 8103 8104 8105; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "localhost:$p/mcp")
  echo "port $p : $code"; [ "$code" = 502 ]
done
curl -s -o /dev/null -w "UI observateur : %{http_code}\n" localhost:7001
