from pathlib import Path

import pytest

from outils.verifier.commun import Etat
from tests.aides import etat_complet, importer_paquet, servir

pytestmark = pytest.mark.skipif(not Path("solutions/lab07").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    return etat_complet(tmp_path_factory.mktemp("etat-lab7"), 7)


async def test_la_solution_passe_son_verificateur(etat, monkeypatch):
    monkeypatch.setenv("CLE_SERVEUR", "cle-de-test")
    from outils.verifier import lab7
    monkeypatch.setattr(lab7, "RACINE", etat)
    with importer_paquet(etat, "serveurs"):
        from serveurs.pharos_docs.serveur import mcp
        with servir(mcp.http_app(path="/mcp", json_response=True)) as base:
            rapport = await lab7.v.executer(url=f"{base}/mcp", sans_modele=True)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()
