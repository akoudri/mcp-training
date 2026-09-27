"""Tâche ou réponse directe : la décision du serveur (LAB 11). L'extension est fournie ; decider est à écrire.

Brancher dans serveurs/pharos_ops/serveur.py (étapes 1 et 2) :

    from datetime import date, timedelta
    from fastmcp import Context
    from fastmcp.utilities.tasks import TaskConfig
    from pharos_ops import planification                       # le moteur fourni
    from serveurs.pharos_ops.taches import ExtensionRecalcul

    mcp.add_extension(ExtensionRecalcul())

    @mcp.tool(name="recalculer_plan_quai", description="…",
              task=TaskConfig(mode="optional", poll_interval=timedelta(seconds=…)))   # l'intervalle suggéré
    async def recalculer_plan_quai(date: date, ctx: Context, quai: int | None = None) -> dict:
        # plan = await planification.recalculer(date, [quai] ou None, rappel_progression) ; la progression :
        #     await ctx.report_progress(traitees, total, "N escales sur M")   → statusMessage de tasks/get
        # return plan.en_dict()                     recalculer est une coroutine : sans await, rien n'est calculé

Le mode « optional » autorise la tâche sans l'imposer ; par défaut, fastmcp ne regarde jamais les arguments.
ExtensionRecalcul intercepte chaque appel de recalculer_plan_quai et demande à decider ce qu'il faut faire.
"""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from fastmcp.utilities.tasks import TASKS_EXTENSION_ID
from fastmcp_tasks import TasksExtension
from fastmcp_tasks.creation import create_task

OUTIL = "recalculer_plan_quai"
DIRECT, TACHE = "direct", "tache"


def decider(nom: str, arguments: dict, client_declare: bool) -> str:
    """Rend DIRECT (réponse immédiate) ou TACHE (réponse en tâche), d'après les arguments de l'appel et ce que
    le client déclare (client_declare : il a déclaré l'extension Tasks dans ses capacités, portées par _meta).

    Quand ni l'un ni l'autre n'est possible, lever fastmcp.exceptions.ToolError avec un refus explicite, qui dit
    ce qui n'est pas possible et ce qui l'est (étape 3, le plan B).

    À écrire : étape 1 (quai=3 → direct ; la journée → tâche), étape 3 (client sans l'extension)."""
    raise NotImplementedError("decider : à écrire (LAB 11, étapes 1 et 3).")


class ExtensionRecalcul(TasksExtension):
    """L'extension Tasks de fastmcp, dont la décision est confiée à decider pour recalculer_plan_quai."""

    async def intercept_tool_call(self, params, context, call_next):
        if params.name != OUTIL:
            return await super().intercept_tool_call(params, context, call_next)
        declare = context.client_extension_settings(TASKS_EXTENSION_ID) is not None
        try:
            decision = decider(params.name, dict(params.arguments or {}), declare)
        except NotImplementedError as exc:            # le gabarit : dire au client ce qui manque, pas « erreur interne »
            raise ToolError(str(exc)) from None
        if decision == DIRECT:
            return await call_next()
        if decision == TACHE:
            outil = await context.fastmcp.get_tool(params.name)
            return await create_task(outil, params.arguments, context)
        raise ToolError(f"decider doit rendre {DIRECT!r} ou {TACHE!r} (ou lever ToolError), pas {decision!r}.")
