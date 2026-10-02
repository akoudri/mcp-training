"""Fixtures de la suite de pharos-docs — fournies, avec les signatures justes du SDK épinglé (fastmcp 4.0.10).

Transport mémoire : Client(mcp) parle au serveur dans le même processus. Ni HTTP, ni modèle, ni réseau.
"""

import pytest
from fastmcp import Client

from serveurs.pharos_docs.serveur import mcp


@pytest.fixture(autouse=True)
def cle_serveur(monkeypatch):
    monkeypatch.setenv("CLE_SERVEUR", "cle-de-test")


@pytest.fixture
async def client():
    async with Client(mcp) as c:
        yield c
