"""Outils du LAB 9 : les identités de salle (make lab9-identites) et les trois contournements (make lab9-contourner).

python -m outils.lab9 identites
python -m outils.lab9 contourner N [--jeton jeton-rance]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import asyncpg

from outils.client_test import ClientTest
from pharos import autorisation, base

URL = "http://observateur:8102/mcp"
CONTOURNEMENTS = {
    1: ["WITH x AS (DELETE FROM mouvements RETURNING *) SELECT count(*) FROM x"],
    2: ["SELECT e.escale_id, t.montant FROM escales e JOIN tarifs t ON t.navire_id = e.navire_id"],
    3: ["SELECT e.tarif_negocie FROM escales e", "SELECT e.armateur FROM escales e",
        "SELECT x.mouvement_id FROM esc_hdr_legacy x"],
}


async def _navires() -> dict[str, list[str]]:
    connexion = await asyncpg.connect(base.dsn("pharos_app"))
    try:
        async with connexion.transaction():
            await connexion.execute("SET LOCAL ROLE pharos_exploitation")
            lignes = await connexion.fetch("SELECT agent_id, nom FROM navires ORDER BY navire_id")
    finally:
        await connexion.close()
    navires: dict[str, list[str]] = {}
    for l in lignes:
        navires.setdefault(l["agent_id"], []).append(l["nom"])
    return navires


def identites() -> int:
    try:
        navires = asyncio.run(_navires())
    except (OSError, asyncpg.PostgresError) as exc:
        print(f"Base injoignable ({exc.__class__.__name__}) : lancer « make lab8-base ».")
        return 1
    print("Trois identités de salle (jetons fixes, pas des secrets : le mécanisme réel est au module SG2).\n")
    for jeton, i in autorisation.JETONS.items():
        perimetre = "toutes les escales" if i.agent_id is None else \
            f"les escales de ses {len(navires.get(i.agent_id, []))} navires : {', '.join(navires.get(i.agent_id, []))}"
        print(f"  {jeton:<20} {i.nom} ({i.profil}) — voit {perimetre}")
    print("\nChoisir l'identité du client : PHAROS_JETON=jeton-rance make lab8-question Q=…")
    print("Appeler un outil sous une identité : make appeler URL=http://observateur:8102/mcp OUTIL=… PHAROS_JETON=…")
    return 0


async def _contourner(n: int, jeton: str, url: str) -> int:
    async with ClientTest(url, jeton=jeton) as c:
        for sql in CONTOURNEMENTS[n]:
            r = await c.appeler("requete_sql", {"sql": sql})
            texte = "\n".join(getattr(b, "text", "") or "" for b in r.content) or json.dumps(r.structured_content)
            print(f"SQL : {sql}\n→ {'REFUS' if r.is_error else 'PASSÉ'} : {texte}\n")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m outils.lab9")
    sous = p.add_subparsers(dest="commande", required=True)
    sous.add_parser("identites")
    c = sous.add_parser("contourner")
    c.add_argument("n", type=int, choices=sorted(CONTOURNEMENTS))
    c.add_argument("--jeton", default=os.environ.get("PHAROS_JETON") or "jeton-rance")
    c.add_argument("--url", default=URL)
    a = p.parse_args(argv)
    if a.commande == "identites":
        return identites()
    return asyncio.run(_contourner(a.n, a.jeton, a.url))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
