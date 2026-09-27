"""Suite de tests de pharos-docs v1 — solution de référence du LAB 7 (six familles)."""

import json

import pytest

from outils.empreinte import CHEMIN, empreinte
from pharos_docs import extraction, jetons


async def _appel(client, outil, arguments):
    return await client.call_tool(outil, arguments, raise_on_error=False)


# 1. Schémas
async def test_sujet_hors_enumeration_refuse_avant_le_code_metier(client):
    r = await _appel(client, "rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": "retards"})
    assert r.is_error and "validation" in r.content[0].text.lower()


# 2. Erreurs métier
@pytest.mark.parametrize("arguments, attendu", [
    ({"escale_id": "ESC-2026-9999", "sujet": "penalites"}, "ESC-AAAA-NNNN"),
    ({"escale_id": "ESC-2026-0406", "sujet": "penalites"}, "BL-0406-1"),
    ({"escale_id": "ESC-2026-0408", "sujet": "assurance"}, "penalites"),
])
async def test_erreurs_metier(client, arguments, attendu):
    r = await _appel(client, "rechercher_clause", arguments)
    texte = r.content[0].text
    assert r.is_error and attendu in texte and not texte.startswith("Error calling tool")


# 3. Formes et bornes
@pytest.mark.parametrize("sujet", ["penalites", "delais", "manutention", "assurance"])
async def test_extrait_borne(client, sujet):
    r = await _appel(client, "rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": sujet})
    assert not r.is_error and 0 < len(r.data["texte"]) <= 1500


# 4. Handles
async def _handle(client):
    return (await _appel(client, "ouvrir_dossier", {"escale_id": "ESC-2026-0412"})).data["handle"]


async def test_handle_expire(client):
    h = jetons.signer({"e": "ESC-2026-0412", "d": "CM-0412"}, "cle-de-test", duree_s=-1)
    r = await _appel(client, "lire_section", {"handle": h, "section": "CM-0412:s07"})
    assert r.is_error and "a expiré" in r.content[0].text


async def test_handle_altere(client):
    h = await _handle(client)
    altere = h[:-3] + ("A" if h[-3] != "A" else "B") + h[-2:]
    r = await _appel(client, "lire_section", {"handle": altere, "section": "CM-0412:s07"})
    assert r.is_error and "ouvrir_dossier" in r.content[0].text


async def test_handle_hors_portee(client):
    r = await _appel(client, "lire_section", {"handle": await _handle(client), "section": "CM-0405:s07"})
    assert r.is_error and "n'appartient pas" in r.content[0].text


# 5. Ressources
async def test_ressources_taille_et_type(client):
    ressources = {str(r.uri): r for r in await client.list_resources()}
    assert len(ressources) == len(extraction.documents())
    r = ressources["pharos://escales/ESC-2026-0409/documents/CM-0409"]
    [contenu] = await client.read_resource(str(r.uri))
    assert r.mime_type == contenu.mime_type == "text/plain"
    assert r.size == len(contenu.text.encode("utf-8"))
    assert "lister_documents" not in {o.name for o in await client.list_tools()}


async def test_prompt_joint_le_contrat(client):
    rendu = await client.get_prompt("note_alerte_escale", {"escale_id": "ESC-2026-0412"})
    assert str(rendu.messages[-1].content.resource.uri).endswith("/documents/CM-0412")


# 6. Empreinte du catalogue
async def test_empreinte_du_catalogue(client):
    assert empreinte(await client.list_tools()) == json.loads(CHEMIN.read_text(encoding="utf-8")), \
        "Catalogue modifié : si c'est voulu, make lab7-empreinte et committer le fichier AVEC le changement."
