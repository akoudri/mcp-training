from pathlib import Path

from outils.verifier.commun import Etat
from tests.aides import importer_client, serveur_demo, servir


async def test_le_squelette_ne_passe_pas():
    with importer_client(Path("gabarits/lab04/client")):
        from outils.verifier import lab4
        with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
            rapport = await lab4.v.executer(url=f"{base}/mcp", sans_modele=True)
    echecs = [r for r in rapport.resultats if r.etat is Etat.ECHEC]
    assert echecs and all("pas encore écrite" in r.detail for r in echecs)
    assert rapport.code_sortie == 1


async def test_sans_pharos_client():
    from outils.verifier import lab4
    with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab4.v.executer(url=f"{base}/mcp", sans_modele=True)
    assert any("make depart LAB=4" in r.detail for r in rapport.resultats)
