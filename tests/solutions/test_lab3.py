import importlib
import json
from pathlib import Path

import pytest
from fastmcp.exceptions import McpError

from outils.client_test import ClientTest
from outils.repartiteur import creer_repartiteur
from outils.scenario_legacy import derouler
from outils.verifier.commun import Etat
from tests.aides import etat_complet, importer_paquet, servir

pytestmark = pytest.mark.skipif(not Path("solutions/lab03").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")


@pytest.fixture(scope="module")
def serveur(tmp_path_factory):
    etat = etat_complet(tmp_path_factory.mktemp("etat-lab3"), 3)
    with importer_paquet(etat, "serveurs"):
        return importlib.import_module("serveurs.pharos_legacy.serveur")


@pytest.fixture(autouse=True)
def environnement(monkeypatch, tmp_path):
    monkeypatch.setenv("CLE_SERVEUR", "cle-de-test")
    monkeypatch.setenv("PHAROS_JOURNAL_LEGACY", str(tmp_path / "pharos-legacy.jsonl"))


@pytest.mark.parametrize("revision", ["2025-11-25", "2026-07-28"])
async def test_un_deploiement_deux_clients(serveur, revision):
    with servir(serveur.creer_app()) as base:
        d = await derouler(f"{base}/mcp", revision)
    assert d.erreur is None and len(d.mouvements) == 57
    fuite = any("hdl_" in e.corps_reponse for e in d.echanges)
    assert fuite is (revision == "2026-07-28")


async def test_catalogue_et_codes_adaptes_a_la_revision(serveur):
    with servir(serveur.creer_app()) as base:
        schemas, codes = {}, {}
        for revision in ("2025-11-25", "2026-07-28"):
            async with ClientTest(f"{base}/mcp", revision) as c:
                page_suivante = next(o for o in await c.outils() if o.name == "page_suivante")
                schemas[revision] = page_suivante.input_schema.get("required", [])
                with pytest.raises(McpError) as exc:
                    await c.appeler("etat_escale", {"escale_id": "ESC-2026-9999"})
                codes[revision] = exc.value.error.code
    assert schemas == {"2025-11-25": [], "2026-07-28": ["handle"]}
    assert codes == {"2025-11-25": -32002, "2026-07-28": -32602}


async def test_journal_une_ligne_par_requete(serveur, tmp_path):
    with servir(serveur.creer_app()) as base:
        d = await derouler(f"{base}/mcp", "2025-11-25")
    lignes = [json.loads(l) for l in (tmp_path / "pharos-legacy.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(lignes) == len(d.echanges) and {l["revision"] for l in lignes} == {"2025-11-25"}


async def test_la_solution_passe_son_verificateur(serveur, monkeypatch):
    from outils.verifier import lab3
    with servir(serveur.creer_app()) as a, servir(serveur.creer_app()) as b, \
         servir(creer_repartiteur(a, b, affinite=True)) as r:
        monkeypatch.setenv("AMONT_LEGACY_A", a)
        monkeypatch.setenv("AMONT_LEGACY_B", b)
        rapport = await lab3.v.executer(url=f"{r}/mcp", sans_modele=True)
    assert [x for x in rapport.resultats if x.etat is Etat.ECHEC] == [], rapport.texte()
    assert "échoue" in rapport.resultats[-1].detail                  # constat sans affinité
