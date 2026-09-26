"""Vérificateur du LAB 3, sur l'origine (seul le client ancien passe) et sans affinité."""

import pytest

from outils.repartiteur import creer_repartiteur
from outils.verifier import lab3
from outils.verifier.commun import Etat
from serveurs.pharos_legacy.serveur import creer_app
from tests.aides import servir


@pytest.fixture(autouse=True)
def journal(tmp_path, monkeypatch):
    monkeypatch.setenv("PHAROS_JOURNAL_LEGACY", str(tmp_path / "pharos-legacy.jsonl"))


def _par_libelle(rapport) -> dict:
    return {r.libelle.split(" — ")[0][:40]: r for r in rapport.resultats}


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


async def test_sans_affinite_le_critere_decisif_le_dit():
    with servir(creer_app()) as a, servir(creer_app()) as b, servir(creer_repartiteur(a, b)) as r:
        rapport = await lab3.v.executer(url=f"{r}/mcp")
    decisif = next(x for x in rapport.resultats if x.libelle.startswith("Critère décisif — le test"))
    assert decisif.etat is Etat.ECHEC and "make lab3-deux-instances" in decisif.detail
