from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from outils.verifier import lab1
from outils.verifier.commun import Etat
from tests.aides import charger_module, servir


async def test_le_squelette_ne_passe_pas():
    squelette = charger_module(Path("gabarits/lab01/serveurs/pharos_docs/serveur.py"), "gabarit_lab1_serveur")
    with servir(squelette.mcp.http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab1.v.executer(url=f"{base}/mcp", sans_modele=True)
    premier = rapport.resultats[0]
    assert premier.etat is Etat.ECHEC and "extraire_dates_contractuelles" in premier.detail
    assert rapport.code_sortie == 1
    assert any(r.etat is Etat.SAUTE for r in rapport.resultats)           # banc sauté sans modèle


def _resultat(rapport, libelle: str):
    return next(r for r in rapport.resultats if r.libelle == libelle)


def _serveur_dates_alternatives() -> FastMCP:
    """Répond au format « prose », avec un saut de ligne réel au milieu de l'échéance (comme CM-0412)."""
    mcp = FastMCP("test-dates-alternatives")

    @mcp.tool
    def lister_documents(escale_id: str) -> dict:
        return {"escale_id": escale_id, "documents": []}

    @mcp.tool
    def rechercher_clause(escale_id: str, sujet: str) -> dict:
        raise ToolError("non pertinent pour ce test")

    @mcp.tool
    def extraire_dates_contractuelles(escale_id: str) -> str:
        return ("Le contrat CM-0412 a été signé le 2 mars 2026. Il prend effet le 1er avril 2026 "
                "et arrive à échéance le 31 mars\n2027.")

    return mcp


async def test_dates_acceptent_les_formes_alternatives():
    with servir(_serveur_dates_alternatives().http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab1.v.executer(url=f"{base}/mcp", sans_modele=True)
    resultat = _resultat(rapport, "Les dates du contrat de ESC-2026-0412 sont justes : "
                                  "signature, prise d'effet, échéance.")
    assert resultat.etat is Etat.OK, resultat.detail


def _serveur_erreurs_alternatives() -> FastMCP:
    """Messages d'erreur métier reformulés, sans les identifiants exacts BL-0406/AE-0406."""
    mcp = FastMCP("test-erreurs-alternatives")

    @mcp.tool
    def lister_documents(escale_id: str) -> dict:
        return {"escale_id": escale_id, "documents": []}

    @mcp.tool
    def rechercher_clause(escale_id: str, sujet: str) -> dict:
        if escale_id == "ESC-2026-9999":
            raise ToolError("Escale ESC-2026-9999 inconnue ; identifiants de la forme ESC-AAAA-NNNN, "
                            "voir lister_documents.")
        if escale_id == "ESC-2026-0406":
            raise ToolError("Pas de contrat : deux connaissements et un avis d'escale.")
        if escale_id == "ESC-2026-0408" and sujet == "assurance":
            raise ToolError("Sujet absent de ce contrat ; sujets disponibles : penalites, delais, manutention.")
        return {"document_id": "CM-XXXX", "article": "Article X", "page": 1, "texte": "…"}

    @mcp.tool
    def extraire_dates_contractuelles(escale_id: str) -> dict:
        raise ToolError("non pertinent pour ce test")

    return mcp


async def test_erreurs_metier_acceptent_les_formes_alternatives():
    with servir(_serveur_erreurs_alternatives().http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab1.v.executer(url=f"{base}/mcp", sans_modele=True)
    resultat = _resultat(rapport, "Les trois erreurs métier disent quoi faire au tour suivant (étape 2).")
    assert resultat.etat is Etat.OK, resultat.detail
