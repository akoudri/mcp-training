"""Faits de fastmcp 4.0.10 sur lesquels reposent les LAB 11 à 13 (spec §11 du sous-projet 3, critère §17.3 ; MCP
Apps : décision 5 de la spec du sous-projet 4).

Si une mise à jour de fastmcp en change un, ce test le dit avant les binômes. Aucun modèle, aucun Docker.
"""

import asyncio
import json
import subprocess
import sys
import textwrap
from datetime import timedelta

import mcp_types
import pytest
from fastmcp import Client, Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from fastmcp.utilities.tasks import TASKS_EXTENSION_ID, TaskConfig
from fastmcp_tasks import TasksExtension, ToolTask
from fastmcp_tasks.client_models import ClientCreateTaskResult
from fastmcp_tasks.creation import create_task
from mcp.server.request_state import RequestStateSecurity
from mcp.shared.exceptions import MCPError

from outils.servir import servir
from tests.aides import RACINE_KIT

CLE = "cle-de-test-pharos-au-moins-32-octets-0001"
TERMINAUX = ("completed", "failed", "cancelled")


class ClientNu(Client):
    """Un client qui ne déclare aucune extension interne (ni Tasks, ni MCP Apps)."""

    _auto_internal_extensions = False


def serveur_taches(vus: dict) -> FastMCP:
    class Decidee(TasksExtension):
        async def intercept_tool_call(self, params, context, call_next):
            vus["declare"] = context.client_extension_settings(TASKS_EXTENSION_ID) is not None
            if (params.arguments or {}).get("quai") is not None:
                return await call_next()
            if not vus["declare"]:
                raise ToolError("plan B : quai par quai")
            return await create_task(await context.fastmcp.get_tool(params.name), params.arguments, context)

    mcp = FastMCP("faits", mask_error_details=True)
    mcp.add_extension(Decidee())

    @mcp.tool(task=TaskConfig(mode="optional", poll_interval=timedelta(seconds=0.1)))
    async def recalculer(date: str, ctx: Context, quai: int | None = None, echouer: bool = False) -> dict:
        total = 1 if quai else 5
        try:
            for i in range(1, total + 1):
                await asyncio.sleep(0.15)
                if echouer and i == 3:
                    raise RuntimeError("secret-dans-l-exception")
                await ctx.report_progress(i, total, f"{i} escales sur {total}")
        except asyncio.CancelledError:
            vus["annule"] = True
            raise
        return {"escales": total}

    return mcp


async def _soumettre(client, arguments):
    return await client.session.call_tool(name="recalculer", arguments=arguments, allow_claimed=True)


async def _suivre(client, brut):
    tache, messages = ToolTask(client, "recalculer", brut, raise_on_error=False), []
    while True:
        etat = await tache.status()
        if etat.status_message and etat.status_message not in messages:
            messages.append(etat.status_message)
        if etat.status in TERMINAUX:
            return etat, messages, await tache.result()
        await asyncio.sleep(0.05)


async def test_tasks_decision_par_les_arguments_et_progression():
    vus = {}
    async with Client(serveur_taches(vus)) as c:
        direct = await _soumettre(c, {"date": "2026-10-08", "quai": 3})
        assert not isinstance(direct, ClientCreateTaskResult) and direct.structured_content == {"escales": 1}
        brut = await _soumettre(c, {"date": "2026-10-08"})
        assert isinstance(brut, ClientCreateTaskResult) and brut.poll_interval_ms == 100 and vus["declare"]
        etat, messages, resultat = await _suivre(c, brut)
    assert etat.status == "completed" and resultat.structured_content == {"escales": 5}
    assert messages[0] == "1 escales sur 5" and len(messages) >= 3


async def test_call_tool_ordinaire_attend_seul_la_fin_de_la_tache():
    """Le piège du LAB 11 : un appel ordinaire est suivi en silence jusqu'au bout (aucune progression visible)."""
    async with Client(serveur_taches({})) as c:
        r = await c.call_tool("recalculer", {"date": "2026-10-08"})
    assert r.structured_content == {"escales": 5}


async def test_une_exception_termine_la_tache_en_erreur_masquee_et_non_en_failed():
    async with Client(serveur_taches({})) as c:
        etat, _, resultat = await _suivre(c, await _soumettre(c, {"date": "2026-10-08", "echouer": True}))
    assert etat.status == "completed" and resultat.is_error
    assert "secret-dans-l-exception" not in resultat.content[0].text        # mask_error_details respecté


async def test_annulation():
    vus = {}
    async with Client(serveur_taches(vus)) as c:
        tache = ToolTask(c, "recalculer", await _soumettre(c, {"date": "2026-10-08"}), raise_on_error=False)
        await asyncio.sleep(0.3)
        await tache.cancel()
        etat = await tache.wait(timeout=5)
        resultat = await tache.result()
        for _ in range(100):                          # le statut peut précéder la fin de l'outil annulé
            if vus.get("annule"):
                break
            await asyncio.sleep(0.02)
    assert etat.status == "cancelled" and vus.get("annule") and resultat.is_error


async def test_client_sans_extension_et_plan_b():
    vus = {}
    async with ClientNu(serveur_taches(vus)) as c:
        r = await c.call_tool("recalculer", {"date": "2026-10-08"}, raise_on_error=False)
        direct = await c.call_tool("recalculer", {"date": "2026-10-08", "quai": 3})
    assert r.is_error and "plan B" in r.content[0].text and vus["declare"] is False
    assert direct.structured_content == {"escales": 1}


def test_un_client_ne_declare_tasks_que_si_fastmcp_tasks_est_importe():
    vus = {}
    script = textwrap.dedent("""
        import asyncio, sys
        from fastmcp import Client
        if sys.argv[2] == "importer":
            import fastmcp_tasks  # noqa: F401
        async def main():
            async with Client(sys.argv[1]) as c:
                await c.call_tool("recalculer", {"date": "2026-10-08"}, raise_on_error=False)
        asyncio.run(main())
    """)
    with servir(serveur_taches(vus).http_app(path="/mcp", json_response=True)) as url:
        for mode, attendu in (("sans", False), ("importer", True)):
            subprocess.run([sys.executable, "-c", script, f"{url}/mcp", mode], check=True, cwd=RACINE_KIT,
                           capture_output=True, timeout=60)
            assert vus["declare"] is attendu, mode


class Espion(Middleware):
    def __init__(self):
        self.outils, self.refus = [], []

    async def on_call_tool(self, context, call_next):
        self.outils.append(context.message.name)
        return await call_next(context)

    async def on_message(self, context, call_next):
        try:
            return await call_next(context)
        except MCPError as exc:
            self.refus.append((context.method, str(exc)))
            raise


def serveur_mrtr(publiees: list, espion: Espion, cle: str | None = CLE) -> FastMCP:
    securite = RequestStateSecurity(keys=[cle], audience="pharos-ops") if cle else None
    mcp = FastMCP("pharos-ops", middleware=[espion], request_state_security=securite)

    @mcp.tool
    async def publier(escale_id: str, ctx: Context) -> dict:
        if ctx.input_responses:
            publiees.append((escale_id, json.loads(ctx.request_state)))
            return {"publiee": True}
        return mcp_types.InputRequiredResult(
            input_requests={"ok": mcp_types.ElicitRequest(params=mcp_types.ElicitRequestFormParams(
                message=f"Publier {escale_id} ?", requested_schema={
                    "type": "object", "properties": {"confirmer": {"type": "boolean", "default": False}}}))},
            request_state=json.dumps({"escale_id": escale_id}))

    return mcp


OUI = {"ok": mcp_types.ElicitResult(action="accept", content={"confirmer": True})}


async def _rejouer(client, escale_id, etat):
    return await client.session.call_tool(name="publier", arguments={"escale_id": escale_id}, input_responses=OUI,
                                          request_state=etat, allow_input_required=True)


async def test_requeststate_scelle_partage_entre_instances_et_refus_proteges():
    publiees, espion_a, espion_b = [], Espion(), Espion()
    a, b = serveur_mrtr(publiees, espion_a), serveur_mrtr(publiees, espion_b)
    autre = serveur_mrtr(publiees, Espion(), cle=None)                          # clé éphémère de processus
    async with Client(a) as ca, Client(b) as cb, Client(autre) as cx:
        demande = await ca.session.call_tool(name="publier", arguments={"escale_id": "ESC-2026-0412"},
                                             allow_input_required=True)
        assert isinstance(demande, mcp_types.InputRequiredResult) and publiees == []
        etat = demande.request_state
        assert "ESC-2026-0412" not in etat                                    # scellé : illisible en clair
        assert (await _rejouer(cb, "ESC-2026-0412", etat)).structured_content == {"publiee": True}
        milieu = len(etat) // 2
        altere = etat[:milieu] + ("A" if etat[milieu] != "A" else "B") + etat[milieu + 1:]
        for client, escale_id, jeton in ((ca, "ESC-2026-0412", altere), (ca, "ESC-2026-0405", etat),
                                         (cx, "ESC-2026-0412", etat)):
            with pytest.raises(MCPError, match="Invalid or expired requestState"):
                await _rejouer(client, escale_id, jeton)
        await _rejouer(ca, "ESC-2026-0412", etat)                             # rejeu du rejeu : publie encore
    assert publiees == [("ESC-2026-0412", {"escale_id": "ESC-2026-0412"})] * 2
    assert ("tools/call", "Invalid or expired requestState") in espion_a.refus
    assert espion_a.outils.count("publier") == 2                             # les refus n'atteignent pas on_call_tool


def test_cle_de_requeststate_trop_courte():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        RequestStateSecurity(keys=["pharos-salle-2026"])


async def test_capacites_du_client_et_pilotage_automatique_de_l_elicitation():
    capacites = []
    mcp = FastMCP("caps")

    @mcp.tool
    async def voir(ctx: Context) -> dict:
        meta = ctx.request_context.meta
        brut = meta.model_dump(by_alias=True) if hasattr(meta, "model_dump") else dict(meta or {})
        capacites.append("elicitation" in (brut.get("io.modelcontextprotocol/clientCapabilities") or {}))
        if ctx.input_responses:
            return {"reponse": ctx.input_responses["q"].content}
        return mcp_types.InputRequiredResult(input_requests={"q": mcp_types.ElicitRequest(
            params=mcp_types.ElicitRequestFormParams(message="?", requested_schema={
                "type": "object", "properties": {"x": {"type": "boolean"}}}))})

    async def repondre(message, response_type, params, context):
        return {"x": True}

    async with Client(mcp, elicitation_handler=repondre) as c:
        r = await c.call_tool("voir", {})
    async with Client(mcp) as c:
        brut = await c.session.call_tool(name="voir", arguments={}, allow_input_required=True)
    assert r.structured_content == {"reponse": {"x": True}}                   # le client a répondu seul
    assert capacites == [True, True, False] and isinstance(brut, mcp_types.InputRequiredResult)


def serveur_vue(vus: list) -> FastMCP:
    """Un outil qui porte une vue MCP App (LAB 13) : ressource ui:// déclarée à l'avance, et le résultat reste un dict."""
    from fastmcp.apps import UI_EXTENSION_ID, AppConfig

    mcp = FastMCP("vue")

    @mcp.resource("ui://pharos-ops/plan-quai", name="plan-quai")
    def vue() -> str:
        return "<!doctype html><title>plan</title>"

    @mcp.tool(app=AppConfig(resource_uri="ui://pharos-ops/plan-quai"))
    def plan(ctx: Context) -> dict:
        vus.append(ctx.client_supports_extension(UI_EXTENSION_ID))
        return {"date": "2026-10-08", "placements": [{"escale_id": "ESC-2026-0412", "statut": "a_decaler"}]}

    return mcp


async def test_mcp_apps_la_vue_se_declare_et_le_texte_reste_le_meme():
    """LAB 13, étape 4 : fastmcp.apps est dans le paquet de base (aucune dépendance de plus) ; la vue se déclare par
    une ressource ui:// (type text/html;profile=mcp-app, posé seul) et app=AppConfig(resource_uri=…) sur l'outil
    (_meta.ui.resourceUri de tools/list). Rien n'est filtré selon le client : avec ou sans l'extension déclarée,
    le résultat est le même — texte ET structuredContent ; c'est l'hôte qui choisit d'afficher la vue."""
    from fastmcp.apps import UI_EXTENSION_ID, UI_MIME_TYPE
    from mcp.client.extension import ClientExtension

    class ExtensionUI(ClientExtension):
        identifier = UI_EXTENSION_ID

    assert (UI_EXTENSION_ID, UI_MIME_TYPE) == ("io.modelcontextprotocol/ui", "text/html;profile=mcp-app")
    vus: list = []
    mcp = serveur_vue(vus)
    resultats = []
    for client in (ClientNu(mcp), Client(mcp, extensions=[ExtensionUI()])):
        async with client:
            outil = (await client.list_tools())[0]
            ressource = (await client.list_resources())[0]
            r = await client.call_tool("plan", {})
        assert outil.meta["ui"]["resourceUri"] == "ui://pharos-ops/plan-quai"
        assert str(ressource.uri) == "ui://pharos-ops/plan-quai" and ressource.mime_type == UI_MIME_TYPE
        resultats.append(("\n".join(b.text for b in r.content), r.structured_content))
    assert resultats[0] == resultats[1] and "ESC-2026-0412" in resultats[0][0]
    assert vus == [False, True]          # le serveur PEUT savoir si le client déclare l'extension
