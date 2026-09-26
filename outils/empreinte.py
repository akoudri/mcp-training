"""make lab7-empreinte — fige le catalogue de pharos-docs dans tests/empreinte_catalogue.json.

L'empreinte qui passe au rouge est un succès : mettre le fichier à jour DANS LE MÊME COMMIT que le
changement de catalogue, pour que la revue voie le contrat changer.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client

CHEMIN = Path("tests/empreinte_catalogue.json")


def empreinte(outils) -> list[dict]:
    return sorted(({"name": o.name, "description": o.description or "", "inputSchema": o.input_schema or {}}
                   for o in outils), key=lambda d: d["name"])


async def empreinte_de(serveur) -> list[dict]:
    async with Client(serveur) as c:
        return empreinte(await c.list_tools())


def serialiser(e: list[dict]) -> str:
    return json.dumps(e, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    from serveurs.pharos_docs.serveur import mcp

    chemin = Path(argv[0]) if argv else CHEMIN
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(serialiser(asyncio.run(empreinte_de(mcp))), encoding="utf-8")
    print(f"Empreinte écrite : {chemin}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
