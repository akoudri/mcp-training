"""pharos-legacy, migré en 2026-07-28 (solution de référence du LAB 2).

Plus de poignée de main ni de session : chaque requête se décrit elle-même (révision et client
dans _meta, méthode et nom dans les en-têtes). Le curseur de pagination, qui vivait dans la
session, voyage désormais dans un handle signé, daté, expirant, limité à une escale et à un
appelant. L'escale inconnue garde son code -32002 : consignée à l'inventaire, traitée au LAB 3.
"""

from __future__ import annotations

import json
import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from pharos import jetons
from serveurs.pharos_legacy import metier

REVISION = "2026-07-28"
REVISIONS_SERVIES = [REVISION]
IDENTITE = {"name": "pharos-legacy", "version": "2.0.0"}
CAPACITES = {"tools": {"listChanged": False}}
CLE_META = "io.modelcontextprotocol/"

OUTILS = [
    {"name": "etat_escale",
     "description": "État d'une escale : quai, créneau, tirant d'eau, statut.",
     "inputSchema": {"type": "object", "required": ["escale_id"], "properties": {
         "escale_id": {"type": "string", "description": "Identifiant d'escale, format ESC-AAAA-NNNN."}}}},
    {"name": "lister_mouvements",
     "description": "Première page (20 au plus) des mouvements de conteneurs d'une escale, et un handle "
                    "pour la page suivante s'il en reste une.",
     "inputSchema": {"type": "object", "required": ["escale_id"], "properties": {
         "escale_id": {"type": "string", "description": "Identifiant d'escale, format ESC-AAAA-NNNN."}}}},
    {"name": "page_suivante",
     "description": "Page suivante des mouvements, à partir du handle rendu par lister_mouvements ou par "
                    "le page_suivante précédent. Rend un nouveau handle s'il reste une page.",
     "inputSchema": {"type": "object", "required": ["handle"], "properties": {
         "handle": {"type": "string", "description": "Handle rendu par l'appel précédent (hdl_…), tel quel."}}}},
]


# --- JSON-RPC ------------------------------------------------------------------------------

def resultat(id_, contenu: dict, liste: bool = False) -> JSONResponse:
    """Tout résultat 2026-07-28 porte resultType ; les listes et discover, leur politique de cache."""
    contenu = {**contenu, "resultType": "complete"}
    if liste:
        contenu |= {"ttlMs": 0, "cacheScope": "private"}
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": contenu})


def erreur(id_, code: int, message: str, statut_http: int = 200, donnees: dict | None = None) -> JSONResponse:
    corps = {"code": code, "message": message} | ({"data": donnees} if donnees else {})
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "error": corps}, status_code=statut_http)


def structure(donnees: dict) -> dict:
    """Résultat d'outil : le JSON en texte, et la même donnée en structuredContent."""
    return {"content": [{"type": "text", "text": json.dumps(donnees, ensure_ascii=False)}],
            "structuredContent": donnees, "isError": False}


def erreur_metier(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


# --- Handles : le curseur qui n'a plus de session où vivre -----------------------------------

def _cle() -> str:
    return os.environ["CLE_SERVEUR"]


def page_et_handle(escale_id: str, numero: int, appelant: str) -> dict:
    page = metier.page_de_mouvements(escale_id, numero)
    if numero < page["pages"]:
        page["handle"] = jetons.signer({"escale_id": escale_id, "appelant": appelant, "position": numero + 1}, _cle())
    return page


def page_suivante(handle: str, appelant: str) -> dict:
    try:
        charge = jetons.verifier(handle, _cle())
    except jetons.JetonExpire:
        return erreur_metier("Handle expiré : relancer lister_mouvements pour repartir de la première page.")
    except jetons.JetonInvalide:
        return erreur_metier("Handle invalide (modifié ou tronqué) : le passer tel quel, ou relancer lister_mouvements.")
    if charge.get("appelant") != appelant:
        return erreur_metier("Ce handle a été émis pour un autre client : relancer lister_mouvements.")
    return structure(page_et_handle(charge["escale_id"], charge["position"], appelant))


# --- Outils --------------------------------------------------------------------------------

def appeler_outil(nom: str, arguments: dict, appelant: str) -> dict:
    """Rend le résultat d'outil ; lève metier.EscaleInconnue (traduite en -32002 par l'appelant)."""
    if nom == "etat_escale":
        return structure(metier.etat_escale(arguments.get("escale_id", "")))
    if nom == "lister_mouvements":
        return structure(page_et_handle(arguments.get("escale_id", ""), 1, appelant))
    if nom == "page_suivante":
        return page_suivante(str(arguments.get("handle", "")), appelant)
    return erreur_metier(f"Outil inconnu : {nom}.")


# --- Point d'entrée HTTP -------------------------------------------------------------------

def controler_entetes(requete: Request, methode: str, params: dict) -> str | None:
    """Mcp-Method et Mcp-Name déclarent : on vérifie qu'ils disent la même chose que le corps."""
    if requete.headers.get("mcp-method") != methode:
        return "l'en-tête Mcp-Method ne correspond pas à la méthode du corps"
    if methode == "tools/call" and requete.headers.get("mcp-name") != params.get("name"):
        return "l'en-tête Mcp-Name ne correspond pas à l'outil appelé dans le corps"
    return None


async def point_mcp(requete: Request) -> Response:
    if requete.method != "POST":       # ni flux SSE, ni session à fermer
        return Response(status_code=405, headers={"Allow": "POST"})
    try:
        message = json.loads(await requete.body())
    except ValueError:
        return erreur(None, -32700, "Erreur d'analyse : corps JSON illisible.", 400)
    if not isinstance(message, dict):
        return erreur(None, -32600, "Requête invalide : un seul message JSON-RPC par requête.", 400)
    methode, id_, params = message.get("method") or "", message.get("id"), message.get("params") or {}
    if methode.startswith("notifications/"):
        return Response(status_code=202)

    meta = params.get("_meta") or {}   # la révision et le client voyagent dans chaque requête
    revision = meta.get(CLE_META + "protocolVersion")
    if revision not in REVISIONS_SERVIES:
        return erreur(id_, -32022, "Révision non prise en charge.", 400,
                      {"supported": REVISIONS_SERVIES, "requested": revision})
    probleme = controler_entetes(requete, methode, params)
    if probleme:
        return erreur(id_, -32020, f"En-têtes incohérents : {probleme}.", 400)
    appelant = (meta.get(CLE_META + "clientInfo") or {}).get("name", "inconnu")

    if methode == "server/discover":
        return resultat(id_, {"supportedVersions": REVISIONS_SERVIES, "capabilities": CAPACITES,
                              "_meta": {CLE_META + "serverInfo": IDENTITE}}, liste=True)
    if methode == "ping":
        return resultat(id_, {})
    if methode == "tools/list":
        return resultat(id_, {"tools": OUTILS}, liste=True)
    if methode == "tools/call":
        try:
            return resultat(id_, appeler_outil(params.get("name", ""), params.get("arguments") or {}, appelant))
        except metier.EscaleInconnue as exc:
            return erreur(id_, -32002, f"Escale inconnue : {exc}.")
    return erreur(id_, -32601, f"Méthode inconnue : {methode}.")


def creer_app() -> Starlette:
    return Starlette(routes=[Route("/mcp", point_mcp, methods=["GET", "POST", "DELETE"])])


app = creer_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), log_level="warning")
