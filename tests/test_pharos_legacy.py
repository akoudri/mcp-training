"""pharos-legacy d'origine, en 2025-11-25 : poignée de main, sessions, curseur de session, -32002."""

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import McpError

from outils.client_test import ClientTest
from serveurs.pharos_legacy.serveur import creer_app
from tests.aides import origine_seulement, servir

pytestmark = origine_seulement

ESCALE = "ESC-2026-0412"


@pytest.fixture
def url():
    with servir(creer_app()) as base:
        yield f"{base}/mcp"


def _texte(r) -> str:
    return r.content[0].text


async def test_poignee_de_main_puis_session(url):
    async with ClientTest(url, "2025-11-25") as c:
        noms = [o.name for o in await c.outils()]
    assert noms == ["etat_escale", "lister_mouvements", "page_suivante"]
    initialize = c.echanges[0]
    assert initialize.methode_mcp == "initialize" and "mcp-session-id" in initialize.entetes_reponse
    session = initialize.entetes_reponse["mcp-session-id"]
    assert all(e.entetes_requete.get("mcp-session-id") == session for e in c.echanges[1:])


async def test_pagination_par_le_curseur_de_session(url):
    async with ClientTest(url, "2025-11-25") as c:
        assert "lister_mouvements" in _texte(await c.appeler("page_suivante"))       # rien d'ouvert
        pages = [await c.appeler("lister_mouvements", {"escale_id": ESCALE})]
        pages += [await c.appeler("page_suivante") for _ in range(2)]
        fin = await c.appeler("page_suivante")
    assert [p.is_error for p in pages] == [False, False, False]
    assert all(p.structured_content is None for p in pages)                         # texte seul
    assert '"page": 3' in _texte(pages[2]) and fin.is_error and "Plus de page" in _texte(fin)
    assert not any("hdl_" in e.corps_reponse for e in c.echanges)


async def test_escale_inconnue_en_erreur_json_rpc_32002(url):
    async with ClientTest(url, "2025-11-25") as c:
        with pytest.raises(McpError) as exc:
            await c.appeler("etat_escale", {"escale_id": "ESC-2026-9999"})
    assert exc.value.error.code == -32002


async def test_client_2026_refuse_faute_de_session(url):
    with pytest.raises(McpError, match="Session absente"):
        async with ClientTest(url, "2026-07-28") as c:
            await c.outils()


async def test_mode_auto_se_replie_sur_2025(url):
    async with Client(StreamableHttpTransport(url), mode="auto") as c:
        assert len(await c.list_tools()) == 3


async def test_sessions_propres_a_chaque_instance():
    with servir(creer_app()) as a, servir(creer_app()) as b:
        async with httpx.AsyncClient() as http:
            r = await http.post(f"{a}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                                  "params": {"clientInfo": {"name": "t", "version": "1"}}})
            session = r.headers["mcp-session-id"]
            ping = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
            chez_a = await http.post(f"{a}/mcp", json=ping, headers={"Mcp-Session-Id": session})
            chez_b = await http.post(f"{b}/mcp", json=ping, headers={"Mcp-Session-Id": session})
    assert chez_a.json() == {"jsonrpc": "2.0", "id": 2, "result": {}}
    assert chez_b.status_code == 404 and chez_b.json()["error"]["code"] == -32600


async def test_requetes_malformees(url):
    async with httpx.AsyncClient() as http:
        illisible = await http.post(url, content=b"{pas du json", headers={"Content-Type": "application/json"})
        lot = await http.post(url, json=[{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
        sans_session = await http.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        flux = await http.get(url)
    assert (illisible.status_code, illisible.json()["error"]["code"]) == (400, -32700)
    assert (lot.status_code, lot.json()["error"]["code"]) == (400, -32600)
    assert sans_session.status_code == 400 and "initialize" in sans_session.json()["error"]["message"]
    assert flux.status_code == 405


async def test_methode_inconnue_et_fermeture(url):
    async with httpx.AsyncClient() as http:
        r = await http.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        entetes = {"Mcp-Session-Id": r.headers["mcp-session-id"]}
        inconnue = await http.post(url, json={"jsonrpc": "2.0", "id": 2, "method": "resources/list"}, headers=entetes)
        ferme = await http.delete(url, headers=entetes)
        apres = await http.post(url, json={"jsonrpc": "2.0", "id": 3, "method": "ping"}, headers=entetes)
    assert inconnue.json()["error"]["code"] == -32601
    assert ferme.status_code == 200 and apres.status_code == 404
