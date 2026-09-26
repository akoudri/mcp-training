"""Vérificateur du LAB 2, sur ce que le binôme reçoit (l'origine) et sur une migration inachevée."""

import pytest
from fastmcp import FastMCP

from outils.repartiteur import creer_repartiteur
from outils.verifier import lab2
from outils.verifier.commun import Etat
from serveurs.pharos_legacy.serveur import creer_app
from tests.aides import origine_seulement, servir


def _etats(rapport) -> list[Etat]:
    return [r.etat for r in rapport.resultats]


@pytest.fixture(autouse=True)
def cle(monkeypatch):
    monkeypatch.setenv("CLE_SERVEUR", "cle-de-test")


@origine_seulement
async def test_sur_l_origine_tout_est_a_faire():
    with servir(creer_app()) as a, servir(creer_app()) as b, servir(creer_repartiteur(a, b)) as r:
        rapport = await lab2.v.executer(url=f"{r}/mcp")
    assert _etats(rapport) == [Etat.CONSTAT] + [Etat.ECHEC] * 6
    assert "Session absente" in rapport.resultats[1].detail
    assert rapport.code_sortie == 1


def _migration_sans_handle() -> FastMCP:
    """Un serveur qui parle 2026-07-28 (fastmcp) mais pagine encore sans handle."""
    mcp = FastMCP("pharos-legacy")

    @mcp.tool
    def etat_escale(escale_id: str) -> dict:
        return {"escale_id": escale_id, "quai": 3}

    @mcp.tool
    def lister_mouvements(escale_id: str) -> dict:
        return {"escale_id": escale_id, "page": 1, "pages": 3, "total": 57, "mouvements": []}

    return mcp


async def test_migration_mecanique_faite_handle_a_faire():
    serveur = _migration_sans_handle().http_app(path="/mcp", json_response=True)
    with servir(serveur) as a, servir(creer_repartiteur(a, a)) as r:
        rapport = await lab2.v.executer(url=f"{r}/mcp")
    assert _etats(rapport) == [Etat.CONSTAT, Etat.OK, Etat.OK, Etat.OK, Etat.OK, Etat.ECHEC, Etat.ECHEC]
    assert "handle" in rapport.resultats[5].detail


async def test_serveur_arrete():
    rapport = await lab2.v.executer(url="http://127.0.0.1:9/mcp")
    assert len(rapport.resultats) == 1 and "make lab2-deux-instances" in rapport.resultats[0].detail
