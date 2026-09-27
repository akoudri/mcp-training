from pathlib import Path

import pytest

from outils.verifier.commun import Etat
from tests.aides import charger_module, etat_complet, importer_client

pytestmark = pytest.mark.skipif(not Path("solutions/lab10").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    return etat_complet(tmp_path_factory.mktemp("etat-lab10"), 10)


async def test_la_solution_passe_son_verificateur(etat, mocks_servis, monkeypatch):
    from outils.verifier import lab10 as verificateur

    monkeypatch.setattr(verificateur, "RACINE", etat)
    monkeypatch.setattr(verificateur, "NOTE", etat / "labs" / "lab10" / "note-panne.md")
    with importer_client(etat / "client"):
        rapport = await verificateur.v.executer(url=f"{mocks_servis}/_sante", sans_modele=True)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()


def test_les_erreurs_inattendues_sont_masquees(etat):
    """Comme pharos-data : une exception inattendue n'est jamais renvoyée telle quelle au client (le journal la
    garde). fastmcp 4.0.10 range ce réglage dans l'attribut privé FastMCP._mask_error_details."""
    serveur = charger_module(etat / "serveurs" / "pharos_ops" / "serveur.py", "solution_lab10_serveur")
    assert serveur.mcp._mask_error_details is True


def test_mesures_consignees(etat):
    texte = (etat / "labs" / "lab10" / "mesures.md").read_text(encoding="utf-8")
    assert "À RELEVER" not in texte and "Ne pas conclure sur le risque météo" in texte
