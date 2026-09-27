from pathlib import Path

import pytest

from outils.verifier.commun import Etat
from tests.aides import base_requise, charger_module, etat_complet, importer_client, importer_paquet

pytestmark = pytest.mark.skipif(not Path("solutions/lab11").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    return etat_complet(tmp_path_factory.mktemp("etat-lab11"), 11)


@base_requise
async def test_la_solution_passe_son_verificateur(etat, base_de_test, mocks_servis, monkeypatch):
    from outils.verifier import lab11

    monkeypatch.setattr(lab11, "RACINE", etat)
    monkeypatch.setenv("PHAROS_VITESSE", "rapide")                   # le vérificateur la change : restaurée ici
    with importer_paquet(etat, "serveurs"), importer_client(etat / "client"):
        rapport = await lab11.v.executer(url=f"{mocks_servis}/_sante", sans_modele=True)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()


def test_les_erreurs_inattendues_sont_masquees(etat):
    with importer_paquet(etat, "serveurs"):
        serveur = charger_module(etat / "serveurs" / "pharos_ops" / "serveur.py", "solution_lab11_serveur")
        assert serveur.mcp._mask_error_details is True


def test_observations_consignees(etat):
    texte = (etat / "labs" / "lab11" / "observations.md").read_text(encoding="utf-8")
    assert "À RELEVER" not in texte and "quai par quai" in texte
