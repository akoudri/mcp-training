import json

import pytest

from outils import client_test
from outils.client_test import ClientTest
from tests.aides import serveur_demo, servir


@pytest.fixture
def url():
    with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
        yield f"{base}/mcp"


async def test_revision_recente_sans_session(url):
    async with ClientTest(url, "2026-07-28") as c:
        r = await c.appeler("etat", {"escale_id": "ESC-2026-0412"})
    assert not r.is_error and r.data["quai"] == 3
    methodes = [e.methode_mcp for e in c.echanges]
    assert "initialize" not in methodes and "tools/call" in methodes
    assert all("mcp-session-id" not in {k.lower() for k in e.entetes_requete} for e in c.echanges)
    appel = next(e for e in c.echanges if e.methode_mcp == "tools/call")
    assert appel.entetes_requete["mcp-method"] == "tools/call"
    assert appel.entetes_requete["mcp-name"] == "etat"
    assert appel.statut == 200 and json.loads(appel.corps_reponse)["result"]["structuredContent"]["quai"] == 3


async def test_revision_ancienne_poignee_de_main(url):
    async with ClientTest(url, "2025-11-25") as c:
        await c.appeler("etat", {"escale_id": "ESC-2026-0412"})
    assert c.echanges[0].methode_mcp == "initialize"


async def test_erreur_metier_sans_exception(url):
    async with ClientTest(url) as c:
        r = await c.appeler("etat", {"escale_id": "ESC-2026-9999"})
    assert r.is_error and "Escale inconnue." in r.content[0].text


async def test_requete_brute(url):
    async with ClientTest(url) as c:
        r = await c.brut({"jsonrpc": "2.0", "id": 99, "method": "tools/list", "params": {}},
                         {"Mcp-Method": "tools/list"})
    assert r.status_code < 500
    assert c.echanges[-1].methode_mcp == "tools/list"


def test_revision_inconnue():
    with pytest.raises(ValueError, match="révision"):
        ClientTest("http://x/mcp", "2024-01-01")


def test_ligne_de_commande(url, capsys):
    code = client_test.main(["--rev", "2026-07-28", url, "etat", '{"escale_id": "ESC-2026-0412"}'])
    sortie = capsys.readouterr().out
    assert code == 0 and '"quai": 3' in sortie and "tools/call" in sortie
