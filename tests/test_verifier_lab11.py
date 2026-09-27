"""Vérificateur du LAB 11 : sur un serveur jouet dont on active les défauts un par un. Les mocks sont servis dans
le processus, la base est simulée (compter_escales remplacé) ; aucun modèle."""

import asyncio
import shutil
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.utilities.tasks import TaskConfig

from outils.verifier.commun import Etat
from tests.aides import BOUCLE_MINIMALE, charger_module, importer_client

TOTAL = 6
BOUCLE_TACHES = BOUCLE_MINIMALE.replace("from pharos_client import modele", "from pharos_client import modele, taches") \
    .replace("res = s.appeler(a.nom, a.arguments, correlation=correlation)",
             "res = taches.appeler_ou_suivre(s, a.nom, a.arguments, correlation=correlation)")


def jouet(*, parametre=False, minuteur=False, faux_total=False, toujours_tache=False, sans_plan_b=False,
          ignore_panne=False, deux_outils=False) -> FastMCP:
    taches = charger_module(Path("gabarits/lab11/serveurs/pharos_ops/taches.py"), f"jouet11_{id(object())}")

    def decider(nom, arguments, client_declare):
        if arguments.get("quai") is not None and not toujours_tache:
            return taches.DIRECT
        if client_declare or sans_plan_b:
            return taches.TACHE if client_declare else taches.DIRECT
        raise ToolError("Journée impossible sans l'extension Tasks : recalculer quai par quai (quai=1 à 7).")

    taches.decider = decider
    mcp = FastMCP("jouet11")
    mcp.add_extension(taches.ExtensionRecalcul())

    async def calcul(ctx, quai):
        total = 1 if quai else TOTAL
        for i in range(1, total + 1):
            await asyncio.sleep(0.12)
            panne = httpx.get(f"{__import__('os').environ['METEO_URL'].rsplit('/', 1)[0]}/_config").json()["panne"]
            if panne and not ignore_panne:
                raise ToolError("Recalcul interrompu : météo indisponible. Ne pas conclure sur le plan.")
            message = f"{i * 100 // total} %" if minuteur else f"{i} escales sur {99 if faux_total else total}"
            await ctx.report_progress(i, total, message)
        return {"escales": total, "quai": quai, "placements": [f"ESC-{n}" for n in range(total)]}

    tache = TaskConfig(mode="optional", poll_interval=timedelta(seconds=0.1))
    if parametre:
        @mcp.tool(name="recalculer_plan_quai", task=tache)
        async def avec_parametre(date: str, ctx: Context, quai: int | None = None, asynchrone: bool = False) -> dict:
            """Recalcul."""
            return await calcul(ctx, quai)
    else:
        @mcp.tool(name="recalculer_plan_quai", task=tache)
        async def recalculer_plan_quai(date: str, ctx: Context, quai: int | None = None) -> dict:
            """Recalcul."""
            return await calcul(ctx, quai)

    if deux_outils:
        @mcp.tool
        async def recalculer_plan_journee(date: str) -> dict:
            """Recalcul de la journée."""
            return {}

    return mcp


def _client(dossier: Path, boucle: str) -> Path:
    shutil.copytree("gabarits/lab04/client", dossier, dirs_exist_ok=True)
    shutil.copytree("gabarits/lab11/client", dossier, dirs_exist_ok=True)
    (dossier / "pharos_client" / "boucle.py").write_text(boucle, encoding="utf-8")
    return dossier


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    return _client(tmp_path_factory.mktemp("client11"), BOUCLE_TACHES)


@pytest.fixture(scope="module")
def client_sans_suivi(tmp_path_factory):
    return _client(tmp_path_factory.mktemp("client11-nu"), BOUCLE_MINIMALE)


async def _rapport(mcp, url, client, monkeypatch):
    from outils.verifier import lab11

    async def total():
        return TOTAL

    monkeypatch.setattr(lab11, "charger_serveur", lambda: mcp)
    monkeypatch.setattr(lab11, "compter_escales", total)
    monkeypatch.setenv("PHAROS_VITESSE", "rapide")                   # le vérificateur la change : restaurée ici
    with importer_client(client):
        return await lab11.v.executer(url=f"{url}/_sante", sans_modele=True)


def _echecs(rapport) -> dict[str, str]:
    return {r.libelle: r.detail for r in rapport.resultats if r.etat is Etat.ECHEC}


def _un(echecs: dict, mot: str) -> str:
    [detail] = [d for libelle, d in echecs.items() if mot in libelle]
    return detail


async def test_jouet_correct(mocks_servis, client, monkeypatch):
    rapport = await _rapport(jouet(), mocks_servis, client, monkeypatch)
    assert _echecs(rapport) == {}, rapport.texte()
    assert httpx.get(f"{mocks_servis}/_config").json()["panne"] is None             # panne levée à la fin


@pytest.mark.parametrize("defaut, critere, attendu", [
    ({"parametre": True}, "aucun paramètre", "asynchrone"),
    ({"deux_outils": True}, "aucun paramètre", "un seul"),
    ({"minuteur": True}, "compte réel", "au moins deux"),
    ({"faux_total": True}, "compte réel", f"jeudi compte {TOTAL}"),
    ({"toujours_tache": True}, "Immédiat", "quai=3 rend une tâche"),
    ({"sans_plan_b": True}, "Plan B", "au lieu d'un refus"),
    ({"ignore_panne": True}, "Trois issues", "sans erreur"),
])
async def test_defauts(mocks_servis, client, monkeypatch, defaut, critere, attendu):
    echecs = _echecs(await _rapport(jouet(**defaut), mocks_servis, client, monkeypatch))
    assert attendu in _un(echecs, critere), echecs


async def test_boucle_sans_suivi_des_taches(mocks_servis, client_sans_suivi, monkeypatch):
    echecs = _echecs(await _rapport(jouet(), mocks_servis, client_sans_suivi, monkeypatch))
    assert list(echecs) == ["Critère décisif — la boucle affiche une progression qui avance, et ne réinjecte que "
                            "le résultat reçu."] and "appeler_ou_suivre" in _un(echecs, "décisif"), echecs


async def test_gabarit_decider_a_ecrire(mocks_servis, client, monkeypatch, tmp_path):
    taches = charger_module(Path("gabarits/lab11/serveurs/pharos_ops/taches.py"), "gabarit11_verif")
    mcp = FastMCP("gabarit11")
    mcp.add_extension(taches.ExtensionRecalcul())

    @mcp.tool(task=TaskConfig(mode="optional"))
    async def recalculer_plan_quai(date: str, ctx: Context, quai: int | None = None) -> dict:
        """Recalcul."""
        return {}

    rapport = await _rapport(mcp, mocks_servis, client, monkeypatch)
    ok = [r.libelle for r in rapport.resultats if r.etat is Etat.OK]
    assert ok == ["recalculer_plan_quai est au catalogue, sous le nom du brief.",
                  "La décision vient du serveur : aucun paramètre ne la commande, un seul outil de recalcul."]
    assert "decider : à écrire" in _un(_echecs(rapport), "Immédiat")


async def test_mocks_ou_base_absents(client, monkeypatch):
    from outils import lab10
    from outils.servir import servir
    from outils.verifier import lab11

    monkeypatch.setattr(lab10, "URL_MOCKS", "http://127.0.0.1:1")
    with servir(FastMCP("x").http_app(path="/mcp", json_response=True)) as url:
        monkeypatch.setattr(lab11, "charger_serveur", lambda: jouet())
        with importer_client(client):
            rapport = await lab11.v.executer(url=f"{url}/mcp", sans_modele=True)
    assert "make lab10-mocks" in rapport.texte()
