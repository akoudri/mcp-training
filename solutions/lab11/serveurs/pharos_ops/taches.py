"""Tâche ou réponse directe : la décision du serveur (LAB 11) — solution de référence de decider.

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
        # planification.recalculer(date, [quai] ou None, rappel_progression) ; la progression :
        #     await ctx.report_progress(traitees, total, "N escales sur M")   → statusMessage de tasks/get
        ...

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


PLAN_B = ("Recalcul de la journée entière impossible avec ce client : il dure deux minutes environ et exige un "
          "client qui suit les tâches (extension Tasks), que celui-ci ne déclare pas. Possible : recalculer quai par "
          "quai (quai=1 à 7), quelques secondes chacun, puis assembler les résultats.")


def decider(nom: str, arguments: dict, client_declare: bool) -> str:
    """Un quai seul : quelques secondes, réponse directe. La journée : une tâche, si le client sait la suivre ;
    sinon un refus explicite, qui propose le calcul quai par quai (le plan B)."""
    if arguments.get("quai") is not None:
        return DIRECT
    if client_declare:
        return TACHE
    raise ToolError(PLAN_B)


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
        raise ValueError(f"decider doit rendre {DIRECT!r} ou {TACHE!r} (ou lever ToolError), pas {decision!r}.")
