from pathlib import Path

import pytest

from outils.construire_etats import superposer
from outils.verifier.commun import Etat
from tests.aides import charger_module, importer_client, servir

pytestmark = pytest.mark.skipif(not Path("solutions/lab04").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("etat-lab4")
    superposer(dossier, Path("gabarits"), Path("solutions"), 4)
    return dossier


async def test_la_solution_passe_son_verificateur(etat):
    serveur = charger_module(etat / "serveurs" / "pharos_docs" / "serveur.py", "solution_lab4_serveur")
    with importer_client(etat / "client"):
        from outils.verifier import lab4
        with servir(serveur.mcp.http_app(path="/mcp", json_response=True)) as base:
            rapport = await lab4.v.executer(url=f"{base}/mcp", sans_modele=True)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()
