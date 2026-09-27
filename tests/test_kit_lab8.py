"""Kit du LAB 8 : gabarit de pharos-data (signature imposée), vérité de référence, questions du banc."""

import asyncio
from pathlib import Path

from fastmcp import Client

from outils import banc, verite_lab8
from tests.aides import base_requise, charger_module


async def test_gabarit_signature_imposee_et_outil_a_ecrire():
    serveur = charger_module(Path("gabarits/lab08/serveurs/pharos_data/serveur.py"), "gabarit_lab8")
    async with Client(serveur.mcp) as c:
        [outil] = await c.list_tools()
        r = await c.call_tool_mcp("requete_mouvements", {"date_debut": "2026-09-28", "date_fin": "2026-10-04"})
    schema = outil.input_schema
    assert outil.name == "requete_mouvements" and schema["required"] == ["date_debut", "date_fin"]
    assert set(schema["properties"]) == {"date_debut", "date_fin", "quai", "type_conteneur", "sens"}
    assert "Europe/Paris" in outil.description and "date_fin incluse" in outil.description
    assert r.is_error
    assert serveur.PARAMETRES_POOL["server_settings"] == {"application_name": "pharos-data"}


def test_questions_du_banc():
    [q] = banc.charger_questions("outils/questions/lab8.yaml")
    assert q.attendu == "requete_mouvements" and q.arguments_attendus == {"quai": 5, "sens": "debarquement"}


@base_requise
def test_verite(base_de_test, capsys):
    v = asyncio.run(verite_lab8.verite())
    assert (v.nombre, v.nombre_utc) == (16, 15)
    assert verite_lab8.main() == 0
    sortie = capsys.readouterr().out
    assert "Réponse exacte : 16" in sortie and "UTC" in sortie and "Europe/Paris" in sortie
