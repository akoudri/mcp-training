import importlib
from pathlib import Path

import httpx
import pytest
from fastmcp.exceptions import McpError

from outils.client_test import ClientTest
from outils.repartiteur import creer_repartiteur
from outils.scenario_legacy import derouler
from outils.verifier.commun import Etat
from tests.aides import etat_complet, importer_paquet, servir

pytestmark = pytest.mark.skipif(not Path("solutions/lab02").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def serveur(tmp_path_factory):
    etat = etat_complet(tmp_path_factory.mktemp("etat-lab2"), 2)
    with importer_paquet(etat, "serveurs"):
        return importlib.import_module("serveurs.pharos_legacy.serveur")


@pytest.fixture(autouse=True)
def cle(monkeypatch):
    monkeypatch.setenv("CLE_SERVEUR", "cle-de-test")


async def test_pagination_par_handle_sur_deux_instances(serveur):
    with servir(serveur.creer_app()) as a, servir(serveur.creer_app()) as b, servir(creer_repartiteur(a, b)) as r:
        d = await derouler(f"{r}/mcp", "2026-07-28")
    assert d.erreur is None and len(d.mouvements) == 57
    assert [bool(p.get("handle")) for p in d.pages] == [True, True, False]
    assert not any("mcp-session-id" in e.entetes_reponse for e in d.echanges)


async def test_handle_d_un_autre_client_refuse(serveur):
    with servir(serveur.creer_app()) as base:
        async with ClientTest(f"{base}/mcp", nom="client-a") as a:
            handle = (await a.appeler("lister_mouvements", {"escale_id": "ESC-2026-0412"})).structured_content["handle"]
        async with ClientTest(f"{base}/mcp", nom="client-b") as b:
            r = await b.appeler("page_suivante", {"handle": handle})
    assert r.is_error and "autre client" in r.content[0].text


async def test_revision_non_servie_et_escale_inconnue(serveur):
    with servir(serveur.creer_app()) as base:
        with pytest.raises(McpError):
            async with ClientTest(f"{base}/mcp", "2025-11-25") as ancien:
                await ancien.outils()
        async with ClientTest(f"{base}/mcp") as c:
            with pytest.raises(McpError) as exc:
                await c.appeler("etat_escale", {"escale_id": "ESC-2026-9999"})
        async with httpx.AsyncClient() as http:
            illisible = await http.post(f"{base}/mcp", content=b"{", headers={"Mcp-Method": "tools/call"})
    assert exc.value.error.code == -32002            # consigné à l'inventaire, laissé tel quel
    assert illisible.status_code == 400              # extension A : corps illisible, en-têtes corrects


async def test_la_solution_passe_son_verificateur(serveur):
    from outils.verifier import lab2
    with servir(serveur.creer_app()) as a, servir(serveur.creer_app()) as b, servir(creer_repartiteur(a, b)) as r:
        rapport = await lab2.v.executer(url=f"{r}/mcp", sans_modele=True)
    assert [x for x in rapport.resultats if x.etat is Etat.ECHEC] == [], rapport.texte()
