"""pharos-quai : le métier est correct sur la table de vérité ; le catalogue fourni est celui du brief."""

import json
from datetime import date, time

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from serveurs.pharos_quai import metier
from tests.aides import RACINE_KIT, quai_d_origine

EMPREINTE = RACINE_KIT / "tests" / "empreinte_schemas_quai.json"
JEUDI = date(2026, 10, 8)
# Le tableau « Le catalogue fourni » du brief du LAB 6, mot pour mot.
CATALOGUE_DU_BRIEF = {
    "get_data": "Récupère les données depuis la base en utilisant l'index construit au démarrage.",
    "get_data_2": "Variante de get_data avec filtrage.",
    "process": "Traite un élément.",
    "info_quai": "Informations.",
    "search": "Recherche.",
    "check": "Vérifie la disponibilité.",
}


async def _outils():
    from serveurs.pharos_quai.serveur import mcp
    async with Client(mcp) as c:
        return await c.list_tools()


def _canonique(schema: dict) -> str:
    return json.dumps({**schema, "required": sorted(schema.get("required", []))}, sort_keys=True)


@quai_d_origine
async def test_catalogue_fourni_mot_pour_mot():
    assert {o.name: o.description for o in await _outils()} == CATALOGUE_DU_BRIEF


async def test_schemas_identiques_a_l_empreinte():
    """Vrai sur main comme sur les états des labs : la réécriture ne touche pas les schémas (noms libres)."""
    empreinte = json.loads(EMPREINTE.read_text(encoding="utf-8"))
    assert sorted(empreinte) == sorted(CATALOGUE_DU_BRIEF)
    assert sorted(_canonique(o.input_schema) for o in await _outils()) == sorted(map(_canonique, empreinte.values()))


def test_aucun_parametre_decrit():
    schemas = json.loads(EMPREINTE.read_text(encoding="utf-8"))
    assert all("description" not in p for s in schemas.values() for p in s["properties"].values())
    assert json.dumps(schemas).count('"title"') == 0


def test_question_1_escales_du_jour():
    ids = [e["escale_id"] for e in metier.escales_du_jour(date(2026, 10, 6))["escales"]]
    assert ids == ["ESC-2026-0406", "ESC-2026-0408", "ESC-2026-0409"]


def test_question_2_caracteristiques_du_quai_3():
    q = metier.caracteristiques_quai(3)
    assert q["tirant_eau_max_m"] == 13.5 and q["longueur_m"] == 300


def test_question_3_creneaux_du_vent_d_autan():
    r = metier.creneaux_du_navire("Vent d'Autan", JEUDI)
    assert r["creneaux"] == [{"quai": 3, "debut": "06:00", "fin": "20:00", "escale_id": "ESC-2026-0412"}]
    assert metier.disponibilite(3, JEUDI, time(7, 0))["libre"] is False
    assert metier.disponibilite(3, JEUDI, time(4, 30))["libre"] is True


def test_question_4_escales_au_quai_3_demain():
    assert metier.escales_du_quai(date(2026, 10, 7), 3)["escales"] == []
    assert [e["escale_id"] for e in metier.escales_du_quai(date(2026, 10, 7), 1)["escales"]] == ["ESC-2026-0410"]


def test_question_5_heure_d_accostage_du_vent_d_autan():
    r = metier.heure_accostage("Vent d'Autan", JEUDI)
    assert (r["heure"], r["quai"], r["jusqu_a"], r["maree_requise"], r["reserve"]) == ("06:00", 3, "07:30", True, True)


def test_heure_d_accostage_sans_reservation_ni_maree():
    r = metier.heure_accostage("Belle-Île", JEUDI)
    assert (r["heure"], r["quai"], r["maree_requise"], r["reserve"]) == ("00:00", 1, False, False)


@pytest.mark.parametrize("nom", ["le vent d’autan", "  VENT D’AUTAN ", "Le Vent d’Autan"])
def test_nom_de_navire_tolerant(nom):
    assert metier.creneaux_du_navire(nom, JEUDI)["navire"] == "Vent d'Autan"

@pytest.mark.parametrize("appel, attendu", [
    (lambda: metier.creneaux_du_navire("Nautilus", JEUDI), "Navires connus : Albatros"),
    (lambda: metier.caracteristiques_quai(7), "quais 1 à 4"),
    (lambda: metier.disponibilite(3, date(2026, 10, 10), time(7)), "du 2026-10-06 au 2026-10-08"),
    (lambda: metier.heure_accostage("Vent d'Autan", date(2026, 10, 12)), "du 2026-10-06 au 2026-10-08"),
])
def test_erreurs_metier_qui_disent_quoi_faire(appel, attendu):
    with pytest.raises(ToolError, match=attendu):
        appel()


async def test_erreur_metier_a_travers_le_protocole():
    from serveurs.pharos_quai.serveur import mcp
    async with Client(mcp) as c:
        # l'outil de search, quel que soit son nom : le seul dont le schéma a un paramètre q
        outil = next(o.name for o in await c.list_tools() if "q" in o.input_schema["properties"])
        r = await c.call_tool(outil, {"q": "Nautilus", "d": "2026-10-08"}, raise_on_error=False)
    assert r.is_error and "Navires connus" in r.content[0].text
