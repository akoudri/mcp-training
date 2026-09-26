"""pharos-legacy — le serveur MCP de l'équipe d'exploitation, écrit il y a un an.

Révision 2025-11-25, en HTTP « streamable » (réponses JSON, sans flux SSE), écrit à la main sur
Starlette : poignée de main, table des sessions et curseur de pagination sont du code visible.
C'est ce code que le LAB 2 démonte. Le métier (escales, mouvements) est dans metier.py.
"""

from __future__ import annotations

import json
import os
import uuid

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from serveurs.pharos_legacy import metier

REVISION = "2025-11-25"
IDENTITE = {"name": "pharos-legacy", "version": "1.4.2"}

OUTILS = [
    {"name": "etat_escale",
     "description": "État d'une escale : quai, créneau, tirant d'eau, statut.",
     "inputSchema": {"type": "object", "required": ["escale_id"], "properties": {
         "escale_id": {"type": "string", "description": "Identifiant d'escale, format ESC-AAAA-NNNN."}}}},
    {"name": "lister_mouvements",
     "description": "Première page (20 au plus) des mouvements de conteneurs d'une escale. "
                    "Les pages suivantes s'obtiennent avec page_suivante.",
     "inputSchema": {"type": "object", "required": ["escale_id"], "properties": {
         "escale_id": {"type": "string", "description": "Identifiant d'escale, format ESC-AAAA-NNNN."}}}},
    {"name": "page_suivante",
     "description": "Page suivante des mouvements, à partir du dernier lister_mouvements de la session.",
     "inputSchema": {"type": "object", "properties": {}}},
]


# --- JSON-RPC ------------------------------------------------------------------------------

def resultat(id_, contenu: dict, entetes: dict | None = None) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": contenu}, headers=entetes)


def erreur(id_, code: int, message: str, statut_http: int = 200) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}},
                        status_code=statut_http)


def texte(donnees: dict, est_erreur: bool = False) -> dict:
    """Résultat d'outil : le JSON en contenu textuel, seule forme connue de nos clients."""
    return {"content": [{"type": "text", "text": json.dumps(donnees, ensure_ascii=False)}], "isError": est_erreur}


def erreur_metier(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


# --- Sessions : Mcp-Session-Id → {"client": nom du client, "curseur": {"escale_id", "page"} | None}

class Sessions:
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


# --- Outils --------------------------------------------------------------------------------

def appeler_outil(nom: str, arguments: dict, session: dict) -> dict:
    """Rend le résultat d'outil ; lève metier.EscaleInconnue (traduite en -32002 par l'appelant)."""
    if nom == "etat_escale":
        return texte(metier.etat_escale(arguments.get("escale_id", "")))
    if nom == "lister_mouvements":
        escale_id = arguments.get("escale_id", "")
        page = metier.page_de_mouvements(escale_id, 1)
        session["curseur"] = {"escale_id": escale_id, "page": 1}
        return texte(page)
    if nom == "page_suivante":
        curseur = session["curseur"]
        if curseur is None:
            return erreur_metier("Aucune pagination en cours : appeler d'abord lister_mouvements.")
        try:
            page = metier.page_de_mouvements(curseur["escale_id"], curseur["page"] + 1)
        except metier.PageHorsLimites:
            return erreur_metier(f"Plus de page pour {curseur['escale_id']} : tous les mouvements ont été lus.")
        curseur["page"] += 1
        return texte(page)
    return erreur_metier(f"Outil inconnu : {nom}.")


# --- Point d'entrée HTTP -------------------------------------------------------------------

async def point_mcp(requete: Request) -> Response:
    sessions: Sessions = requete.app.state.sessions
    session_id = requete.headers.get("mcp-session-id")
    if requete.method == "GET":        # pas de flux SSE ouvert par le serveur
        return Response(status_code=405, headers={"Allow": "POST, DELETE"})
    if requete.method == "DELETE":     # le client ferme sa session
        return Response(status_code=200 if sessions.fermer(session_id) else 404)
    try:
        message = json.loads(await requete.body())
    except ValueError:
        return erreur(None, -32700, "Erreur d'analyse : corps JSON illisible.", 400)
    if not isinstance(message, dict):
        return erreur(None, -32600, "Requête invalide : un seul message JSON-RPC par requête.", 400)
    methode, id_, params = message.get("method") or "", message.get("id"), message.get("params") or {}

    if methode == "initialize":        # la poignée de main : négociation, puis session
        client = (params.get("clientInfo") or {}).get("name", "inconnu")
        return resultat(id_, {"protocolVersion": REVISION, "capabilities": {"tools": {}}, "serverInfo": IDENTITE},
                        {"Mcp-Session-Id": sessions.ouvrir(client)})

    session = sessions.lire(session_id)
    if session is None:                # toute autre requête exige une session ouverte
        if session_id is None:
            return erreur(id_, -32600, "Session absente : commencer par initialize.", 400)
        return erreur(id_, -32600, "Session inconnue ou expirée : recommencer par initialize.", 404)

    if methode.startswith("notifications/"):     # dont notifications/initialized
        return Response(status_code=202)
    if methode == "ping":
        return resultat(id_, {})
    if methode == "tools/list":
        return resultat(id_, {"tools": OUTILS})
    if methode == "tools/call":
        try:
            return resultat(id_, appeler_outil(params.get("name", ""), params.get("arguments") or {}, session))
        except metier.EscaleInconnue as exc:
            return erreur(id_, -32002, f"Escale inconnue : {exc}.")
    return erreur(id_, -32601, f"Méthode inconnue : {methode}.")


def creer_app() -> Starlette:
    app = Starlette(routes=[Route("/mcp", point_mcp, methods=["GET", "POST", "DELETE"])])
    app.state.sessions = Sessions()
    return app


app = creer_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), log_level="warning")
