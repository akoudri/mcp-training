"""make tokens-catalogue — ce que coûtent les seules définitions d'outils, avant toute question."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass

import tiktoken

ENCODAGE = tiktoken.get_encoding("o200k_base")
URL_DEFAUT = "http://observateur:8100/mcp"


@dataclass(frozen=True)
class MesureOutil:
    nom: str
    total: int
    description: int
    proprietes: int
    enums: int


def _t(texte: str) -> int:
    return len(ENCODAGE.encode(texte))


def mesurer(outils: list) -> list[MesureOutil]:
    mesures = []
    for o in outils:
        schema = o.input_schema or {}
        definition = {"name": o.name, "description": o.description or "", "parameters": schema}
        props = schema.get("properties", {})
        mesures.append(MesureOutil(
            nom=o.name,
            total=_t(json.dumps(definition, ensure_ascii=False)),
            description=_t(o.description or ""),
            proprietes=sum(_t(p.get("description", "")) for p in props.values()),
            enums=sum(_t(json.dumps(p["enum"], ensure_ascii=False)) for p in props.values() if "enum" in p),
        ))
    return mesures


async def mesurer_serveur(cible) -> list[MesureOutil]:
    from fastmcp import Client
    async with Client(cible) as c:
        return mesurer(await c.list_tools())


def formater(mesures: list[MesureOutil]) -> str:
    lignes = ["Coût du catalogue en tokens — approximation (encodage o200k_base ; chaque modèle découpe à sa façon)", "",
              f"  {'outil':<26}{'total':>7}{'description':>13}{'propriétés':>12}{'enum':>7}"]
    for m in sorted(mesures, key=lambda m: -m.total):
        lignes.append(f"  {m.nom:<26}{m.total:>7}{m.description:>13}{m.proprietes:>12}{m.enums:>7}")
    lignes += ["", f"  Total : {sum(m.total for m in mesures)} tokens pour {len(mesures)} outils, "
                   f"payés à chaque tour de la boucle."]
    return "\n".join(lignes)


if __name__ == "__main__":
    print(formater(asyncio.run(mesurer_serveur(sys.argv[1] if len(sys.argv) > 1 else URL_DEFAUT))))
