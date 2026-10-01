"""Empreintes du contexte d'évaluation (LAB 15) : la base, le catalogue agrégé, le prompt système, le modèle.

Une empreinte est un condensé court (16 caractères hexadécimaux) : deux exécutions du jeu ne se comparent que si
leurs empreintes sont égales. Elles servent le contexte figé du harnais (la base) et la chaîne (le catalogue, le
prompt et le modèle : ses trois déclencheurs).

    await empreinte_base(dsn)                   # les lignes des tables métier, triées : stable d'un chargement à l'autre
    empreinte_catalogue(catalogues)             # {serveur: [outils fastmcp ou dicts]} → noms, descriptions, schémas
    empreinte_prompt(Path("client/pharos_client/consigne.md"))
    empreinte_modele()                          # PHAROS_MODELE, ou le modèle par défaut — en clair, pas condensé
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from pharos.openrouter import MODELE_DEFAUT

LONGUEUR = 16


def condenser(donnees) -> str:
    texte = json.dumps(donnees, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:LONGUEUR]


async def empreinte_base(dsn: str) -> str:
    """Condensé des tables métier (schéma public), lignes triées. Ni séquence ni horodatage de chargement n'y
    entrent : la base n'en a pas ; une ligne qui change change l'empreinte."""
    import asyncpg

    connexion = await asyncpg.connect(dsn)
    try:
        tables = [l["table_name"] for l in await connexion.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name")]
        contenu = {}
        for table in tables:
            lignes = await connexion.fetch(f'SELECT to_jsonb(t)::text AS l FROM "{table}" t')
            contenu[table] = sorted(l["l"] for l in lignes)
    finally:
        await connexion.close()
    return condenser(contenu)


def _outil(o) -> dict:
    if isinstance(o, dict):
        return {"name": o["name"], "description": o.get("description") or "", "inputSchema": o.get("inputSchema") or {}}
    return {"name": o.name, "description": o.description or "", "inputSchema": o.input_schema or {}}


def empreinte_catalogue(catalogues: dict[str, list]) -> str:
    """Le catalogue agrégé tel que le modèle le voit : un outil renommé, une description retouchée, un schéma
    changé — l'empreinte change. L'ordre des serveurs et des outils n'y entre pas."""
    return condenser(sorted((_outil(o) for outils in catalogues.values() for o in outils), key=lambda d: d["name"]))


def empreinte_prompt(chemin: Path) -> str:
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()[:LONGUEUR]


def empreinte_modele() -> str:
    return os.environ.get("PHAROS_MODELE") or MODELE_DEFAUT
