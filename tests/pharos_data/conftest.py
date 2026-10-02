"""Fixtures de la suite de pharos-data (LAB 9) : un client en mémoire, sous une identité donnée.

Sans modèle, sans réseau vers l'extérieur : le serveur tourne dans le processus du test, contre
pharos-db (lancer « make lab8-base » avant). Si la base ne répond pas, les tests sont sautés, avec un message.

    async def test_…(client_en_tant_que):
        async with client_en_tant_que("jeton-rance") as c:
            r = await c.call_tool("escales_a_risque", {"date": "2026-10-08"})
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import asyncpg
import pytest
from fastmcp import Client

from pharos import autorisation, base


def _base_joignable() -> bool:
    async def essayer():
        try:
            connexion = await asyncpg.connect(base.dsn("pharos_app"), timeout=3)
        except (OSError, asyncpg.PostgresError, asyncio.TimeoutError):
            return False
        await connexion.close()
        return True

    return asyncio.run(essayer())


def pytest_collection_modifyitems(config, items):
    miens = [item for item in items if "pharos_data" in item.nodeid]
    if miens and not _base_joignable():
        saut = pytest.mark.skip(reason="pharos-db injoignable : lancer « make lab8-base »")
        for item in miens:
            item.add_marker(saut)


@pytest.fixture
def client_en_tant_que():
    """Rend une fabrique : « async with client_en_tant_que(jeton) as c » — le client porte l'identité du jeton."""
    from serveurs.pharos_data.serveur import mcp

    @asynccontextmanager
    async def ouvrir(jeton: str):
        with autorisation.en_tant_que(jeton):
            async with Client(mcp) as client:      # ouvert DANS le bloc : le serveur hérite de l'identité
                yield client

    return ouvrir
