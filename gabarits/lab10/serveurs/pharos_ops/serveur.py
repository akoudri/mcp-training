"""pharos-ops v0 (LAB 10) — squelette. Les trois outils du brief appellent les deux API BRUTES : rien n'est
normalisé, aucune erreur n'est traduite, aucun plafond n'est posé, rien n'est rendu partiellement. C'est le
point de départ — pas un exemple à suivre.

Déjà branché : l'identité par jeton (pharos.autorisation) et le journal (logs/pharos-ops.jsonl) ; la position
de chaque quai (donnees/base/quais.yaml) ; le client météo pharos.meteo (URL et clé lues dans l'environnement,
réponse brute : voir sa documentation) ; l'adresse du référentiel (docs/api/referentiel.yaml, qui ment) ; le
lancement HTTP (make lab10-up → http://localhost:8103/mcp).

À écrire :
  étape 1 — normaliser la sortie : unités dans les noms (vent_kt, houle_m…), dates ISO 8601 avec fuseau, une
            règle unique pour les absences sur les deux API ; la clé n'apparaît nulle part ;
  étape 2 — le message de panne, en trois parties (bloc 17.3) ;
  étape 3 — un plafond par outil, et le refus qui dit comment consommer moins ;
  étape 4 — la réponse partielle de meteo_creneau : resultats, incomplets (quai, raison), complet.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import httpx
from fastmcp import FastMCP

from donnees.base import generer
from pharos import autorisation, horloge, journal, meteo

REFERENTIEL_URL = os.environ.get("REFERENTIEL_URL", "http://mocks:8000/referentiel")
# Position de chaque quai : le serveur la connaît, le modèle ne la donne jamais (bloc 16.1).
POSITIONS = {q.quai: (q.latitude, q.longitude) for q in generer.quais()}

mcp = FastMCP("pharos-ops", auth=autorisation.verificateur(), middleware=[journal.Journal("pharos-ops")])


def _paris(instant: datetime) -> datetime:
    """Une heure sans fuseau est lue à Paris : c'est une décision d'exploitation, pas un paramètre."""
    return instant.replace(tzinfo=horloge.FUSEAU) if instant.tzinfo is None else instant


@mcp.tool(name="meteo_creneau",
          description="Conditions météo marines sur un créneau d'accostage, pour un ou plusieurs quais.")
async def meteo_creneau(quais: list[int], debut: datetime, fin: datetime) -> dict:
    # Brut : un appel par quai, l'un après l'autre ; la première erreur interrompt tout.
    return {str(q): await meteo.previsions(*POSITIONS[q], _paris(debut), _paris(fin)) for q in quais}


@mcp.tool(name="meteo_alerte",
          description="Risque météo à venir sur un quai, dans les heures qui viennent.")
async def meteo_alerte(quai: int, horizon_h: int) -> dict:
    # Brut : les prévisions de l'horizon, sans seuil ni conclusion. Quel risque, et lequel ? À écrire.
    debut = horloge.maintenant().replace(minute=0, second=0, microsecond=0)
    return await meteo.previsions(*POSITIONS[quai], debut, debut + timedelta(hours=horizon_h))


@mcp.tool(name="navire_par_nom",
          description="Fiche d'un navire à partir de son nom : identifiant, caractéristiques, escales connues.")
async def navire_par_nom(nom: str) -> dict:
    # Brut : la réponse du référentiel telle quelle (pagination et version comprises).
    async with httpx.AsyncClient(timeout=10) as http:
        reponse = await http.get(f"{REFERENTIEL_URL}/navires", params={"nom": nom})
        reponse.raise_for_status()
        return reponse.json()


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp", json_response=True, show_banner=False,
            middleware=journal.http("pharos-ops"))
