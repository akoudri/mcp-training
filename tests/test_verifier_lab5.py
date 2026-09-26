from outils.verifier.commun import Etat
from tests.aides import serveur_demo, servir


async def test_sans_ouvrir_dossier(monkeypatch):
    monkeypatch.setenv("CLE_SERVEUR", "cle-de-test")
    from outils.verifier import lab5
    with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab5.v.executer(url=f"{base}/mcp", sans_modele=True)
    echec = next(r for r in rapport.resultats if r.etat is Etat.ECHEC)
    assert "ouvrir_dossier" in echec.detail
