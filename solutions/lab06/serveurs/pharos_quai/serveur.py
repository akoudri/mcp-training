"""pharos-quai — quais, créneaux et accostages (LAB 6). Solution de référence : catalogue réécrit.

Seuls les noms et les descriptions ont changé : mêmes six outils, mêmes paramètres, mêmes schémas
(make lab6-mesurer retrouve chaque outil par son schéma). Chaque description suit le bloc 10.2 :
ce que l'outil fait, quand l'appeler, ce qu'il renvoie, ce qu'il ne fait pas.
"""

from __future__ import annotations

from datetime import date, time

from fastmcp import FastMCP

from serveurs.pharos_quai import metier

mcp = FastMCP("pharos-quai")


@mcp.tool(name="escales_du_jour",
          description="Liste les escales prévues à une date d (AAAA-MM-JJ), tous quais confondus : navire, "
                      "quai, début et fin. À appeler pour savoir quels navires sont attendus un jour donné. "
                      "Pour un seul quai, utiliser escales_du_quai.")
def get_data(d: date) -> dict:
    return metier.escales_du_jour(d)


@mcp.tool(name="escales_du_quai",
          description="Liste les escales prévues à une date d sur un seul quai f (numéro 1 à 4). À appeler "
                      "quand la question nomme un quai. Pour tous les quais, utiliser escales_du_jour.")
def get_data_2(d: date, f: int) -> dict:
    return metier.escales_du_quai(d, f)


@mcp.tool(name="heure_accostage",
          description="Calcule la première heure à laquelle le navire x (son nom) peut accoster à la date d : "
                      "créneau libre ou réservé pour lui, quai assez profond, fenêtre de marée si son tirant "
                      "d'eau l'exige. À appeler pour « à quelle heure tel navire peut-il accoster ». Ne liste "
                      "pas les réservations : voir creneaux_du_navire.")
def process(x: str, d: date) -> dict:
    return metier.heure_accostage(x, d)


@mcp.tool(name="caracteristiques_quai",
          description="Donne les caractéristiques physiques du quai id (1 à 4) : longueur, tirant d'eau "
                      "maximal, équipements. À appeler pour une question sur le quai lui-même, pas sur son "
                      "planning.")
def info_quai(id: int) -> dict:
    return metier.caracteristiques_quai(id)


@mcp.tool(name="creneaux_du_navire",
          description="Liste les créneaux réservés au navire q (son nom) à la date d : quai, début, fin. À "
                      "appeler pour savoir si un navire a un créneau, en partant de son nom. Ne calcule pas "
                      "l'heure d'accostage : voir heure_accostage.")
def search(q: str, d: date) -> dict:
    return metier.creneaux_du_navire(q, d)


@mcp.tool(name="creneau_libre",
          description="Dit si le créneau de deux heures qui contient l'heure h (HH:MM), au quai id et à la "
                      "date d, est libre ou réservé, et à quelle escale. À appeler quand le quai et l'heure sont "
                      "déjà connus ; pour partir d'un navire, utiliser creneaux_du_navire.")
def check(id: int, d: date, h: time) -> dict:
    return metier.disponibilite(id, d, h)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp", json_response=True, show_banner=False)
