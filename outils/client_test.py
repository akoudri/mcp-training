"""Clients de test : un par révision (2025-11-25 et 2026-07-28), qui enregistrent chaque échange HTTP.

Utilisés par les vérificateurs, et à la main : make appeler REV=… URL=… OUTIL=… ARGS='{…}'.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field

import httpx
import mcp_types
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REVISIONS = {"2025-11-25": "legacy", "2026-07-28": "2026-07-28"}


@dataclass
class Echange:
    methode_http: str
    url: str
    entetes_requete: dict
    corps_requete: str
    statut: int = 0
    entetes_reponse: dict = field(default_factory=dict)
    corps_reponse: str = ""

    @property
    def methode_mcp(self) -> str | None:
        try:
            return json.loads(self.corps_requete).get("method")
        except (ValueError, AttributeError):
            return None


class ClientTest:
    """Client MCP d'une révision donnée ; « echanges » garde tout le trafic HTTP."""

    def __init__(self, url: str, revision: str = "2026-07-28", nom: str = "pharos-test"):
        if revision not in REVISIONS:
            raise ValueError(f"révision inconnue : {revision} (attendu : {', '.join(REVISIONS)})")
        self.url, self.revision = url, revision
        self.echanges: list[Echange] = []
        self._en_cours: dict[int, Echange] = {}
        transport = StreamableHttpTransport(url, httpx_client_factory=self._fabrique)
        self._client = Client(transport, mode=REVISIONS[revision],
                              client_info=mcp_types.Implementation(name=nom, version="1.0"))

    def _fabrique(self, **options) -> httpx.AsyncClient:
        return httpx.AsyncClient(event_hooks={"request": [self._requete], "response": [self._reponse]}, **options)

    async def _requete(self, requete: httpx.Request) -> None:
        echange = Echange(requete.method, str(requete.url), {k.lower(): v for k, v in requete.headers.items()},
                          requete.content.decode("utf-8", "replace") if requete.content else "")
        self.echanges.append(echange)
        self._en_cours[id(requete)] = echange

    async def _reponse(self, reponse: httpx.Response) -> None:
        echange = self._en_cours.pop(id(reponse.request), None)
        if echange is None:
            return
        echange.statut = reponse.status_code
        echange.entetes_reponse = {k.lower(): v for k, v in reponse.headers.items()}
        if not reponse.headers.get("content-type", "").startswith("text/event-stream"):
            await reponse.aread()
            echange.corps_reponse = reponse.text

    async def __aenter__(self) -> "ClientTest":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.__aexit__(*exc)

    async def outils(self):
        return await self._client.list_tools()

    async def appeler(self, nom: str, arguments: dict | None = None):
        return await self._client.call_tool(nom, arguments or {}, raise_on_error=False)

    async def ressources(self):
        return await self._client.list_resources()

    async def lire(self, uri: str):
        return await self._client.read_resource(uri)

    async def prompts(self):
        return await self._client.list_prompts()

    async def prompt(self, nom: str, arguments: dict | None = None):
        return await self._client.get_prompt(nom, arguments or {})

    async def brut(self, corps: dict, entetes: dict | None = None) -> httpx.Response:
        """Requête JSON-RPC forgée à la main (en-têtes libres), enregistrée comme les autres."""
        base = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        async with self._fabrique(timeout=30) as http:
            return await http.post(self.url, json=corps, headers={**base, **(entetes or {})})

    def instances(self) -> list[str]:
        return [e.entetes_reponse.get("x-pharos-instance", "?") for e in self.echanges if e.methode_mcp == "tools/call"]


def _resume(echange: Echange) -> str:
    session = echange.entetes_reponse.get("mcp-session-id") or echange.entetes_requete.get("mcp-session-id") or "–"
    instance = echange.entetes_reponse.get("x-pharos-instance", "–")
    return (f"  {echange.methode_http} {echange.methode_mcp or '?':<26} → {echange.statut}"
            f"   Mcp-Session-Id: {session}   X-Pharos-Instance: {instance}")


async def _appeler(url: str, revision: str, outil: str, arguments: dict) -> int:
    async with ClientTest(url, revision) as c:
        r = await c.appeler(outil, arguments)
    texte = "\n".join(getattr(b, "text", "") for b in r.content)
    try:
        texte = json.dumps(json.loads(texte), ensure_ascii=False, indent=2)
    except ValueError:
        pass
    print(("ERREUR MÉTIER (isError)\n" if r.is_error else "") + texte)
    print("\nÉchanges :")
    for e in c.echanges:
        print(_resume(e))
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="make appeler", description="Appelle un outil MCP et montre les échanges.")
    p.add_argument("--rev", default="2026-07-28", choices=list(REVISIONS))
    p.add_argument("url")
    p.add_argument("outil")
    p.add_argument("arguments", nargs="?", default="{}")
    a = p.parse_args(argv)
    try:
        arguments = json.loads(a.arguments or "{}")
    except json.JSONDecodeError:
        print(f"ARGS n'est pas du JSON valide : {a.arguments}")
        return 2
    return asyncio.run(_appeler(a.url, a.rev, a.outil, arguments))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
