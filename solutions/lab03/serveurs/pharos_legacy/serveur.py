"""pharos-legacy, servant 2025-11-25 et 2026-07-28 depuis un seul déploiement (solution du LAB 3).

L'aiguillage décide, requête par requête, de la révision : la poignée de main fait foi quand elle
a eu lieu (initialize, ou un Mcp-Session-Id), _meta sinon. Un seul métier (metier.py), deux
adaptateurs au bord :
- page_suivante, divergence incompatible → adaptation : curseur de session en 2025-11-25, handle
  en 2026-07-28 (et le catalogue annonce la signature de chaque révision) ;
- le résultat d'appel, divergence additive → sur-ensemble : texte et structuredContent pour tous ;
- l'escale inconnue : -32002 en 2025-11-25, -32602 en 2026-07-28 (bloc 7.1).
"""

from __future__ import annotations

import json
import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from pharos import jetons
from serveurs.pharos_legacy import compat, metier

REVISION = "2026-07-28"
REVISIONS_SERVIES = [REVISION]      # ce qu'annonce server/discover : 2025-11-25 n'a pas de discover
IDENTITE = {"name": "pharos-legacy", "version": "2.1.0"}
CAPACITES = {"tools": {"listChanged": False}}
CLE_META = "io.modelcontextprotocol/"
CODE_ESCALE_INCONNUE = {compat.REVISION: -32002, REVISION: -32602}

_ESCALE = {"escale_id": {"type": "string", "description": "Identifiant d'escale, format ESC-AAAA-NNNN."}}
OUTILS_COMMUNS = [
    {"name": "etat_escale",
     "description": "État d'une escale : quai, créneau, tirant d'eau, statut.",
     "inputSchema": {"type": "object", "required": ["escale_id"], "properties": _ESCALE}},
    {"name": "lister_mouvements",
     "description": "Première page (20 au plus) des mouvements de conteneurs d'une escale. "
                    "Les pages suivantes s'obtiennent avec page_suivante.",
     "inputSchema": {"type": "object", "required": ["escale_id"], "properties": _ESCALE}},
]
PAGE_SUIVANTE = {
    compat.REVISION: {
        "name": "page_suivante",
        "description": "Page suivante des mouvements, à partir du dernier lister_mouvements de la session.",
        "inputSchema": {"type": "object", "properties": {}}},
    REVISION: {
        "name": "page_suivante",
        "description": "Page suivante des mouvements, à partir du handle rendu par lister_mouvements ou par "
                       "le page_suivante précédent. Rend un nouveau handle s'il reste une page.",
        "inputSchema": {"type": "object", "required": ["handle"], "properties": {
            "handle": {"type": "string", "description": "Handle rendu par l'appel précédent (hdl_…), tel quel."}}}},
}


# --- JSON-RPC ------------------------------------------------------------------------------

def resultat(id_, contenu: dict, revision: str, liste: bool = False) -> JSONResponse:
    """resultType, ttlMs et cacheScope n'existent qu'en 2026-07-28."""
    if revision == REVISION:
        contenu = {**contenu, "resultType": "complete"}
        if liste:
            contenu |= {"ttlMs": 0, "cacheScope": "private"}
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": contenu})


def erreur(id_, code: int, message: str, statut_http: int = 200, donnees: dict | None = None) -> JSONResponse:
    corps = {"code": code, "message": message} | ({"data": donnees} if donnees else {})
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "error": corps}, status_code=statut_http)


def structure(donnees: dict) -> dict:
    """Sur-ensemble : le JSON en texte (tous les clients) et en structuredContent (ignoré au besoin)."""
    return {"content": [{"type": "text", "text": json.dumps(donnees, ensure_ascii=False)}],
            "structuredContent": donnees, "isError": False}


def erreur_metier(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


# --- Adaptateur 2026-07-28 : le curseur voyage dans un handle -------------------------------

def _cle() -> str:
    return os.environ["CLE_SERVEUR"]


def page_et_handle(escale_id: str, numero: int, appelant: str) -> dict:
    page = metier.page_de_mouvements(escale_id, numero)
    if numero < page["pages"]:
        page["handle"] = jetons.signer({"escale_id": escale_id, "appelant": appelant, "position": numero + 1}, _cle())
    return page


def page_suivante_par_handle(handle: str, appelant: str) -> dict:
    try:
        charge = jetons.verifier(handle, _cle())
    except jetons.JetonExpire:
        return erreur_metier("Handle expiré : relancer lister_mouvements pour repartir de la première page.")
    except jetons.JetonInvalide:
        return erreur_metier("Handle invalide (modifié ou tronqué) : le passer tel quel, ou relancer lister_mouvements.")
    if charge.get("appelant") != appelant:
        return erreur_metier("Ce handle a été émis pour un autre client : relancer lister_mouvements.")
    return structure(page_et_handle(charge["escale_id"], charge["position"], appelant))


# --- Adaptateur 2025-11-25 : le curseur vit dans la session ---------------------------------

def page_suivante_par_session(session: dict) -> dict:
    curseur = session["curseur"]
    if curseur is None:
        return erreur_metier("Aucune pagination en cours : appeler d'abord lister_mouvements.")
    try:
        page = metier.page_de_mouvements(curseur["escale_id"], curseur["page"] + 1)
    except metier.PageHorsLimites:
        return erreur_metier(f"Plus de page pour {curseur['escale_id']} : tous les mouvements ont été lus.")
    curseur["page"] += 1
    return structure(page)


# --- Outils : un seul métier, l'aiguillage au bord --------------------------------------------

def appeler_outil(nom: str, arguments: dict, revision: str, appelant: str, session: dict | None) -> dict:
    """Rend le résultat d'outil ; lève metier.EscaleInconnue (traduite par l'appelant)."""
    if nom == "etat_escale":
        return structure(metier.etat_escale(arguments.get("escale_id", "")))
    if nom == "lister_mouvements":
        escale_id = arguments.get("escale_id", "")
        if revision == compat.REVISION:
            page = metier.page_de_mouvements(escale_id, 1)
            session["curseur"] = {"escale_id": escale_id, "page": 1}
            return structure(page)
        return structure(page_et_handle(escale_id, 1, appelant))
    if nom == "page_suivante":
        if revision == compat.REVISION:
            return page_suivante_par_session(session)
        return page_suivante_par_handle(str(arguments.get("handle", "")), appelant)
    return erreur_metier(f"Outil inconnu : {nom}.")


def controler_entetes(requete: Request, methode: str, params: dict) -> str | None:
    """Mcp-Method et Mcp-Name déclarent : on vérifie qu'ils disent la même chose que le corps."""
    if requete.headers.get("mcp-method") != methode:
        return "l'en-tête Mcp-Method ne correspond pas à la méthode du corps"
    if methode == "tools/call" and requete.headers.get("mcp-name") != params.get("name"):
        return "l'en-tête Mcp-Name ne correspond pas à l'outil appelé dans le corps"
    return None


# --- Point d'entrée HTTP : l'aiguillage -------------------------------------------------------

async def point_mcp(requete: Request) -> Response:
    sessions: compat.Sessions = requete.app.state.sessions
    session_id = requete.headers.get("mcp-session-id")
    if requete.method == "GET":
        compat.journaliser(compat.REVISION if session_id else None, "GET")
        return Response(status_code=405, headers={"Allow": "POST, DELETE"})
    if requete.method == "DELETE":
        compat.journaliser(compat.REVISION, "DELETE")
        return compat.fermer(sessions, session_id)
    try:
        message = json.loads(await requete.body())
    except ValueError:
        return erreur(None, -32700, "Erreur d'analyse : corps JSON illisible.", 400)
    if not isinstance(message, dict):
        return erreur(None, -32600, "Requête invalide : un seul message JSON-RPC par requête.", 400)
    methode, id_, params = message.get("method") or "", message.get("id"), message.get("params") or {}
    meta = params.get("_meta") or {}
    outil = params.get("name") if methode == "tools/call" else None

    # La poignée de main fait foi quand elle a eu lieu ; _meta sinon (jamais « pas de _meta, donc ancien »).
    if methode == "initialize" or session_id is not None:
        revision = compat.REVISION
        session = sessions.lire(session_id)
        compat.journaliser(revision, methode, session["client"] if session else None, outil)
        if methode == "initialize":
            return compat.repondre_initialize(sessions, id_, params, {"tools": {}}, IDENTITE)
        if session is None:
            return compat.refuser_sans_session(id_, session_id)
        appelant = session["client"]
    else:
        revision = meta.get(CLE_META + "protocolVersion")
        appelant = (meta.get(CLE_META + "clientInfo") or {}).get("name", "inconnu")
        session = None
        compat.journaliser(revision, methode, appelant, outil)
        if methode.startswith("notifications/"):
            return Response(status_code=202)
        if revision not in REVISIONS_SERVIES:
            return erreur(id_, -32022, "Révision non prise en charge : une requête sans session doit porter "
                          "_meta.io.modelcontextprotocol/protocolVersion.", 400,
                          {"supported": REVISIONS_SERVIES, "requested": revision})
        probleme = controler_entetes(requete, methode, params)
        if probleme:
            return erreur(id_, -32020, f"En-têtes incohérents : {probleme}.", 400)

    if methode.startswith("notifications/"):     # dont notifications/initialized
        return Response(status_code=202)
    if methode == "server/discover" and revision == REVISION:
        return resultat(id_, {"supportedVersions": REVISIONS_SERVIES, "capabilities": CAPACITES,
                              "_meta": {CLE_META + "serverInfo": IDENTITE}}, revision, liste=True)
    if methode == "ping":
        return resultat(id_, {}, revision)
    if methode == "tools/list":
        return resultat(id_, {"tools": [*OUTILS_COMMUNS, PAGE_SUIVANTE[revision]]}, revision, liste=True)
    if methode == "tools/call":
        try:
            contenu = appeler_outil(outil or "", params.get("arguments") or {}, revision, appelant, session)
        except metier.EscaleInconnue as exc:
            return erreur(id_, CODE_ESCALE_INCONNUE[revision], f"Escale inconnue : {exc}.")
        return resultat(id_, contenu, revision)
    return erreur(id_, -32601, f"Méthode inconnue : {methode}.")


def creer_app() -> Starlette:
    app = Starlette(routes=[Route("/mcp", point_mcp, methods=["GET", "POST", "DELETE"])])
    app.state.sessions = compat.Sessions()
    return app


app = creer_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), log_level="warning")
