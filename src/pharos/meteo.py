"""Client HTTP de la météo marine (LAB 10 et suivants) — l'appel brut, SANS normalisation, et sans MCP.

    brut = await meteo.previsions(latitude, longitude, debut, fin)       # debut, fin : datetime AVEC fuseau

URL (METEO_URL, défaut http://mocks:8000/meteo) et clé (METEO_CLE) sont lues dans l'environnement du
processus, à chaque appel : la clé n'est jamais un paramètre. Réponse brute de l'API, telle quelle :

    {"latitude": …, "longitude": …, "timezone": "GMT", "utc_offset_seconds": 0,
     "hourly_units": {"time": "iso8601", "wind_speed_10m": "kn", "wind_gusts_10m": "kn",
                      "wave_height": "m", "visibility": "km"},
     "hourly": {"time": ["2026-10-08T12:00", …],          ← heures GMT, sans fuseau
                "wind_speed_10m": [12.4, …], "wind_gusts_10m": […], "wave_height": […],
                "visibility": [9.1, None, …]}}              ← une valeur peut manquer (null)

Erreurs : celles de httpx, telles quelles — httpx.HTTPStatusError (403 clé refusée, 400 paramètre refusé,
429 quota, 503 panne ; en-tête Retry-After sur 429), httpx.TimeoutException, httpx.TransportError.
Attention : le message d'une HTTPStatusError contient l'URL complète, clé comprise (bloc 17.1).
Utilisé par pharos-ops (LAB 10), par le moteur de planification (LAB 11) et par pharos-data (LAB 13).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

URL_DEFAUT = "http://mocks:8000/meteo"
VARIABLES = "wind_speed_10m,wind_gusts_10m,wave_height,visibility"


def _gmt(instant: datetime, nom: str) -> str:
    if instant.tzinfo is None:
        raise ValueError(f"{nom} sans fuseau : passer un datetime avec fuseau (l'API attend des heures GMT).")
    return instant.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


async def previsions(latitude: float, longitude: float, debut: datetime, fin: datetime, *,
                     delai_s: float = 10.0) -> dict:
    """Prévisions horaires brutes sur [debut, fin] ; lève les erreurs httpx sans les traduire."""
    cle = os.environ.get("METEO_CLE")
    if not cle:
        raise RuntimeError("METEO_CLE absente de l'environnement du serveur (variable de salle, compose/commun/base.yaml).")
    parametres = {"latitude": latitude, "longitude": longitude, "hourly": VARIABLES,
                  "start_hour": _gmt(debut, "debut"), "end_hour": _gmt(fin, "fin"), "apikey": cle}
    async with httpx.AsyncClient(timeout=delai_s) as http:
        reponse = await http.get(f"{os.environ.get('METEO_URL', URL_DEFAUT)}/previsions", params=parametres)
        reponse.raise_for_status()
        return reponse.json()
