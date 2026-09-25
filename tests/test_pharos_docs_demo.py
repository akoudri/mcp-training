from pathlib import Path

import pytest
from fastmcp import Client

from labs.lab0.serveur.serveur import creer_serveur


@pytest.fixture(autouse=True)
def corpus(monkeypatch):
    monkeypatch.setenv("PHAROS_DOCUMENTS", str(Path("donnees/documents").resolve()))


async def appeler(outil, arguments, jumeau=False):
    async with Client(creer_serveur(outil_jumeau=jumeau)) as client:
        return await client.call_tool(outil, arguments, raise_on_error=False)


async def test_trois_outils_et_schemas_verbeux():
    async with Client(creer_serveur()) as client:
        outils = {o.name: o for o in await client.list_tools()}
    assert set(outils) == {"lister_documents", "lire_document", "rechercher_clause"}
    schema = outils["rechercher_clause"].input_schema
    assert schema["properties"]["sujet"]["enum"] == ["penalites", "delais", "manutention", "assurance"]
    assert all("description" in p for p in schema["properties"].values())
    assert len(outils["rechercher_clause"].description) > 200


async def test_outil_jumeau_conditionnel():
    async with Client(creer_serveur(outil_jumeau=True)) as client:
        noms = {o.name for o in await client.list_tools()}
    assert "chercher_clause_contrat" in noms and len(noms) == 4


async def test_lister_documents():
    r = await appeler("lister_documents", {"escale_id": "ESC-2026-0412"})
    assert not r.is_error
    assert {d["document_id"] for d in r.data["documents"]} == {"CM-0412", "BL-0412-1", "BL-0412-2", "AE-0412"}


@pytest.mark.parametrize("escale", ["ESC-2026-9999", "esc-2026-0412", "ESC-2026-412"])
async def test_lister_documents_escale_inconnue_vide_avec_succes(escale):
    r = await appeler("lister_documents", {"escale_id": escale})
    assert not r.is_error and r.data["documents"] == []


async def test_lire_document_par_plage():
    r = await appeler("lire_document", {"document_id": "CM-0412", "page_debut": 1, "page_fin": 2})
    assert not r.is_error
    assert [p["numero"] for p in r.data["pages"]] == [1, 2]


@pytest.mark.parametrize("args, attendu", [
    ({"document_id": "CM-9999", "page_debut": 1, "page_fin": 1}, "lister_documents"),
    ({"document_id": "CM-0412", "page_debut": 5, "page_fin": 2}, "page_debut"),
    ({"document_id": "CM-0412", "page_debut": 55, "page_fin": 70}, "56 pages"),
    ({"document_id": "CM-0412", "page_debut": 1, "page_fin": 30}, "20 pages"),
])
async def test_lire_document_erreurs_metier(args, attendu):
    r = await appeler("lire_document", args)
    assert r.is_error
    assert attendu in r.content[0].text
    assert "Traceback" not in r.content[0].text


async def test_rechercher_clause_penalites():
    r = await appeler("rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": "penalites"})
    assert not r.is_error
    assert r.data["article"] == "Article 7 — Pénalités de retard"
    assert "1 850 €" in r.data["texte"] and r.data["page"] >= 1


@pytest.mark.parametrize("args, attendu", [
    ({"escale_id": "ESC-2026-9999", "sujet": "penalites"}, "ESC-AAAA-NNNN"),
    ({"escale_id": "ESC-2026-0406", "sujet": "penalites"}, "connaissement"),
    ({"escale_id": "ESC-2026-0408", "sujet": "assurance"}, "penalites"),
])
async def test_rechercher_clause_erreurs_metier(args, attendu):
    r = await appeler("rechercher_clause", args)
    assert r.is_error and attendu in r.content[0].text


async def test_sujet_hors_enumeration_refuse():
    r = await appeler("rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": "retards"})
    assert r.is_error
