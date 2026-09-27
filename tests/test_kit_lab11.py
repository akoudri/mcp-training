"""Kit du LAB 11 : suivi des tâches côté client, extension côté serveur (decider à écrire), profils de client,
cibles et démarrage. Serveurs jouets en mémoire ou servis dans le processus ; ni base, ni Docker, ni modèle."""

import asyncio
import re
import time
from datetime import timedelta
from pathlib import Path

import mcp_types
import pytest
from fastmcp import Client, Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.utilities.tasks import TaskConfig

from outils import labs
from outils.client_test import ClientTest
from outils.servir import servir
from tests.aides import charger_module, importer_client

TACHES_SERVEUR = charger_module(Path("gabarits/lab11/serveurs/pharos_ops/taches.py"), "gabarit_lab11_taches")


GABARIT_TACHES = Path("gabarits/lab11/serveurs/pharos_ops/taches.py")
SOLUTION_TACHES = Path("solutions/lab11/serveurs/pharos_ops/taches.py")


def jouet(decider=None, total=4, pause=0.3, echouer=False, chemin=GABARIT_TACHES) -> FastMCP:
    """recalculer_plan_quai en tâche optionnelle, derrière l'extension fournie, avec un decider au choix."""
    module = charger_module(chemin, f"jouet_taches_{id(decider)}_{chemin.parts[0]}")
    if decider is not None:
        module.decider = decider
    mcp = FastMCP("jouet")
    mcp.add_extension(module.ExtensionRecalcul())

    @mcp.tool(task=TaskConfig(mode="optional", poll_interval=timedelta(seconds=0.05)))
    async def recalculer_plan_quai(date: str, ctx: Context, quai: int | None = None) -> dict:
        n = 1 if quai else total
        for i in range(1, n + 1):
            await asyncio.sleep(pause)
            if echouer:
                raise ToolError("Recalcul interrompu : météo indisponible.")
            await ctx.report_progress(i, n, f"{i} escales sur {n}")
        return {"escales": n, "quai": quai}

    @mcp.tool
    def autre() -> str:
        """Un outil que l'extension laisse passer."""
        return "ok"

    return mcp


def decider_reference(nom, arguments, client_declare):
    if arguments.get("quai") is not None:
        return "direct"
    if client_declare:
        return "tache"
    raise ToolError("Plan B : recalculer quai par quai (quai=1 à 7).")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """Le client du gabarit du LAB 4, plus taches.py (gabarit du LAB 11)."""
    import shutil

    dossier = tmp_path_factory.mktemp("client")
    shutil.copytree("gabarits/lab04/client", dossier, dirs_exist_ok=True)
    shutil.copytree("gabarits/lab11/client", dossier, dirs_exist_ok=True)
    return dossier


async def test_gabarit_serveur_decider_a_ecrire_et_extension_transparente():
    with pytest.raises(NotImplementedError, match="à écrire"):
        TACHES_SERVEUR.decider("recalculer_plan_quai", {"date": "2026-10-08"}, True)
    async with Client(jouet()) as c:
        assert (await c.call_tool("autre", {})).data == "ok"                     # hors de recalculer : inchangé
        r = await c.call_tool("recalculer_plan_quai", {"date": "2026-10-08"}, raise_on_error=False)
    assert r.is_error and "decider : à écrire" in r.content[0].text


@pytest.mark.parametrize("chemin", [
    GABARIT_TACHES,
    pytest.param(SOLUTION_TACHES, marks=pytest.mark.skipif(
        not SOLUTION_TACHES.is_file(), reason="solutions absentes : branche main")),
])
async def test_decider_qui_rend_une_mauvaise_valeur_est_dit_au_client(chemin):
    async with Client(jouet(lambda nom, arguments, declare: "TACHE", chemin=chemin)) as c:
        r = await c.call_tool("recalculer_plan_quai", {"date": "2026-10-08"}, raise_on_error=False)
    assert r.is_error and "decider doit rendre 'direct' ou 'tache'" in r.content[0].text and "'TACHE'" in r.content[0].text


def test_hors_budget_et_tache_perdue_rendent_un_resultat_inconnu(client):
    with importer_client(client):
        from pharos_client import taches
        from pharos_client.transport import Session

        with Session(jouet(decider_reference, pause=2), delai_s=0.5) as s:
            lent = taches.appeler_ou_suivre(s, "recalculer_plan_quai", {"date": "2026-10-08", "quai": 3},
                                            afficher=lambda l: None)
            cree = s._executer(s._client.session.call_tool(name="recalculer_plan_quai", arguments={"date": "2026-10-08"},
                                                           allow_claimed=True))
            s._executer(taches.ToolTask(s._client, "recalculer_plan_quai", cree).cancel())
            fantome = taches.Tache(s, "recalculer_plan_quai", cree.model_copy(update={"task_id": "tache-inconnue"}))
            perdue = taches.suivre(fantome, afficher=lambda l: None)
            perdue_resultat = fantome.resultat()
    assert lent.est_erreur and "n'a pas répondu dans le budget de tour" in lent.texte
    assert "résultat inconnu, ne rien en conclure" in lent.texte
    for r in (perdue, perdue_resultat):
        assert r.est_erreur and "perdue côté serveur" in r.texte and "résultat inconnu, ne rien en conclure" in r.texte


def test_suivi_cote_client_trois_cas(client):
    with importer_client(client):
        from pharos_client import taches
        from pharos_client.transport import Session

        lignes = []
        with Session(jouet(decider_reference)) as s:
            direct = taches.appeler_ou_suivre(s, "recalculer_plan_quai", {"date": "2026-10-08", "quai": 3},
                                              afficher=lignes.append)
            suivi = taches.appeler_ou_suivre(s, "recalculer_plan_quai", {"date": "2026-10-08"}, afficher=lignes.append)
            tache = taches.soumettre(s, "recalculer_plan_quai", {"date": "2026-10-08"})
            assert isinstance(tache, taches.Tache) and tache.intervalle_s == taches.INTERVALLE_MIN_S
            tache.annuler()
            deadline = time.monotonic() + 5
            while tache.etat().statut != "cancelled" and time.monotonic() < deadline:
                time.sleep(0.05)
            annule = tache.resultat()
    assert not direct.est_erreur and '"quai": 3' in direct.texte.replace('"quai":3', '"quai": 3')
    assert not suivi.est_erreur and '"escales"' in suivi.texte
    progressions = [l for l in lignes if "escales sur" in l]
    # La dernière progression peut être remplacée par l'état terminal avant d'être vue : 1 à 3 au moins, dans l'ordre.
    assert progressions[:3] == [f"    … recalculer_plan_quai : {i} escales sur 4" for i in range(1, 4)]
    assert any("acceptée par le serveur" in l for l in lignes)
    assert annule.est_erreur and "cancelled" in annule.texte


def test_suivi_cote_client_tache_en_erreur(client):
    with importer_client(client):
        from pharos_client import taches
        from pharos_client.transport import Session

        with Session(jouet(decider_reference, echouer=True)) as s:
            r = taches.appeler_ou_suivre(s, "recalculer_plan_quai", {"date": "2026-10-08"}, afficher=lambda l: None)
    assert r.est_erreur and "météo indisponible" in r.texte


async def test_profils_du_client_de_test_et_clients_du_lab11(capsys):
    from outils import lab11

    with servir(jouet(decider_reference).http_app(path="/mcp", json_response=True)) as url:
        await lab11.clients(f"{url}/mcp", "jeton-exploitation", False, {"date": "2026-10-08"})
        tache = capsys.readouterr().out
        await lab11.clients(f"{url}/mcp", "jeton-exploitation", True, {"date": "2026-10-08"})
        refus = capsys.readouterr().out
        await lab11.clients(f"{url}/mcp", "jeton-exploitation", False, {"date": "2026-10-08", "quai": 3})
        direct = capsys.readouterr().out
    assert "déclare : Tasks : oui" in tache and "Tâche créée" in tache and "3 escales sur 4" in tache
    assert "completed" in tache and '"escales":4' in tache.replace(" ", "")
    assert "Tasks : non (aucune extension)" in refus and "ERREUR MÉTIER" in refus and "Plan B" in refus
    assert "Réponse directe" in direct


async def test_profils_elicitation():
    recus = []
    mcp = FastMCP("mrtr")

    @mcp.tool
    async def publier(ctx: Context) -> dict:
        if ctx.input_responses:
            recus.append(ctx.input_responses["ok"].action)
            return {"reponse": ctx.input_responses["ok"].content}
        return mcp_types.InputRequiredResult(input_requests={"ok": mcp_types.ElicitRequest(
            params=mcp_types.ElicitRequestFormParams(message="Publier ?", requested_schema={
                "type": "object", "properties": {"confirmer": {"type": "boolean", "default": False}}}))})

    with servir(mcp.http_app(path="/mcp", json_response=True)) as url:
        async with ClientTest(f"{url}/mcp", profil="defaut") as c:
            defaut = await c.appeler("publier")
        async with ClientTest(f"{url}/mcp", profil="complet") as c:
            refuse = await c.appeler("publier")
            brut = await c.appeler_brut("publier")
        async with ClientTest(f"{url}/mcp", profil="sans_elicitation") as c:
            sans = await c.appeler_brut("publier")
    assert defaut.structured_content == {"reponse": {"confirmer": False}}
    assert isinstance(brut, mcp_types.InputRequiredResult) and isinstance(sans, mcp_types.InputRequiredResult)
    assert recus == ["accept", "decline"] and refuse.structured_content == {"reponse": None}
    with pytest.raises(ValueError, match="profil inconnu"):
        ClientTest("http://x/mcp", profil="magique")


def test_clients_du_lab11_disent_quoi_lancer_si_le_serveur_ne_repond_pas(capsys):
    from outils import lab11

    assert lab11.main(["clients", "--url", "http://127.0.0.1:1/mcp"]) == 1
    sortie = capsys.readouterr().out
    assert "ne répond pas" in sortie and "make lab11-scaffold" in sortie


def test_depart_et_cibles_du_lab11():
    assert (labs.DEPARTS[11], labs.SORTIES[11]) == ("is2-fin", "is3-fin")
    assert labs.DEMARRAGE[11] == ["lab8-base", "lab10-mocks", "lab10-up"] and labs.PORTS_PRETS[11] == [8103]
    cibles = set(re.findall(r"^([a-z0-9-]+):", Path("mk/lab11.mk").read_text(encoding="utf-8"), re.MULTILINE))
    assert {"lab11-scaffold", "lab11-clients", "lab11-verifier"} <= cibles
    assert "PHAROS_VITESSE" in Path("compose/lab10.yaml").read_text(encoding="utf-8")
    texte = Path("gabarits/lab11/serveurs/pharos_ops/taches.py").read_text(encoding="utf-8")
    assert "async" not in re.findall(r"def decider\(([^)]*)\)", texte)[0]         # aucun paramètre async imposé
