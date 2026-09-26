"""Scénario des deux clients de test (make lab3-clients, vérificateurs des LAB 2 et 3)."""

from fastmcp import FastMCP

from outils.scenario_legacy import PAGES_MAX, afficher, derouler
from serveurs.pharos_legacy.serveur import creer_app
from tests.aides import servir


async def test_client_ancien_complet_sur_l_origine():
    with servir(creer_app()) as base:
        d = await derouler(f"{base}/mcp", "2025-11-25")
    assert d.erreur is None and d.etat["quai"] == 3
    assert [p["page"] for p in d.pages] == [1, 2, 3] and len(d.mouvements) == 57
    assert "scénario complet" in afficher(d) and "aucun handle" in afficher(d)


async def test_client_recent_refuse_par_l_origine():
    with servir(creer_app()) as base:
        d = await derouler(f"{base}/mcp", "2026-07-28")
    assert d.etat is None and "Session absente" in d.erreur
    assert "ÉCHEC" in afficher(d)


async def test_serveur_injoignable():
    d = await derouler("http://127.0.0.1:9/mcp", "2026-07-28")
    assert d.etat is None and d.erreur


async def test_garde_fou_contre_une_pagination_sans_fin():
    mcp = FastMCP("sans-fin")
    compteur = {"page": 1}

    @mcp.tool
    def etat_escale(escale_id: str) -> dict:
        return {"escale_id": escale_id, "quai": 3}

    @mcp.tool
    def lister_mouvements(escale_id: str) -> dict:
        return {"page": 1, "pages": 99, "total": 0, "mouvements": []}

    @mcp.tool
    def page_suivante() -> dict:
        compteur["page"] += 1
        return {"page": compteur["page"], "pages": 99, "total": 0, "mouvements": []}

    with servir(mcp.http_app(path="/mcp", json_response=True)) as base:
        d = await derouler(f"{base}/mcp", "2025-11-25")
    assert len(d.pages) == PAGES_MAX


async def test_page_sans_handle_en_2026():
    mcp = FastMCP("sans-handle")

    @mcp.tool
    def etat_escale(escale_id: str) -> dict:
        return {"escale_id": escale_id, "quai": 3}

    @mcp.tool
    def lister_mouvements(escale_id: str) -> dict:
        return {"page": 1, "pages": 3, "total": 57, "mouvements": []}

    with servir(mcp.http_app(path="/mcp", json_response=True)) as base:
        d = await derouler(f"{base}/mcp", "2026-07-28")
    assert "sans handle" in d.erreur and len(d.pages) == 1
