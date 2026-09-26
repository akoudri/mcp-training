from pathlib import Path

import pytest

from outils.construire_etats import superposer
from outils.verifier.commun import Etat
from tests.aides import base_requise, charger_module, importer_client, servir

pytestmark = [pytest.mark.skipif(not Path("solutions/lab08").is_dir(),
                                 reason="instantanés présents sur la branche solutions uniquement"), base_requise]


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("etat-lab8")
    superposer(dossier, Path("gabarits"), Path("solutions"), 8)
    return dossier


async def test_la_solution_passe_son_verificateur(etat, base_de_test, monkeypatch):
    serveur = charger_module(etat / "serveurs" / "pharos_data" / "serveur.py", "solution_lab8_serveur")
    with importer_client(etat / "client"):
        from outils.verifier import lab8
        monkeypatch.setattr(lab8, "MESURES", etat / "labs" / "lab8" / "mesures.md")
        with servir(serveur.mcp.http_app(path="/mcp", json_response=True)) as url:
            rapport = await lab8.v.executer(url=f"{url}/mcp", sans_modele=True)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()


def test_les_erreurs_inattendues_sont_masquees(etat):
    """Consigne du contrôleur (Task 8) : mask_error_details=True sur pharos-data, pour qu'une exception
    inattendue (SQL, schéma) ne soit jamais renvoyée telle quelle au client — seul le journal (Task 4) la
    garde. fastmcp 4.0.10 range ce réglage dans l'attribut privé FastMCP._mask_error_details."""
    serveur = charger_module(etat / "serveurs" / "pharos_data" / "serveur.py", "solution_lab8_serveur_masque")
    assert serveur.mcp._mask_error_details is True
