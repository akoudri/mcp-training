"""Module navires — livré par l'équipe référentiel pour pharos-data (LAB 13) : la fiche d'un navire, lue dans la
base PHAROS, sous l'identité de l'appelant. FOURNI : ne pas le modifier, le brancher.

À brancher dans serveurs/pharos_data/serveur.py, après la création de mcp et d'emprunter :

    from serveurs.pharos_data import navires
    navires.enregistrer(mcp, emprunter)                     # nom_outil="navire_par_nom" par défaut

Puis regarder le catalogue agrégé des trois serveurs (make lab13-catalogue) avant d'aller plus loin.
"""

from __future__ import annotations

from fastmcp.exceptions import ToolError

DESCRIPTION = ("Fiche d'un navire à partir de son nom (recherche partielle, casse indifférente) : identifiant "
               "NAV-NNNN, IMO, longueur et tirant d'eau maximal en mètres, pavillon. Lue dans la base PHAROS.")


def enregistrer(mcp, emprunter, nom_outil: str = "navire_par_nom"):
    """Ajoute l'outil à mcp sous le nom donné. emprunter() : la connexion sous le rôle de l'appelant."""

    async def navire_par_nom(nom: str) -> dict:
        if not nom.strip():
            raise ToolError("Nom de navire vide : donner tout ou partie du nom, par exemple « Vent d'Autan ».")
        async with emprunter() as connexion:
            lignes = await connexion.fetch(
                "SELECT navire_id, nom, imo, longueur_m, tirant_eau_max_m, pavillon FROM navires "
                "WHERE nom ILIKE '%' || $1 || '%' ORDER BY nom LIMIT 10", nom.strip())
        return {"navires": [{**dict(l), "longueur_m": float(l["longueur_m"]),
                             "tirant_eau_max_m": float(l["tirant_eau_max_m"])} for l in lignes]}

    return mcp.tool(name=nom_outil, description=DESCRIPTION)(navire_par_nom)
