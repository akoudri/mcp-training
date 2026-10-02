"""Compatibilité 2025-11-25 — fourni pour le LAB 3.

La mécanique de l'ancienne révision, extraite du pharos-legacy d'origine : poignée de main
(initialize, puis notifications/initialized), émission et contrôle du Mcp-Session-Id, table des
sessions avec le curseur de pagination de chacune. Vous l'avez démontée au LAB 2 ; elle est
fournie écrite, prête à être appelée par votre aiguillage (serveur.py). Le travail du lab porte
sur l'aiguillage et sur les deux divergences, pas ici.

Aussi fourni : journaliser(), une ligne JSON par requête dans logs/pharos-legacy.jsonl. Le champ
« revision » est celui que lit make lab3-verifier.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from starlette.responses import JSONResponse, Response

from pharos import horloge

REVISION = "2025-11-25"


class Sessions:
    """Mcp-Session-Id → {"client": nom du client, "curseur": {"escale_id", "page"} | None}.

    En mémoire, propre à chaque instance : derrière un répartiteur, un client 2025-11-25 doit
    retomber sur l'instance qui a ouvert sa session (affinité de session)."""

    def __init__(self) -> None:
        self._table: dict[str, dict] = {}

    def ouvrir(self, client: str) -> str:
        session_id = uuid.uuid4().hex
        self._table[session_id] = {"client": client, "curseur": None}
        return session_id

    def lire(self, session_id: str | None) -> dict | None:
        return self._table.get(session_id) if session_id else None

    def fermer(self, session_id: str | None) -> bool:
        return self._table.pop(session_id, None) is not None if session_id else False


def repondre_initialize(sessions: Sessions, id_, params: dict, capacites: dict, identite: dict) -> JSONResponse:
    """Répond à initialize en 2025-11-25 et ouvre une session (en-tête Mcp-Session-Id)."""
    client = (params.get("clientInfo") or {}).get("name", "inconnu")
    corps = {"jsonrpc": "2.0", "id": id_,
             "result": {"protocolVersion": REVISION, "capabilities": capacites, "serverInfo": identite}}
    return JSONResponse(corps, headers={"Mcp-Session-Id": sessions.ouvrir(client)})


def refuser_sans_session(id_, session_id: str | None) -> JSONResponse:
    """Requête 2025-11-25 sans session valide : 400 si l'en-tête manque, 404 s'il est inconnu."""
    if session_id is None:
        message, statut = "Session absente : commencer par initialize.", 400
    else:
        message, statut = "Session inconnue ou expirée : recommencer par initialize.", 404
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "error": {"code": -32600, "message": message}},
                        status_code=statut)


def fermer(sessions: Sessions, session_id: str | None) -> Response:
    """DELETE : le client 2025-11-25 ferme sa session."""
    return Response(status_code=200 if sessions.fermer(session_id) else 404)


def journaliser(revision: str | None, methode: str, client: str | None = None, outil: str | None = None) -> None:
    """Une ligne par requête : {"horodatage", "instance", "revision", "methode", "outil", "client"}."""
    chemin = Path(os.environ.get("PHAROS_JOURNAL_LEGACY", "logs/pharos-legacy.jsonl"))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ligne = {"horodatage": horloge.maintenant().isoformat(timespec="seconds"),
             "instance": os.environ.get("PHAROS_INSTANCE", "unique"), "revision": revision,
             "methode": methode, "outil": outil, "client": client}
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
