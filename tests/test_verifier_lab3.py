"""Vérificateur du LAB 3, sur l'origine (seul le client ancien passe) et sans affinité."""

import pytest
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route

from outils.repartiteur import creer_repartiteur
from outils.verifier import lab3
from outils.verifier.commun import Etat
from serveurs.pharos_legacy.serveur import creer_app
from tests.aides import origine_seulement, servir


@pytest.fixture(autouse=True)
def journal(tmp_path, monkeypatch):
    monkeypatch.setenv("PHAROS_JOURNAL_LEGACY", str(tmp_path / "pharos-legacy.jsonl"))


def _par_libelle(rapport) -> dict:
    return {r.libelle.split(" — ")[0][:40]: r for r in rapport.resultats}


async def _toujours_400(requete):
    return Response(status_code=400)


def _serveur_qui_refuse_tout() -> Starlette:
    """Un serveur Starlette minimal qui répond 400 à tout : le client 2025-11-25 échoue même avec affinité."""
    return Starlette(routes=[Route("/mcp", _toujours_400, methods=["GET", "POST", "DELETE"])])


@origine_seulement
async def test_sur_l_origine_seul_le_client_ancien_passe(monkeypatch):
    with servir(creer_app()) as a, servir(creer_app()) as b, servir(creer_repartiteur(a, b, affinite=True)) as r:
        monkeypatch.setenv("AMONT_LEGACY_A", a)
        monkeypatch.setenv("AMONT_LEGACY_B", b)
        rapport = await lab3.v.executer(url=f"{r}/mcp")
    resultats = rapport.resultats
    etat_escale = resultats[1]
    assert etat_escale.etat is Etat.ECHEC
    assert "client 2026-07-28" in etat_escale.detail and "client 2025-11-25" not in etat_escale.detail
    assert resultats[3].etat is Etat.ECHEC                          # structuredContent absent (texte seul)
    assert resultats[5].etat is Etat.OK                             # aucun handle servi au client ancien
    assert resultats[6].etat is Etat.ECHEC and "compat.journaliser" in resultats[6].detail
    assert "Session inconnue" in resultats[-1].detail               # constat sans affinité


@origine_seulement
async def test_sans_affinite_le_critere_decisif_le_dit():
    with servir(creer_app()) as a, servir(creer_app()) as b, servir(creer_repartiteur(a, b)) as r:
        rapport = await lab3.v.executer(url=f"{r}/mcp")
    decisif = next(x for x in rapport.resultats if x.libelle.startswith("Critère décisif — le test"))
    assert decisif.etat is Etat.ECHEC and "make lab3-deux-instances" in decisif.detail


async def test_sans_affinite_le_constat_attend_l_affinite_dabord():
    """Le client ancien échoue déjà (même sans passer par le répartiteur) : la conclusion « c'est le prix de
    l'état conservé » n'a pas encore de sens, il faut d'abord le faire réussir avec affinité."""
    with servir(_serveur_qui_refuse_tout()) as base:
        rapport = await lab3.v.executer(url=f"{base}/mcp")
    constat = next(r for r in rapport.resultats if r.libelle.startswith("Sans affinité de session"))
    assert "Faire d'abord passer" in constat.detail


def test_le_constat_metier_compte_aussi_les_fonctions_async(tmp_path, monkeypatch):
    """ast.AsyncFunctionDef doit aussi être compté, pas seulement ast.FunctionDef."""
    dossier = tmp_path / "serveurs" / "pharos_legacy"
    dossier.mkdir(parents=True)
    (dossier / "serveur.py").write_text(
        "async def lire_mouvements_deux(escale_id):\n    return FICHIER\n", encoding="utf-8")
    monkeypatch.setattr(lab3, "RACINE", tmp_path)
    fonction = next(c.fonction for c in lab3.v._criteres
                    if c.libelle.startswith("Le code métier de lecture des mouvements"))
    detail = fonction(None)
    assert "serveur.py:lire_mouvements_deux" in detail
