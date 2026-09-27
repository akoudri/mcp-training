"""Client HTTP du canal d'alertes (LAB 12 et suivants) — l'appel brut, sans MCP.

    accuse = await canal.publier(escale_id, niveau, destinataire, note)    # {"alerte_id": "ALR-0001", "recue": …}

Adresse lue dans l'environnement (CANAL_URL, défaut http://mocks:8000/canal). Le canal JOURNALISE et COMPTE ce
qu'il reçoit, par destinataire : make lab12-compteur. Une alerte partie ne se rattrape pas — il n'existe
aucune route pour la retirer. Erreurs : celles de httpx, telles quelles (400 si un champ obligatoire manque).
"""

from __future__ import annotations

import os

import httpx

URL_DEFAUT = "http://mocks:8000/canal"


async def publier(escale_id: str, niveau: str, destinataire: str, note: str = "", *, delai_s: float = 5.0) -> dict:
    corps = {"escale_id": escale_id, "niveau": niveau, "destinataire": destinataire, "note": note}
    async with httpx.AsyncClient(timeout=delai_s) as http:
        reponse = await http.post(f"{os.environ.get('CANAL_URL', URL_DEFAUT)}/alertes", json=corps)
        reponse.raise_for_status()
        return reponse.json()
