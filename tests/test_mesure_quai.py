"""make lab6-mesurer : outils retrouvés par leur schéma, rapport relu par le vérificateur."""

from datetime import date, time

import pytest
from fastmcp import Client, FastMCP
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from outils import mesure_quai
from outils.mesure_quai import SchemasModifies, charger_empreinte, correspondance, empreinte_schemas, lire_mesure
from pharos.openrouter import Appel, Reponse
from tests.aides import servir

NOUVEAUX = {"get_data": "escales_du_jour", "get_data_2": "escales_du_quai", "process": "heure_accostage",
            "info_quai": "caracteristiques_quai", "search": "creneaux_du_navire", "check": "creneau_libre"}
ORIGINE = {n: n for n in NOUVEAUX}


def serveur_quai(noms: dict[str, str] = NOUVEAUX, *, filtre_decrit: bool = False,
                 outil_en_trop: bool = False) -> FastMCP:
    """Les schémas de pharos-quai sous les noms donnés (renommés par défaut) ; en option, un schéma modifié
    ou un outil de plus. Indépendant de serveurs/pharos_quai, qui est réécrit sur les états des labs."""
    mcp = FastMCP("quai")

    @mcp.tool(name=noms["get_data"])
    def a(d: date) -> dict:
        return {}

    if filtre_decrit:
        from typing import Annotated

        from pydantic import Field

        @mcp.tool(name=noms["get_data_2"])
        def b(d: date, f: Annotated[int, Field(description="numéro de quai")]) -> dict:
            return {}
    else:
        @mcp.tool(name=noms["get_data_2"])
        def b(f: int, d: date) -> dict:          # ordre des paramètres inversé : même schéma
            return {}

    @mcp.tool(name=noms["process"])
    def c(x: str, d: date) -> dict:
        return {}

    @mcp.tool(name=noms["info_quai"])
    def e(id: int) -> dict:
        return {}

    @mcp.tool(name=noms["search"])
    def f(q: str, d: date) -> dict:
        return {}

    @mcp.tool(name=noms["check"])
    def g(id: int, d: date, h: time) -> dict:
        return {}

    if outil_en_trop:
        @mcp.tool(name="meteo")
        def m(d: date) -> dict:
            return {}

    return mcp


async def _schemas(mcp) -> dict:
    async with Client(mcp) as c:
        return empreinte_schemas(await c.list_tools())


async def test_catalogue_fourni_correspond_a_lui_meme():
    from serveurs.pharos_quai.serveur import mcp
    noms = correspondance(await _schemas(mcp), charger_empreinte())
    assert sorted(noms) == sorted(NOUVEAUX)


async def test_outils_renommes_retrouves_par_leur_schema():
    assert correspondance(await _schemas(serveur_quai()), charger_empreinte()) == NOUVEAUX


async def test_schema_modifie_refuse():
    with pytest.raises(SchemasModifies, match="schéma introuvable pour : get_data_2"):
        correspondance(await _schemas(serveur_quai(filtre_decrit=True)), charger_empreinte())


async def test_outil_en_trop_refuse():
    with pytest.raises(SchemasModifies, match="7 outils au catalogue, 6 attendus"):
        correspondance(await _schemas(serveur_quai(outil_en_trop=True)), charger_empreinte())


def _modele_qui_choisit(par_question: dict[str, str]):
    def completer(messages, outils, **_):
        nom = par_question[messages[-1]["content"]]
        return Reponse({"role": "assistant", "content": None}, [Appel("a1", nom, {})],
                       {"prompt_tokens": 10, "completion_tokens": 1, "cost": 0.0001})
    return completer


async def test_mesure_puis_relecture():
    choix = {"Quelles escales sont prévues aujourd'hui ?": "escales_du_jour",
             "Quel est le tirant d'eau maximal du quai 3 ?": "caracteristiques_quai",
             "Le Vent d'Autan a-t-il un créneau jeudi matin ?": "creneaux_du_navire",
             "Quelles escales sont prévues au quai 3 demain ?": "escales_du_jour",          # raté
             "À quelle heure le Vent d'Autan peut-il accoster jeudi ?": "creneaux_du_navire"}  # raté
    executions, noms = await mesure_quai.mesurer(serveur_quai(), completer=_modele_qui_choisit(choix))
    texte = mesure_quai.rapport(executions, noms)
    assert "get_data_2 → escales_du_quai" in texte
    relue = lire_mesure(texte)
    assert [l.attendu for l in relue.lignes] == ["escales_du_jour", "caracteristiques_quai", "creneaux_du_navire",
                                                 "escales_du_quai", "heure_accostage"]
    assert all(l.executions == 3 for l in relue.lignes)
    assert relue.reussies == {1, 2, 3}


def test_texte_qui_n_est_pas_une_mesure():
    with pytest.raises(ValueError, match="make lab6-mesurer"):
        lire_mesure("# Avant\n\nRien mesuré.\n")


def test_sans_modele(monkeypatch, capsys):
    monkeypatch.setenv("SANS_MODELE", "1")
    assert mesure_quai.main([]) == 0
    assert "SANS_MODELE=1" in capsys.readouterr().out


def test_serveur_absent(monkeypatch, capsys):
    monkeypatch.delenv("SANS_MODELE", raising=False)
    assert mesure_quai.main(["--url", "http://127.0.0.1:9/mcp"]) == 2
    assert "make lab6-quai" in capsys.readouterr().out


def _observateur_sans_pharos_quai() -> Starlette:
    """Un observateur qui tourne, mais dont pharos-quai est arrêté : relaie un 502 (comme mitmproxy le ferait)."""
    async def repondre(request):
        return PlainTextResponse("Bad Gateway", status_code=502)
    return Starlette(routes=[Route("/mcp", repondre, methods=["POST"])])


def test_pharos_quai_arrete_derriere_l_observateur(monkeypatch, capsys):
    monkeypatch.delenv("SANS_MODELE", raising=False)
    with servir(_observateur_sans_pharos_quai()) as base:
        assert mesure_quai.main(["--url", f"{base}/mcp"]) == 2
    sortie = capsys.readouterr().out
    assert "make lab6-quai" in sortie
    assert "docker compose logs pharos-quai" in sortie


def test_taux_retouche_a_la_main_incoherent_refuse():
    texte = ("Modèle : test\n\n"
             "| 1 | Une question ? | attendu | ✅ a() | ❌ b() | ❌ c() | 2/3 |\n")
    with pytest.raises(ValueError, match="taux incohérent à la question 1"):
        lire_mesure(texte)
