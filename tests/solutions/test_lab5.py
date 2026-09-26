from pathlib import Path

import pytest
from fastmcp import Client

from outils.construire_etats import superposer
from outils.repartiteur import creer_repartiteur
from outils.verifier.commun import Etat
from pharos_docs import jetons
from tests.aides import charger_module, servir

pytestmark = pytest.mark.skipif(not Path("solutions/lab05").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("etat-lab5")
    superposer(dossier, Path("gabarits"), Path("solutions"), 5)
    return dossier


@pytest.fixture(scope="module")
def serveur(etat):
    return charger_module(etat / "serveurs" / "pharos_docs" / "serveur.py", "solution_lab5_serveur")


@pytest.fixture(autouse=True)
def cle(monkeypatch):
    monkeypatch.setenv("CLE_SERVEUR", "cle-de-test")


async def test_lecture_puis_refus_hors_portee(serveur):
    async with Client(serveur.mcp) as c:
        d = (await c.call_tool("ouvrir_dossier", {"escale_id": "ESC-2026-0412"})).data
        assert d["sections"][6]["id"] == "CM-0412:s07" and d["sections"][6]["titre"].startswith("Article 7")
        lu = (await c.call_tool("lire_section", {"handle": d["handle"], "section": "CM-0412:s07"})).data
        assert "1 850" in lu["section"]["texte"] and lu["handle"].startswith("hdl_")
        r = await c.call_tool("lire_section", {"handle": d["handle"], "section": "CM-0405:s07"}, raise_on_error=False)
    assert r.is_error and "ouvrir_dossier" in r.content[0].text


async def test_handle_expire(serveur):
    h = jetons.signer({"e": "ESC-2026-0412", "d": "CM-0412"}, "cle-de-test", duree_s=-1)
    async with Client(serveur.mcp) as c:
        r = await c.call_tool("lire_section", {"handle": h, "section": "CM-0412:s07"}, raise_on_error=False)
    assert r.is_error and "a expiré" in r.content[0].text


async def test_la_solution_passe_son_verificateur(serveur, etat):
    from outils.verifier import lab5
    # Deux instances = deux chargements distincts du module (deux objets FastMCP, aucun état partagé).
    autre = charger_module(etat / "serveurs" / "pharos_docs" / "serveur.py", "solution_lab5_serveur_b")
    with servir(serveur.mcp.http_app(path="/mcp", json_response=True)) as a, \
         servir(autre.mcp.http_app(path="/mcp", json_response=True)) as b, \
         servir(creer_repartiteur(a, b)) as r:
        rapport = await lab5.v.executer(url=f"{r}/mcp", sans_modele=True)
    assert [x for x in rapport.resultats if x.etat is Etat.ECHEC] == [], rapport.texte()
