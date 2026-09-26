"""pharos-data v0 (LAB 8) — squelette. À compléter : le pool (étape 1), la requête (étape 1), le schéma en
ressource (étape 2), le plafond (étape 4).

Déjà branché : l'adresse de la base, le journal serveur (logs/pharos-data.jsonl), la connexion empruntée
sous le rôle de l'exploitation, le lancement HTTP (make lab8-up → http://localhost:8102/mcp).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

import asyncpg  # noqa: F401  (étape 1 : asyncpg.create_pool)
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from pharos import base, journal

# Le pool porte le nom « pharos-data » : c'est à ce nom que le vérificateur reconnaît ses connexions.
PARAMETRES_POOL = {"dsn": base.dsn("pharos_app"), "min_size": 1, "max_size": 5,
                   "server_settings": {"application_name": "pharos-data"}}
PLAFOND = 200
etat: dict = {}          # etat["pool"] : le pool, créé au démarrage du processus


@asynccontextmanager
async def cycle_de_vie(serveur):
    # Étape 1 — créer le pool ICI, une seule fois, au démarrage du processus :
    #     etat["pool"] = await asyncpg.create_pool(**PARAMETRES_POOL)
    # puis le fermer à l'arrêt, après le yield.
    yield {}


@asynccontextmanager
async def emprunter():
    """Une connexion du pool, dans une transaction, sous le rôle de l'exploitation.

    pharos_app n'a aucun droit propre (NOINHERIT) : sans SET LOCAL ROLE, toute lecture est refusée."""
    pool = etat.get("pool")
    if pool is None:
        raise ToolError("Base indisponible : le pool n'est pas créé (LAB 8, étape 1).")
    async with pool.acquire() as connexion, connexion.transaction():
        await connexion.execute("SET LOCAL ROLE pharos_exploitation")
        yield connexion


mcp = FastMCP("pharos-data", lifespan=cycle_de_vie, middleware=[journal.Journal("pharos-data")])


@mcp.tool(name="requete_mouvements",
          description="Mouvements de conteneurs du port sur une période. Dates en heure de Paris "
                      "(Europe/Paris), date_fin incluse. Filtres facultatifs : quai, type de conteneur, sens. "
                      "Rend la requête exécutée et ses paramètres.")
async def requete_mouvements(date_debut: date, date_fin: date, quai: int | None = None,
                             type_conteneur: str | None = None, sens: str | None = None) -> dict:
    # Étape 1 — le SQL est écrit par vous ; le modèle ne fournit que les paramètres.
    # Étape 4 — compter d'abord (COUNT séparé), refuser au-delà de PLAFOND, puis seulement rapatrier.
    raise NotImplementedError("requete_mouvements : à écrire (LAB 8, étape 1).")


# Étape 2 — le schéma en ressource, pharos://schema/… (bloc 13.3) : unités, fuseau horaire, relations
# utiles ; esc_hdr_legacy n'y apparaît pas, et le dictionnaire dit qu'il n'existe pas d'autre source.


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp", json_response=True, show_banner=False,
            middleware=journal.http("pharos-data"))
