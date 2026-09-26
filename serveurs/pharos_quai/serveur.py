"""pharos-quai — quais, créneaux et accostages (LAB 6).

Le code est correct ; le catalogue, lui, a été écrit par quelqu'un qui n'avait jamais lu le module SR1.
Ce que fait réellement chaque outil : labs/lab6/verite.md.

Socle du LAB 6 : ne réécrire que les noms (name=) et les descriptions (description=). Les paramètres,
leurs noms et leurs types font partie des schémas : n'y pas toucher, ni au nombre d'outils.
"""

from __future__ import annotations

from datetime import date, time

from fastmcp import FastMCP

from serveurs.pharos_quai import metier

mcp = FastMCP("pharos-quai")


@mcp.tool(name="get_data",
          description="Récupère les données depuis la base en utilisant l'index construit au démarrage.")
def get_data(d: date) -> dict:
    return metier.escales_du_jour(d)


@mcp.tool(name="get_data_2",
          description="Variante de get_data avec filtrage.")
def get_data_2(d: date, f: int) -> dict:
    return metier.escales_du_quai(d, f)


@mcp.tool(name="process",
          description="Traite un élément.")
def process(x: str, d: date) -> dict:
    return metier.heure_accostage(x, d)


@mcp.tool(name="info_quai",
          description="Informations.")
def info_quai(id: int) -> dict:
    return metier.caracteristiques_quai(id)


@mcp.tool(name="search",
          description="Recherche.")
def search(q: str, d: date) -> dict:
    return metier.creneaux_du_navire(q, d)


@mcp.tool(name="check",
          description="Vérifie la disponibilité.")
def check(id: int, d: date, h: time) -> dict:
    return metier.disponibilite(id, d, h)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp", json_response=True, show_banner=False)
