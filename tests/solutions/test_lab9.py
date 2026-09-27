from pathlib import Path

import pytest

from outils.verifier.commun import Etat
from tests.aides import DSN_TEST, base_requise, etat_complet, importer_paquet, servir

pytestmark = [pytest.mark.skipif(not Path("solutions/lab09").is_dir(),
                                 reason="instantanés présents sur la branche solutions uniquement"), base_requise]


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    return etat_complet(tmp_path_factory.mktemp("etat-lab9"), 9)      # le sous-processus pytest importe src/


async def test_la_solution_passe_son_verificateur(etat, base_de_test, monkeypatch, tmp_path):
    from donnees.base.__main__ import charger

    await charger(DSN_TEST, politique=etat / "labs" / "lab9" / "politique.sql")
    monkeypatch.setenv("PHAROS_LOGS", str(tmp_path))
    try:
        with importer_paquet(etat, "serveurs"):
            from serveurs.pharos_data import serveur
            from outils.verifier import lab9
            monkeypatch.setattr(lab9, "RACINE", etat)
            with servir(serveur.mcp.http_app(path="/mcp", json_response=True)) as url:
                rapport = await lab9.v.executer(url=f"{url}/mcp", sans_modele=True)
    finally:
        await charger(DSN_TEST, politique=Path("/nulle-part.sql"))
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()


def test_les_erreurs_inattendues_sont_masquees(etat):
    """Consigne du contrôleur (Task 8, reconduite au LAB 9) : mask_error_details=True sur pharos-data, pour
    qu'une exception inattendue (SQL, schéma) ne soit jamais renvoyée telle quelle au client — seul le
    journal (Task 4) la garde. fastmcp 4.0.10 range ce réglage dans l'attribut privé FastMCP._mask_error_details."""
    with importer_paquet(etat, "serveurs"):
        from serveurs.pharos_data import serveur
        assert serveur.mcp._mask_error_details is True
