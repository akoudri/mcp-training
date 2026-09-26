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


def _resultat_empreinte(rapport):
    return next(r for r in rapport.resultats if "empreinte" in r.libelle.casefold())


async def _rapport_avec_suite_remplacee(tmp_path, monkeypatch, contenu_suite: str):
    """Assemble un état LAB 7 isolé, remplace tests/pharos_docs/test_pharos_docs.py, lance la vérification."""
    etat = etat_complet(tmp_path, 7)
    (etat / "tests" / "pharos_docs" / "test_pharos_docs.py").write_text(contenu_suite, encoding="utf-8")
    monkeypatch.setenv("CLE_SERVEUR", "cle-de-test")
    from outils.verifier import lab7
    monkeypatch.setattr(lab7, "RACINE", etat)
    with importer_paquet(etat, "serveurs"):
        from serveurs.pharos_docs.serveur import mcp
        with servir(mcp.http_app(path="/mcp", json_response=True)) as base:
            return await lab7.v.executer(url=f"{base}/mcp", sans_modele=True)


async def test_empreinte_qui_ne_compare_rien_est_detectee(tmp_path, monkeypatch):
    """Une suite dont le test d'empreinte ne compare rien (assert True) ne doit pas suffire à passer le critère."""
    rapport = await _rapport_avec_suite_remplacee(
        tmp_path, monkeypatch, "def test_empreinte_du_catalogue():\n    assert True\n")
    r = _resultat_empreinte(rapport)
    assert r.etat is Etat.ECHEC and "ne compare pas le catalogue" in r.detail, rapport.texte()


async def test_suite_rouge_sur_copie_intacte_est_detectee(tmp_path, monkeypatch):
    """Si la suite est déjà rouge sur une copie intacte, le critère d'empreinte ne doit pas conclure à tort."""
    rapport = await _rapport_avec_suite_remplacee(
        tmp_path, monkeypatch, "def test_toujours_rouge():\n    assert False\n")
    r = _resultat_empreinte(rapport)
    assert r.etat is Etat.ECHEC and "copie intacte" in r.detail, rapport.texte()
