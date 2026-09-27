"""pharos-data v1 (LAB 9, 13) — solution de référence : outils métier, cloisonnement dans la base, SQL libre en
lecture stricte. LAB 13 : le module navires de l'équipe référentiel, branché sous un nom préfixé par domaine
(data_navire_par_nom) — navire_par_nom existe déjà dans pharos-ops, et la collision n'apparaît qu'à l'assemblage.
L'identité vient du jeton (pharos.autorisation), jamais d'un argument ; chaque requête
s'exécute sous le rôle de l'appelant, et c'est la politique RLS qui filtre — aucun outil n'ajoute de WHERE.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta

import asyncpg
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from pharos import autorisation, base, horloge, journal
from serveurs.pharos_data import navires, perimetre
from serveurs.pharos_data.definition import CRITERES, CRITERES_EVALUES, DEFINITION_VERSION, MARGE_TIRANT_EAU_M

PARAMETRES_POOL = {"dsn": base.dsn("pharos_app"), "min_size": 1, "max_size": 5,
                   "server_settings": {"application_name": "pharos-data"}}
PLAFOND = 200
TYPES = ("20", "40", "refrigere")
SENS = ("embarquement", "debarquement")
etat: dict = {}

SCHEMA = """# Base d'exploitation du port PHAROS — dictionnaire

Toutes les dates et heures (escales.debut, escales.fin, mouvements.horodatage) sont en heure de Paris
(fuseau Europe/Paris). Longueurs et tirants d'eau en mètres (m).

Il n'existe **aucune autre source** de mouvements de conteneurs que la table `mouvements`. Ce que vous
voyez dépend de votre identité : un agent maritime ne voit que les escales de ses navires.

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
| quais.quai, longueur_m, tirant_eau_max_m, equipements | en mètres |

Relations utiles : mouvements → escales (escale_id) → navires (navire_id) ; escales → quais (quai).

## requete_sql
Lecture seule, une instruction SELECT, trois tables au plus, sur ces seules tables et colonnes :
escales, mouvements, navires, quais (colonnes ci-dessus). Résultat limité à 200 lignes.
Pour les questions courantes, préférer escales_a_risque, conflits_de_creneau et requete_mouvements.
"""


@asynccontextmanager
async def cycle_de_vie(serveur):
    etat["pool"] = await asyncpg.create_pool(**PARAMETRES_POOL)
    try:
        yield {}
    finally:
        await etat.pop("pool").close()


def emprunter():
    """La connexion sous le rôle de l'appelant de la requête en cours."""
    return perimetre.emprunter(etat.get("pool"), autorisation.identite())


mcp = FastMCP("pharos-data", auth=autorisation.verificateur(), lifespan=cycle_de_vie,
              middleware=[journal.Journal("pharos-data")], mask_error_details=True)


navires.enregistrer(mcp, emprunter, nom_outil="data_navire_par_nom")


@mcp.resource("pharos://schema/mouvements", name="schema-mouvements", mime_type="text/markdown",
              description="Dictionnaire des tables escales, mouvements, navires et quais : unités, fuseau, valeurs.")
def schema() -> str:
    return SCHEMA


def _jour(d: date) -> tuple[datetime, datetime]:
    debut = datetime.combine(d, time(0), horloge.FUSEAU)
    return debut, debut + timedelta(days=1)


def _paris(instant: datetime) -> str:
    return instant.astimezone(horloge.FUSEAU).isoformat(timespec="minutes")


# ------------------------------------------------------------------ requete_mouvements (LAB 8, sous identité)

def _filtres(date_debut: date, date_fin: date, quai, type_conteneur, sens) -> tuple[str, list]:
    if date_fin < date_debut:
        raise ToolError(f"Période vide : date_fin ({date_fin}) précède date_debut ({date_debut}).")
    if type_conteneur is not None and type_conteneur not in TYPES:
        raise ToolError(f"type_conteneur inconnu : « {type_conteneur} ». Valeurs possibles : {', '.join(TYPES)}.")
    if sens is not None and sens not in SENS:
        raise ToolError(f"sens inconnu : « {sens} ». Valeurs possibles : {', '.join(SENS)}.")
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


# ------------------------------------------------------------------ outils métier (LAB 9, bloc 14.1)

async def _escales_du_jour(d: date) -> list[dict]:
    debut, fin = _jour(d)
    async with emprunter() as connexion:
        lignes = await connexion.fetch(
            "SELECT e.escale_id, n.nom AS navire, e.quai, e.debut, e.fin, e.tirant_eau_m, q.tirant_eau_max_m "
            "FROM escales e JOIN navires n USING (navire_id) JOIN quais q USING (quai) "
            "WHERE e.statut <> 'annulee' AND e.debut < $2 AND $1 < e.fin ORDER BY e.quai, e.debut", debut, fin)
    return [dict(l) for l in lignes]


def _conflits(escales: list[dict]) -> list[dict]:
    conflits = []
    for i, a in enumerate(escales):
        for b in escales[i + 1:]:
            if a["quai"] == b["quai"] and b["debut"] < a["fin"] and a["debut"] < b["fin"]:
                debut, fin = max(a["debut"], b["debut"]), min(a["fin"], b["fin"])
                conflits.append({"quai": a["quai"], "escales": [a["escale_id"], b["escale_id"]],
                                 "debut": _paris(debut), "fin": _paris(fin),
                                 "chevauchement_min": int((fin - debut).total_seconds() // 60)})
    return conflits


@mcp.tool(name="conflits_de_creneau",
          description="Paires d'escales dont les créneaux se chevauchent sur un même quai, pour une date "
                      "(heure de Paris), avec la durée du chevauchement en minutes.")
async def conflits_de_creneau(date: date) -> dict:
    return {"date": date.isoformat(), "conflits": _conflits(await _escales_du_jour(date))}


@mcp.tool(name="escales_a_risque",
          description="Escales à risque pour une date (heure de Paris), selon la définition d'exploitation "
                      "2.0 : critères tirant_eau (tirant d'eau au-delà du maximum du quai, marge de 1,0 m "
                      "déduite) et conflit_creneau. Rend, par escale, les critères déclenchés et leur détail "
                      "chiffré, et definition_version. Météo et retard cumulé : non évalués dans cette version.")
async def escales_a_risque(date: date) -> dict:
    escales = await _escales_du_jour(date)
    conflits = _conflits(escales)
    resultat = []
    for e in escales:
        criteres = []
        limite = float(e["tirant_eau_max_m"]) - MARGE_TIRANT_EAU_M
        if float(e["tirant_eau_m"]) > limite:
            criteres.append({"critere": "tirant_eau", "detail": {
                "tirant_eau_m": float(e["tirant_eau_m"]), "quai_max_m": float(e["tirant_eau_max_m"]),
                "marge_m": MARGE_TIRANT_EAU_M, "depassement_m": round(float(e["tirant_eau_m"]) - limite, 2)}})
        for c in conflits:
            if e["escale_id"] in c["escales"]:
                autre = next(x for x in c["escales"] if x != e["escale_id"])
                criteres.append({"critere": "conflit_creneau", "detail": {
                    "escale_id": autre, "debut": c["debut"], "fin": c["fin"],
                    "chevauchement_min": c["chevauchement_min"]}})
        if criteres:
            resultat.append({"escale_id": e["escale_id"], "navire": e["navire"], "quai": e["quai"],
                             "debut": _paris(e["debut"]), "fin": _paris(e["fin"]), "criteres": criteres})
    return {"date": date.isoformat(), "definition_version": DEFINITION_VERSION,
            "criteres_evalues": list(CRITERES_EVALUES),
            "criteres_non_evalues": [c for c in CRITERES if c not in CRITERES_EVALUES],
            "escales": resultat}


# ------------------------------------------------------------------ SQL libre en lecture stricte (bloc 15.2)

@mcp.tool(name="requete_sql",
          description="Lecture libre, pour les questions qu'aucun autre outil ne couvre : une instruction SELECT, "
                      "trois tables au plus, parmi escales, mouvements, navires, quais (colonnes : ressource "
                      "pharos://schema/mouvements). Résultat limité à 200 lignes.")
async def requete_sql(sql: str) -> dict:
    lignes = await perimetre.executer_sur_perimetre(etat.get("pool"), sql, autorisation.identite())
    return {"lignes": lignes, "nombre": len(lignes)}


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp", json_response=True, show_banner=False,
            middleware=journal.http("pharos-data"))
