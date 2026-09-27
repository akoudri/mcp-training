"""Outils du LAB 11 : les deux clients de test, avec et sans l'extension Tasks (make lab11-clients).

python -m outils.lab11 clients [--sans-tasks] [--quai N] [--date AAAA-MM-JJ]

Chaque client affiche ce qu'il déclare, puis ce que le serveur rend, brut : une réponse directe, un refus, ou
une tâche — suivie alors jusqu'au bout, chaque statut nouveau affiché avec l'instant où il a été vu.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

from fastmcp_tasks import ToolTask
from fastmcp_tasks.client_models import ClientCreateTaskResult

from outils.client_test import ClientTest, ServeurInjoignable

URL = "http://observateur:8103/mcp"
OUTIL = "recalculer_plan_quai"
TERMINAUX = ("completed", "failed", "cancelled")


def _texte(resultat) -> str:
    texte = "\n".join(getattr(b, "text", "") or "" for b in resultat.content)
    if not texte and getattr(resultat, "structured_content", None) is not None:
        texte = json.dumps(resultat.structured_content, ensure_ascii=False)
    return texte if len(texte) <= 1500 else texte[:1500] + f"… [{len(texte)} caractères]"


async def clients(url: str, jeton: str, sans_tasks: bool, arguments: dict) -> int:
    profil = "sans_tasks" if sans_tasks else "complet"
    async with ClientTest(url, jeton=jeton, profil=profil, nom=f"pharos-lab11-{profil}") as c:
        await c.joindre("« make lab11-scaffold » (pharos-ops, 8103)")
        print(f"Client « {profil} » — déclare : {c.declare()}")
        print(f"Appel : {OUTIL}({', '.join(f'{k}={v}' for k, v in arguments.items())})\n")
        debut = time.monotonic()
        brut = await c.appeler_brut(OUTIL, arguments)
        if not isinstance(brut, ClientCreateTaskResult):
            print(f"Réponse directe, en {time.monotonic() - debut:.1f} s"
                  + (" — ERREUR MÉTIER (isError) :" if brut.is_error else " :"))
            print(_texte(brut))
            return 0
        print(f"Tâche créée en {time.monotonic() - debut:.2f} s : {brut.task_id} "
              f"(statut {brut.status}, intervalle suggéré {brut.poll_interval_ms} ms)")
        tache, dernier = ToolTask(c._client, OUTIL, brut, raise_on_error=False), None
        while True:
            etat = await tache.status()
            vu = (etat.status, etat.status_message)
            if vu != dernier:
                print(f"  {time.monotonic() - debut:6.1f} s  {etat.status:<15} {etat.status_message or ''}")
                dernier = vu
            if etat.status in TERMINAUX:
                break
            await asyncio.sleep(max((etat.poll_interval_ms or 1000) / 1000, 0.2))
        resultat = await tache.result()
        print(f"\nRésultat{' — ERREUR (isError)' if resultat.is_error else ''} :\n{_texte(resultat)}")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m outils.lab11")
    sous = p.add_subparsers(dest="commande", required=True)
    c = sous.add_parser("clients")
    c.add_argument("--sans-tasks", action="store_true")
    c.add_argument("--quai", type=int)
    c.add_argument("--date", default="2026-10-08")
    c.add_argument("--url", default=URL)
    c.add_argument("--jeton", default=os.environ.get("PHAROS_JETON") or "jeton-exploitation")
    a = p.parse_args(argv)
    arguments = {"date": a.date, **({"quai": a.quai} if a.quai is not None else {})}
    try:
        return asyncio.run(clients(a.url, a.jeton, a.sans_tasks, arguments))
    except ServeurInjoignable as exc:
        print(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
