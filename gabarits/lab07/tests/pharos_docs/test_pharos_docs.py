"""Suite de tests de pharos-docs (LAB 7). Une famille par section ; la première est remplie en exemple.

Rappels, fastmcp 4.0.10 :
    r = await client.call_tool("outil", {...}, raise_on_error=False)   → r.is_error, r.data, r.content[0].text
    outils = await client.list_tools()                                  → o.name, o.description, o.input_schema
    ressources = await client.list_resources()                          → r.uri, r.size, r.mime_type
    [contenu] = await client.read_resource(uri)                         → contenu.text, contenu.mime_type
    p = await client.get_prompt("nom", {...})                           → p.messages[i].content
Pièges : un « await » oublié donne un test vert qui ne teste rien — vérifier une fois qu'un test censé
échouer échoue. Ni HTTP, ni modèle, ni sleep : moins de dix secondes (make lab7-tests CHRONO=1).
"""

import pytest


# 1. Schémas — exemple rempli
async def test_sujet_hors_enumeration_refuse_avant_le_code_metier(client):
    r = await client.call_tool("rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": "retards"},
                               raise_on_error=False)
    assert r.is_error and "validation" in r.content[0].text.lower()


# 2. Erreurs métier — les trois du LAB 1
async def test_erreurs_metier(client):
    pytest.fail("À écrire : escale inconnue, contrat absent, sujet absent.")


# 3. Formes et bornes
async def test_extrait_borne(client):
    pytest.fail("À écrire : rechercher_clause renvoie un extrait borné, jamais le contrat entier.")


# 4. Handles — les trois refus du LAB 5
async def test_refus_des_handles(client):
    pytest.fail("À écrire : expiré (pharos_docs.jetons.signer(..., duree_s=-1)), altéré d'un caractère, hors portée.")


# 5. Ressources
async def test_ressources(client):
    pytest.fail("À écrire : resources/list annonce la bonne taille et le bon type ; resources/read répond.")


# 6. Empreinte du catalogue
async def test_empreinte_du_catalogue(client):
    pytest.fail("À écrire : comparer outils.empreinte.empreinte(await client.list_tools()) au contenu de "
                "tests/empreinte_catalogue.json (make lab7-empreinte le génère).")
