from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from outils import banc
from outils.verifier import lab1
from outils.verifier.commun import Etat
from tests.aides import charger_module, servir, serveur_demo


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


async def test_question_4_consignee_sans_verdict(monkeypatch):
    """Q4 dépend de la conversation de Q3 (banc mono-tour) : elle ne doit plus peser sur le critère."""
    q1 = banc.Question(1, "Q1", "lister_documents", {"escale_id": "ESC-2026-0412"})
    q2 = banc.Question(2, "Q2", "rechercher_clause", {"sujet": "penalites"}, constat=True)
    q3 = banc.Question(3, "Q3", "extraire_dates_contractuelles", {"escale_id": "ESC-2026-0412"})
    q4 = banc.Question(4, "Q4", "rechercher_clause", {"sujet": "assurance"}, constat=True)

    executions = [
        banc.Execution(q1, "lister_documents", {"escale_id": "ESC-2026-0412"}, True),
        banc.Execution(q2, "rechercher_clause", {"sujet": "penalites"}, None),
        banc.Execution(q3, "extraire_dates_contractuelles", {"escale_id": "ESC-2026-0412"}, True),
        banc.Execution(q4, None, {}, None),
    ]

    async def _faux_banc(*args, **kwargs):
        return executions

    monkeypatch.setattr(banc, "executer_banc", _faux_banc)
    with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab1.v.executer(url=f"{base}/mcp", sans_modele=False)

    resultat = _resultat(rapport, "Les questions 1, 3 et 4 déclenchent le bon outil sans reformulation humaine.")
    assert resultat.etat is Etat.OK, resultat.detail
    assert "question 4" in resultat.detail.lower() and "question 3" in resultat.detail.lower()

    constat_q2 = _resultat(rapport, "Le résultat de la question 2 est consigné tel quel, y compris s'il est mauvais.")
    assert "rechercher_clause" in constat_q2.detail
    assert constat_q2.detail.count("premier appel") == 2   # Q2 et Q4
