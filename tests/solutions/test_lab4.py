from pathlib import Path

import pytest

from outils.construire_etats import superposer
from outils.verifier.commun import Etat
from tests.aides import charger_module, importer_client, servir

pytestmark = pytest.mark.skipif(not Path("solutions/lab04").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("etat-lab4")
    superposer(dossier, Path("gabarits"), Path("solutions"), 4)
    return dossier


async def test_la_solution_passe_son_verificateur(etat):
    serveur = charger_module(etat / "serveurs" / "pharos_docs" / "serveur.py", "solution_lab4_serveur")
    with importer_client(etat / "client"):
        from outils.verifier import lab4
        with servir(serveur.mcp.http_app(path="/mcp", json_response=True)) as base:
            rapport = await lab4.v.executer(url=f"{base}/mcp", sans_modele=True)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()


def test_la_trace_garde_le_resultat_sans_secret_et_le_serveur(etat):
    """Champs ajoutés au sous-projet 3 (LAB 8, LAB 13) : resultat borné, secrets masqués, serveur, corrélation."""
    from fastmcp import Context, FastMCP

    mcp = FastMCP("echo")

    @mcp.tool
    def echo(cle_api: str, ctx: Context) -> str:
        """Renvoie son argument, et la corrélation reçue."""
        meta = ctx.request_context.meta
        brut = meta.model_dump(by_alias=True) if hasattr(meta, "model_dump") else dict(meta or {})
        return f"reçu {cle_api} / {brut.get('pharos/correlation')}"

    with importer_client(etat / "client"):
        from outils.verifier.modele_simule import ModeleSimule, appel
        from pharos_client import boucle

        with ModeleSimule([[appel("a1", "echo", {"cle_api": "sk-secret-42"})], "fini"]):
            _, [e] = boucle.executer("question", url=mcp)
    assert "sk-secret-42" not in repr(e)
    assert e.resultat == f"reçu *** / {e.correlation}" and e.serveur == "echo"
