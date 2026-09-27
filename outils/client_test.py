"""Clients de test : un par révision (2025-11-25 et 2026-07-28), qui enregistrent chaque échange HTTP.

Utilisés par les vérificateurs, et à la main : make appeler REV=… URL=… OUTIL=… ARGS='{…}'.

Profils (LAB 11 et 12, spec §8.4) — ce que le client déclare au serveur :
  complet            l'extension Tasks et l'élicitation (il refuse toute demande : les vérificateurs
                     rejouent eux-mêmes, par appeler_brut)
  sans_tasks         aucune extension interne (ni Tasks, ni MCP Apps) : « le client sans extension »
  sans_elicitation   Tasks, pas d'élicitation
  defaut             élicitation, mais répond la valeur « default » du schéma sans rien demander (LAB 12 ext. C)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field

import fastmcp_tasks  # noqa: F401 — enregistre l'extension Tasks côté client (profil complet)
import httpx
import mcp_types
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.shared.exceptions import MCPError

REVISIONS = {"2025-11-25": "legacy", "2026-07-28": "2026-07-28"}
PROFILS = ("complet", "sans_tasks", "sans_elicitation", "defaut")


class ServeurInjoignable(Exception):
    """Le serveur visé ne répond pas : 502 de l'observateur (serveur non démarré) ou connexion refusée."""


class ClientSansExtension(Client):
    """Ne déclare aucune extension interne de fastmcp (Tasks, MCP Apps)."""

    _auto_internal_extensions = False


async def _refuser(message, response_type, params, context):
    from fastmcp.client.elicitation import ElicitResult
    return ElicitResult(action="decline")


async def _repondre_defaut(message, response_type, params, context):
    schema = getattr(params, "requested_schema", None) or {}
    return {nom: p["default"] for nom, p in (schema.get("properties") or {}).items() if "default" in p}


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

    def __init__(self, url: str, revision: str = "2026-07-28", nom: str = "pharos-test", jeton: str | None = None,
                 profil: str = "complet"):
        if revision not in REVISIONS:
            raise ValueError(f"révision inconnue : {revision} (attendu : {', '.join(REVISIONS)})")
        if profil not in PROFILS:
            raise ValueError(f"profil inconnu : {profil} (attendu : {', '.join(PROFILS)})")
        self.url, self.revision, self.profil = url, revision, profil
        self.echanges: list[Echange] = []
        self._en_cours: dict[int, Echange] = {}
        # jeton : identité de l'appelant (LAB 9 et suivants), envoyée en « Authorization: Bearer ».
        self.jeton = jeton
        transport = StreamableHttpTransport(url, httpx_client_factory=self._fabrique)
        classe = ClientSansExtension if profil == "sans_tasks" else Client
        gestionnaire = {"complet": _refuser, "sans_tasks": _refuser, "defaut": _repondre_defaut}.get(profil)
        self._client = classe(transport, mode=REVISIONS[revision], elicitation_handler=gestionnaire,
                              client_info=mcp_types.Implementation(name=nom, version="1.0"))

    def _fabrique(self, **options) -> httpx.AsyncClient:
        if self.jeton:
            options["headers"] = {**(options.get("headers") or {}), "Authorization": f"Bearer {self.jeton}"}
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
        try:
            await self._client.__aexit__(*exc)
        except Exception:
            if exc[0] is None:              # sinon, l'erreur de fermeture masquerait celle qui remonte déjà
                raise

    async def outils(self):
        return await self._client.list_tools()

    async def joindre(self, lancer: str) -> None:
        """Premier échange : lève ServeurInjoignable, qui dit quoi lancer, plutôt qu'une trace Python."""
        try:
            await self.outils()
        except (MCPError, httpx.HTTPError) as exc:
            raise ServeurInjoignable(f"{self.url} ne répond pas ({exc}) : lancer {lancer}.") from exc

    async def appeler(self, nom: str, arguments: dict | None = None):
        return await self._client.call_tool(nom, arguments or {}, raise_on_error=False)

    async def appeler_brut(self, nom: str, arguments: dict | None = None, reponses: dict | None = None,
                           etat: str | None = None):
        """tools/call sans rien piloter : rend le résultat tel que le serveur l'envoie — CallToolResult,
        ClientCreateTaskResult (une tâche) ou InputRequiredResult (une demande d'entrée, à rejouer soi-même)."""
        return await self._client.session.call_tool(
            name=nom, arguments=arguments or {}, input_responses=reponses, request_state=etat,
            allow_claimed=True, allow_input_required=True)

    def declare(self) -> str:
        return {"complet": "Tasks : oui · élicitation : oui (refuse toute demande)",
                "sans_tasks": "Tasks : non (aucune extension) · élicitation : oui (refuse toute demande)",
                "sans_elicitation": "Tasks : oui · élicitation : non",
                "defaut": "Tasks : oui · élicitation : oui, répond la valeur par défaut sans rien demander"}[self.profil]

    async def ressources(self):
        return await self._client.list_resources()

    async def gabarits_de_ressources(self):
        return await self._client.list_resource_templates()

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


async def _appeler(url: str, revision: str, outil: str, arguments: dict, jeton: str | None = None) -> int:
    async with ClientTest(url, revision, jeton=jeton) as c:
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
    p.add_argument("--jeton", default=os.environ.get("PHAROS_JETON") or None, help="identité (LAB 9 et suivants)")
    a = p.parse_args(argv)
    try:
        arguments = json.loads(a.arguments or "{}")
    except json.JSONDecodeError:
        print(f"ARGS n'est pas du JSON valide : {a.arguments}")
        return 2
    return asyncio.run(_appeler(a.url, a.rev, a.outil, arguments, a.jeton))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
