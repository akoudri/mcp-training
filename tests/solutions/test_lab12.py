import contextlib
from pathlib import Path

import pytest

from outils.repartiteur import creer_repartiteur
from outils.servir import servir
from outils.verifier.commun import Etat
from tests.aides import charger_module, etat_complet, importer_client, importer_paquet

pytestmark = pytest.mark.skipif(not Path("solutions/lab12").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")
CLE_ETAT = "pharos-salle-2026-cle-etat-mrtr-partagee"


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    return etat_complet(tmp_path_factory.mktemp("etat-lab12"), 12)


@contextlib.contextmanager
def deux_instances(etat: Path):
    """Deux chargements distincts du serveur de la solution (deux « processus »), derrière le répartiteur du kit."""
    with importer_paquet(etat, "serveurs"):
        a = charger_module(etat / "serveurs" / "pharos_ops" / "serveur.py", "solution_lab12_a").mcp
        b = charger_module(etat / "serveurs" / "pharos_ops" / "serveur.py", "solution_lab12_b").mcp
        with servir(a.http_app(path="/mcp", json_response=True)) as ua, \
                servir(b.http_app(path="/mcp", json_response=True)) as ub, servir(creer_repartiteur(ua, ub)) as ur:
            yield f"{ur}/mcp"


async def test_la_solution_passe_son_verificateur(etat, mocks_servis, monkeypatch):
    from outils.verifier import lab12

    monkeypatch.setenv("CLE_ETAT", CLE_ETAT)
    monkeypatch.setenv("CANAL_URL", f"{mocks_servis}/canal")
    monkeypatch.setattr(lab12, "RACINE", etat)
    monkeypatch.setattr(lab12, "MESURES", etat / "labs" / "lab12" / "mesures.md")
    with deux_instances(etat) as url, importer_client(etat / "client"):
        rapport = await lab12.v.executer(url=url, sans_modele=True)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()


def test_les_erreurs_inattendues_sont_masquees(etat, monkeypatch):
    monkeypatch.setenv("CLE_ETAT", CLE_ETAT)
    with importer_paquet(etat, "serveurs"):
        serveur = charger_module(etat / "serveurs" / "pharos_ops" / "serveur.py", "solution_lab12_serveur")
        assert serveur.mcp._mask_error_details is True


def test_mesures_consignees(etat):
    texte = (etat / "labs" / "lab12" / "mesures.md").read_text(encoding="utf-8")
    assert "À RELEVER" not in texte and "CLE_ETAT" in texte
