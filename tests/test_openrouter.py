import json

import httpx
import pytest
from fastmcp import Client, FastMCP

from pharos import openrouter


@pytest.fixture(autouse=True)
def cle(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("PHAROS_MODELE", "google/gemini-3.6-flash")


def client(gestionnaire):
    return httpx.Client(transport=httpx.MockTransport(gestionnaire))


def reponse_outil(nom="lister_documents", arguments='{"escale_id": "ESC-2026-0412"}'):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": "appel-1", "type": "function", "function": {"name": nom, "arguments": arguments}}]}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 12, "cost": 0.0001}}


async def test_outils_openai_depuis_fastmcp():
    mcp = FastMCP("x")

    @mcp.tool
    def lister_documents(escale_id: str) -> dict:
        """Liste les documents."""
        return {}

    async with Client(mcp) as c:
        outils = openrouter.outils_openai(await c.list_tools())
    assert outils[0]["type"] == "function"
    f = outils[0]["function"]
    assert f["name"] == "lister_documents" and f["description"] == "Liste les documents."
    assert f["parameters"]["properties"]["escale_id"]["type"] == "string"


def test_outils_openai_depuis_dict_sans_schema():
    [o] = openrouter.outils_openai([{"name": "ping"}])
    assert o["function"]["parameters"] == {"type": "object", "properties": {}}


def test_requete_conforme_et_appels_lus():
    vu = {}

    def g(r):
        vu["corps"] = json.loads(r.content)
        vu["auth"] = r.headers["authorization"]
        return httpx.Response(200, json=reponse_outil())

    rep = openrouter.completer([{"role": "user", "content": "q"}],
                               openrouter.outils_openai([{"name": "lister_documents"}]), client=client(g))
    assert vu["auth"] == "Bearer sk-or-test"
    assert vu["corps"]["model"] == "google/gemini-3.6-flash"
    assert vu["corps"]["tool_choice"] == "auto"
    assert "parallel_tool_calls" not in vu["corps"]
    assert rep.appels == [openrouter.Appel("appel-1", "lister_documents", {"escale_id": "ESC-2026-0412"})]
    assert rep.message["tool_calls"][0]["id"] == "appel-1"
    assert rep.usage["prompt_tokens"] == 120


def test_sans_outils_pas_de_tool_choice():
    vu = {}

    def g(r):
        vu["corps"] = json.loads(r.content)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Bonjour"}}]})

    rep = openrouter.completer([{"role": "user", "content": "q"}], [], client=client(g))
    assert "tools" not in vu["corps"] and "tool_choice" not in vu["corps"]
    assert rep.appels == [] and rep.message["content"] == "Bonjour"


def test_arguments_non_json():
    rep = openrouter.completer([], [{"type": "function", "function": {"name": "x"}}],
                               client=client(lambda r: httpx.Response(200, json=reponse_outil(arguments="{pas du json"))))
    assert rep.appels[0].arguments == {"_brut": "{pas du json"}


def test_cle_absente(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(openrouter.ErreurModele, match="absente"):
        openrouter.completer([], [], client=client(lambda r: httpx.Response(200)))


@pytest.mark.parametrize("statut, attendu", [(401, "invalide"), (402, "crédit"), (404, "PHAROS_MODELE"),
                                             (429, "patienter"), (503, "HTTP 503")])
def test_erreurs_http(statut, attendu):
    with pytest.raises(openrouter.ErreurModele, match=attendu):
        openrouter.completer([], [], client=client(lambda r: httpx.Response(statut, json={"error": {}})))


def test_erreur_429():
    with pytest.raises(openrouter.ErreurModele, match="patienter une minute"):
        openrouter.completer([], [], client=client(lambda r: httpx.Response(429)))


def test_reseau_injoignable():
    def g(r):
        raise httpx.ConnectError("hors ligne")
    with pytest.raises(openrouter.ErreurModele, match="injoignable"):
        openrouter.completer([], [], client=client(g))


def test_parallel_tool_calls_interdit():
    with pytest.raises(ValueError, match="parallel_tool_calls"):
        openrouter.completer([], [], client=client(lambda r: httpx.Response(200)), parallel_tool_calls=False)


def test_estimer_tokens_croit_avec_le_contexte():
    court = openrouter.estimer_tokens([{"role": "user", "content": "q"}])
    long = openrouter.estimer_tokens([{"role": "user", "content": "q " * 500}])
    assert 0 < court < long
