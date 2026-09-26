"""Répartiteur à deux instances, sans stockage partagé (LAB 2, 3, 5).

Alternance stricte, requête par requête — indépendamment des connexions keep-alive, qu'un
round-robin classique réutiliserait. Chaque réponse porte X-Pharos-Instance: a|b, visible dans
l'Inspector. AFFINITE=1 (LAB 3) : une requête qui porte un Mcp-Session-Id retourne à l'instance
qui l'a émis — la réponse des répartiteurs de production aux sessions de l'ancienne révision.
"""

from __future__ import annotations

import itertools
import os

import httpx
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response, StreamingResponse
from starlette.routing import Route

SAUTES = {"host", "content-length", "connection", "transfer-encoding", "keep-alive"}


def creer_repartiteur(amont_a: str, amont_b: str, affinite: bool = False) -> Starlette:
    instances = {"a": amont_a.rstrip("/"), "b": amont_b.rstrip("/")}
    tour = itertools.cycle("ab")
    sessions: dict[str, str] = {}
    http = httpx.AsyncClient(timeout=None)

    async def relayer(requete: Request) -> Response:
        session = requete.headers.get("mcp-session-id")
        nom = (sessions.get(session) if affinite and session else None) or next(tour)
        url = instances[nom] + requete.url.path + (f"?{requete.url.query}" if requete.url.query else "")
        entetes = {k: v for k, v in requete.headers.items() if k.lower() not in SAUTES}
        try:
            reponse = await http.send(http.build_request(requete.method, url, headers=entetes,
                                                         content=await requete.body()), stream=True)
        except httpx.HTTPError:
            return PlainTextResponse(f"instance {nom} injoignable ({instances[nom]})", status_code=502,
                                     headers={"X-Pharos-Instance": nom})
        emis = reponse.headers.get("mcp-session-id")
        if affinite and emis:
            sessions[emis] = nom
        sortants = {k: v for k, v in reponse.headers.items() if k.lower() not in SAUTES}
        sortants["X-Pharos-Instance"] = nom
        return StreamingResponse(reponse.aiter_raw(), status_code=reponse.status_code, headers=sortants,
                                 background=BackgroundTask(reponse.aclose))

    return Starlette(routes=[Route("/{chemin:path}", relayer, methods=["GET", "POST", "DELETE", "OPTIONS"])])


def main() -> None:
    import uvicorn

    app = creer_repartiteur(os.environ["AMONT_A"], os.environ["AMONT_B"], os.environ.get("AFFINITE") == "1")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), log_level="warning")


if __name__ == "__main__":
    main()
