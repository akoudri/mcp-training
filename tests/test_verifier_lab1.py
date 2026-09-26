from pathlib import Path

from outils.verifier import lab1
from outils.verifier.commun import Etat
from tests.aides import charger_module, servir


async def test_le_squelette_ne_passe_pas():
    squelette = charger_module(Path("gabarits/lab01/serveurs/pharos_docs/serveur.py"), "gabarit_lab1_serveur")
    with servir(squelette.mcp.http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab1.v.executer(url=f"{base}/mcp", sans_modele=True)
    premier = rapport.resultats[0]
    assert premier.etat is Etat.ECHEC and "extraire_dates_contractuelles" in premier.detail
    assert rapport.code_sortie == 1
    assert any(r.etat is Etat.SAUTE for r in rapport.resultats)           # banc sauté sans modèle
