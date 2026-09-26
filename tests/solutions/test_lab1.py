from pathlib import Path

import pytest
import yaml
from fastmcp import Client

from outils.construire_etats import superposer
from outils.verifier import lab1
from outils.verifier.commun import Etat
from tests.aides import charger_module, servir

pytestmark = pytest.mark.skipif(not Path("solutions/lab01").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def serveur(tmp_path_factory):
    etat = tmp_path_factory.mktemp("etat-lab1")
    superposer(etat, Path("gabarits"), Path("solutions"), 1)
    return charger_module(etat / "serveurs" / "pharos_docs" / "serveur.py", "solution_lab1_serveur")


def contrats():
    escales = yaml.safe_load(Path("donnees/corpus/escales.yaml").read_text(encoding="utf-8"))["escales"]
    return [(e["escale_id"], e["contrat"]) for e in escales if e.get("contrat")]


@pytest.mark.parametrize("escale_id, contrat", contrats())
async def test_dates_de_tous_les_contrats(serveur, escale_id, contrat):
    async with Client(serveur.mcp) as c:
        r = await c.call_tool("extraire_dates_contractuelles", {"escale_id": escale_id})
    assert (r.data["signature"], r.data["prise_effet"], r.data["echeance"]) == \
        (contrat["signature"].isoformat(), contrat["prise_effet"].isoformat(), contrat["echeance"].isoformat())


async def test_penalites_vent_d_autan(serveur):
    async with Client(serveur.mcp) as c:
        r = await c.call_tool("rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": "penalites"})
    assert r.data["article"] == "Article 7 — Pénalités de retard" and "1 850" in r.data["texte"]
    assert len(r.data["texte"]) <= serveur.EXTRAIT_MAX


async def test_la_solution_passe_son_verificateur(serveur):
    with servir(serveur.mcp.http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab1.v.executer(url=f"{base}/mcp", sans_modele=True)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()
