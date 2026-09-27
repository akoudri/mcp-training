"""pharos-data v0 (LAB 8) — solution de référence : pool au démarrage, requête paramétrée, schéma en
ressource, plafond compté avant rapatriement, requête exécutée rendue avec le résultat.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta

import asyncpg
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from pharos import base, journal

PARAMETRES_POOL = {"dsn": base.dsn("pharos_app"), "min_size": 1, "max_size": 5,
                   "server_settings": {"application_name": "pharos-data"}}
PLAFOND = 200
TYPES = ("20", "40", "refrigere")
SENS = ("embarquement", "debarquement")
etat: dict = {}

SCHEMA = """# Base d'exploitation du port PHAROS — dictionnaire

Toutes les dates et heures (escales.debut, escales.fin, mouvements.horodatage) sont en heure de Paris
(fuseau Europe/Paris). Longueurs et tirants d'eau en mètres (m).

Il n'existe **aucune autre source** de mouvements de conteneurs que la table `mouvements`.

## escales — une escale d'un navire à un quai
| Colonne | Sens |
|---|---|
| escale_id | identifiant, format ESC-AAAA-NNNN |
| navire_id | navire (→ navires.navire_id) |
| quai | numéro de quai, 1 à 7 (→ quais.quai) |
| debut, fin | arrivée et départ, heure de Paris |
| statut | prevue, accostee, terminee, annulee |
| tirant_eau_m | tirant d'eau du navire pour cette escale, en mètres |

## mouvements — un conteneur embarqué ou débarqué pendant une escale
| Colonne | Sens |
|---|---|
| mouvement_id | identifiant |
| escale_id | escale (→ escales.escale_id) ; le quai d'un mouvement est celui de son escale |
| conteneur_id | numéro du conteneur |
| sens | valeurs possibles, sans accent : `embarquement`, `debarquement` |
| horodatage | heure du mouvement, heure de Paris |
| type_conteneur | valeurs possibles, sans accent : `20`, `40`, `refrigere` (conteneur frigorifique, « reefer ») |

## navires, quais
| Colonne | Sens |
|---|---|
| navires.navire_id, nom, imo, pavillon | identité du navire |
| navires.longueur_m, tirant_eau_max_m | en mètres |
| quais.quai, longueur_m, tirant_eau_max_m | en mètres |

Relations utiles : mouvements → escales (escale_id) → navires (navire_id) ; escales → quais (quai).
"""


@asynccontextmanager
async def cycle_de_vie(serveur):
    etat["pool"] = await asyncpg.create_pool(**PARAMETRES_POOL)
    try:
        yield {}
    finally:
        await etat.pop("pool").close()


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


mcp = FastMCP("pharos-data", lifespan=cycle_de_vie, mask_error_details=True,
              middleware=[journal.Journal("pharos-data")])


@mcp.resource("pharos://schema/mouvements", name="schema-mouvements", mime_type="text/markdown",
              description="Dictionnaire des tables escales, mouvements, navires et quais : unités, fuseau, valeurs.")
def schema() -> str:
    return SCHEMA


def _filtres(date_debut: date, date_fin: date, quai, type_conteneur, sens) -> tuple[str, list]:
    if date_fin < date_debut:
        raise ToolError(f"Période vide : date_fin ({date_fin}) précède date_debut ({date_debut}).")
    if type_conteneur is not None and type_conteneur not in TYPES:
        raise ToolError(f"type_conteneur inconnu : « {type_conteneur} ». Valeurs possibles : {', '.join(TYPES)}.")
    if sens is not None and sens not in SENS:
        raise ToolError(f"sens inconnu : « {sens} ». Valeurs possibles : {', '.join(SENS)}.")
    # Bornes en heure de Paris ; date_fin incluse, donc borne haute exclue au lendemain.
    clauses = ["m.horodatage >= ($1::date::timestamp AT TIME ZONE 'Europe/Paris')",
               "m.horodatage < ($2::date::timestamp AT TIME ZONE 'Europe/Paris')"]
    parametres: list = [date_debut, date_fin + timedelta(days=1)]
    for colonne, valeur in (("e.quai", quai), ("m.type_conteneur", type_conteneur), ("m.sens", sens)):
        if valeur is not None:
            parametres.append(valeur)
            clauses.append(f"{colonne} = ${len(parametres)}")
    return " AND ".join(clauses), parametres


@mcp.tool(name="requete_mouvements",
          description="Mouvements de conteneurs du port sur une période. Dates en heure de Paris "
                      "(Europe/Paris), date_fin incluse. Filtres facultatifs : quai, type de conteneur, sens. "
                      "Rend la requête exécutée et ses paramètres.")
async def requete_mouvements(date_debut: date, date_fin: date, quai: int | None = None,
                             type_conteneur: str | None = None, sens: str | None = None) -> dict:
    ou, parametres = _filtres(date_debut, date_fin, quai, type_conteneur, sens)
    source = "FROM mouvements m JOIN escales e USING (escale_id)"
    sql_compte = f"SELECT count(*) {source} WHERE {ou}"
    sql = (f"SELECT m.mouvement_id, m.escale_id, e.quai, m.conteneur_id, m.sens, m.type_conteneur, "
           f"to_char(m.horodatage AT TIME ZONE 'Europe/Paris', 'YYYY-MM-DD\"T\"HH24:MI') AS horodatage_paris "
           f"{source} WHERE {ou} ORDER BY m.horodatage")
    requete = {"sql": sql, "parametres": [str(p) for p in parametres]}
    async with emprunter() as connexion:
        nombre = await connexion.fetchval(sql_compte, *parametres)
        if nombre > PLAFOND:
            raise ToolError(f"{nombre} mouvements correspondent : au-delà du plafond de {PLAFOND} lignes, rien n'est "
                            f"rendu. Affiner : préciser un quai (1 à 7), ou réduire la période à une semaine. "
                            f"Requête comptée : {sql_compte} ; paramètres : {requete['parametres']}.")
        lignes = await connexion.fetch(sql, *parametres)
    return {"nombre": nombre, "mouvements": [dict(l) for l in lignes], "requete": requete}


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp", json_response=True, show_banner=False,
            middleware=journal.http("pharos-data"))
