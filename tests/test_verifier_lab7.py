from outils.verifier.commun import Etat
from tests.aides import serveur_demo, servir


async def test_sans_ressources():
    from outils.verifier import lab7
    with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab7.v.executer(url=f"{base}/mcp", sans_modele=True)
    assert rapport.resultats[0].etat is Etat.ECHEC and "ressources" in rapport.resultats[0].detail
    assert rapport.code_sortie == 1
