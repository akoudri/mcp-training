"""Adaptateur d'identité (jeton porteur, jamais un argument) et journal serveur (refus compris)."""

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from pharos import autorisation, journal
from tests.aides import servir


@pytest.fixture(autouse=True)
def logs(tmp_path, monkeypatch):
    monkeypatch.setenv("PHAROS_LOGS", str(tmp_path))
    return tmp_path


def serveur(auth=None) -> FastMCP:
    mcp = FastMCP("essai", auth=auth, middleware=[journal.Journal("essai")])

    @mcp.tool
    def qui() -> dict:
        """Rend l'identité de l'appelant."""
        i = autorisation.identite()
        return {"nom": i.nom, "role": i.role, "agent_id": i.agent_id}

    @mcp.tool
    def refuse() -> str:
        """Remplace une erreur brute par un message propre."""
        try:
            raise ValueError('column "e.tarif_negocie" does not exist')
        except ValueError as exc:
            journal.consigner_erreur(exc)
            raise ToolError("La colonne demandée n'est pas accessible sur ce périmètre.") from None

    return mcp


def test_trois_identites():
    assert {j: (i.profil, i.agent_id, i.role) for j, i in autorisation.JETONS.items()} == {
        "jeton-exploitation": ("exploitation", None, "pharos_exploitation"),
        "jeton-rance": ("agent", "AG-RANCE", "pharos_agent"),
        "jeton-iroise": ("agent", "AG-IROISE", "pharos_agent")}


async def test_en_memoire_l_identite_est_injectee():
    with autorisation.en_tant_que("jeton-iroise"):
        async with Client(serveur()) as c:
            assert (await c.call_tool("qui", {})).data["agent_id"] == "AG-IROISE"
    async with Client(serveur()) as c:
        r = await c.call_tool_mcp("qui", {})
    assert r.is_error and "PHAROS_JETON" in r.content[0].text


def test_jeton_inconnu_refuse():
    with pytest.raises(ValueError):
        with autorisation.en_tant_que("jeton-pirate"):
            pass


async def test_en_http_le_jeton_porteur_fait_l_identite(logs):
    mcp = serveur(auth=autorisation.verificateur())
    with servir(mcp.http_app(path="/mcp", json_response=True, middleware=journal.http("essai"))) as url:
        async with Client(f"{url}/mcp", auth="jeton-rance") as c:
            assert (await c.call_tool("qui", {})).data == {"nom": "Agence Maritime Rance", "role": "pharos_agent",
                                                          "agent_id": "AG-RANCE"}
        with pytest.raises(Exception):
            async with Client(f"{url}/mcp") as c:
                await c.list_tools()
    issues = [(l["outil"], l["issue"], l["identite"]) for l in journal.lire("essai")]
    assert ("qui", "ok", "Agence Maritime Rance") in issues
    assert any(o is None and i == "refus" for o, i, _ in issues)            # le 401 est journalisé


async def test_journal_garde_l_erreur_brute_et_la_correlation():
    with autorisation.en_tant_que("jeton-rance"):
        async with Client(serveur()) as c:
            r = await c.call_tool_mcp("refuse", {}, meta={journal.CLE_CORRELATION: "c-42"})
    assert r.is_error and "tarif_negocie" not in r.content[0].text
    [ligne] = journal.lire("essai")
    assert ligne["correlation"] == "c-42" and ligne["issue"] == "refus"
    assert "tarif_negocie" in ligne["erreur_brute"] and ligne["message"].startswith("La colonne demandée")
