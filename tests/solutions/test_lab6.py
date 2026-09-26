from pathlib import Path

import pytest

from outils.mesure_quai import charger_empreinte, correspondance, empreinte_schemas, lire_mesure
from outils.verifier.commun import Etat
from tests.aides import etat_complet, importer_paquet, servir

pytestmark = pytest.mark.skipif(not Path("solutions/lab06").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    return etat_complet(tmp_path_factory.mktemp("etat-lab6"), 6)


async def test_la_solution_passe_son_verificateur(etat, monkeypatch):
    from outils.verifier import lab6
    monkeypatch.setattr(lab6, "RACINE", etat)
    with importer_paquet(etat, "serveurs"):
        from serveurs.pharos_quai.serveur import mcp
        with servir(mcp.http_app(path="/mcp", json_response=True)) as base:
            rapport = await lab6.v.executer(url=f"{base}/mcp", sans_modele=True)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()


async def test_catalogue_reecrit_memes_schemas_autres_noms(etat):
    from fastmcp import Client
    with importer_paquet(etat, "serveurs"):
        from serveurs.pharos_quai.serveur import mcp
        async with Client(mcp) as c:
            noms = correspondance(empreinte_schemas(await c.list_tools()), charger_empreinte())
    assert all(a != n for a, n in noms.items())


def test_etalonnage_consigne(etat):
    """Seuils du §12 de la spec : au moins deux questions ratées au départ, au moins deux gagnées."""
    avant = lire_mesure((etat / "labs" / "lab6" / "avant.md").read_text(encoding="utf-8"))
    apres = lire_mesure((etat / "labs" / "lab6" / "apres.md").read_text(encoding="utf-8"))
    assert len(avant.reussies) <= 3 and len(apres.reussies - avant.reussies) >= 2
