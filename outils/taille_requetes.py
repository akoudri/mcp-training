"""make lab2-taille-requetes — ce que pèsent les requêtes avant et après la migration (extension B du LAB 2).

La taille d'une requête ne dépend que du client : on la mesure contre un serveur de référence en
mémoire, qui parle les deux révisions et expose les trois outils de pharos-legacy. Dix tours =
dix appels à etat_escale, poignée de main comprise pour 2025-11-25.
"""

from __future__ import annotations

import asyncio
import sys

from fastmcp import FastMCP

from outils.client_test import ClientTest, Echange
from outils.servir import servir

TOURS = 10


def serveur_de_reference() -> FastMCP:
    mcp = FastMCP("pharos-legacy")

    @mcp.tool
    def etat_escale(escale_id: str) -> dict:
        """État d'une escale : quai, créneau, tirant d'eau, statut."""
        return {"escale_id": escale_id, "quai": 3, "statut": "prévue"}

    @mcp.tool
    def lister_mouvements(escale_id: str) -> dict:
        """Première page (20 au plus) des mouvements de conteneurs d'une escale."""
        return {"escale_id": escale_id, "page": 1, "mouvements": []}

    @mcp.tool
    def page_suivante() -> dict:
        """Page suivante des mouvements."""
        return {"page": 2, "mouvements": []}

    return mcp


def octets_envoyes(e: Echange) -> int:
    """Ligne de requête, en-têtes et corps, tels qu'envoyés sur le fil."""
    ligne = len(f"{e.methode_http} /mcp HTTP/1.1\r\n")
    entetes = sum(len(k) + len(v) + 4 for k, v in e.entetes_requete.items())
    return ligne + entetes + 2 + len(e.corps_requete.encode("utf-8"))


async def mesurer(url: str, revision: str, tours: int = TOURS) -> dict:
    async with ClientTest(url, revision) as c:
        catalogue = await c.outils()
        for _ in range(tours):
            await c.appeler("etat_escale", {"escale_id": "ESC-2026-0412"})
    poignee = [e for e in c.echanges if e.methode_mcp in ("initialize", "notifications/initialized")
               or (e.methode_http == "GET")]
    appels = [e for e in c.echanges if e.methode_mcp == "tools/call"]
    liste = next(e for e in c.echanges if e.methode_mcp == "tools/list")
    return {"revision": revision, "outils": len(catalogue),
            "poignee": sum(map(octets_envoyes, poignee)), "requetes_poignee": len(poignee),
            "par_appel": sum(map(octets_envoyes, appels)) // len(appels),
            "total": sum(map(octets_envoyes, poignee + appels)),
            "reponse_liste": len(liste.corps_reponse.encode("utf-8"))}


def tableau(avant: dict, apres: dict) -> str:
    lignes = [f"Taille des requêtes sur {TOURS} tours (octets envoyés : ligne, en-têtes, corps)", "",
              f"| | {avant['revision']} | {apres['revision']} |", "|---|---:|---:|",
              f"| Poignée de main | {avant['poignee']} ({avant['requetes_poignee']} requêtes) | "
              f"{apres['poignee']} ({apres['requetes_poignee']} requête) |",
              f"| Un appel tools/call | {avant['par_appel']} | {apres['par_appel']} |",
              f"| {TOURS} tours, poignée comprise | {avant['total']} | {apres['total']} |", "",
              f"Chaque appel 2026-07-28 porte {apres['par_appel'] - avant['par_appel']:+d} octets : la révision, "
              "le client et ses capacités voyagent dans chaque requête.",
              f"Réponse tools/list : {apres['reponse_liste']} octets. Un client qui relit le catalogue à chaque "
              f"tour en recevrait {TOURS * apres['reponse_liste']} ; mis en cache (ttlMs, bloc 4.4), "
              f"{apres['reponse_liste']} — soit {(TOURS - 1) * apres['reponse_liste']} octets économisés."]
    return "\n".join(lignes)


async def _principal() -> int:
    with servir(serveur_de_reference().http_app(path="/mcp", json_response=True)) as base:
        avant = await mesurer(f"{base}/mcp", "2025-11-25")
        apres = await mesurer(f"{base}/mcp", "2026-07-28")
    print(tableau(avant, apres))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_principal()))
