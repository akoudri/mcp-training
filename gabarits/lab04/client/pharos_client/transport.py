"""Transport MCP — fourni : tools/list, tools/call et ressources, déjà branchés. Ne pas réimplémenter MCP.

API synchrone, pour que la boucle reste lisible :
    with Session() as s:
        outils = s.lister_outils()                       # format « function calling »
        r = s.appeler("rechercher_clause", {...})        # Resultat(texte, est_erreur, octets)
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from dataclasses import dataclass

from fastmcp import Client

from pharos.openrouter import outils_openai

URL_DEFAUT = os.environ.get("PHAROS_URL", "http://observateur:8101/mcp")


@dataclass(frozen=True)
class Resultat:
    texte: str
    est_erreur: bool
    octets: int


class Session:
    """Session synchrone sur un serveur MCP (URL, ou objet FastMCP pour les tests)."""

    def __init__(self, url=URL_DEFAUT):
        self._client = Client(url)
        self._evenements = asyncio.new_event_loop()
        self._fil = threading.Thread(target=self._evenements.run_forever, daemon=True)

    def _executer(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._evenements).result()

    async def _tenir(self, pret: asyncio.Future) -> None:
        try:
            async with self._client:
                pret.set_result(None)
                await self._fin.wait()
        except BaseException as exc:
            if not pret.done():
                pret.set_exception(exc)
            raise

    def __enter__(self) -> "Session":
        self._fil.start()

        async def demarrer():
            self._fin = asyncio.Event()
            pret = asyncio.get_running_loop().create_future()
            self._tache = asyncio.create_task(self._tenir(pret))
            await pret

        try:
            self._executer(demarrer())
        except BaseException:
            self._arreter()
            raise
        return self

    def __exit__(self, *exc) -> None:
        async def fermer():
            self._fin.set()
            await asyncio.gather(self._tache, return_exceptions=True)

        try:
            self._executer(fermer())
        finally:
            self._arreter()

    def _arreter(self) -> None:
        self._evenements.call_soon_threadsafe(self._evenements.stop)
        self._fil.join(5)
        self._evenements.close()

    def lister_outils(self) -> list[dict]:
        return outils_openai(self._executer(self._client.list_tools()))

    def appeler(self, nom: str, arguments: dict) -> Resultat:
        r = self._executer(self._client.call_tool(nom, arguments, raise_on_error=False))
        texte = "\n".join(getattr(b, "text", "") or "" for b in r.content)
        if not texte and r.structured_content is not None:
            texte = json.dumps(r.structured_content, ensure_ascii=False)
        return Resultat(texte, bool(r.is_error), len(texte.encode("utf-8")))

    def lister_ressources(self) -> list[dict]:
        return [{"uri": str(r.uri), "nom": r.name, "mime_type": r.mime_type, "taille": r.size}
                for r in self._executer(self._client.list_resources())]

    def lire_ressource(self, uri: str) -> str:
        return "\n".join(getattr(c, "text", "") or "" for c in self._executer(self._client.read_resource(uri)))
