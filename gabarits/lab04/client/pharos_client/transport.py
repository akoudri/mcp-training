"""Transport MCP — fourni : tools/list, tools/call et ressources, déjà branchés. Ne pas réimplémenter MCP.

API synchrone, pour que la boucle reste lisible :
    with Session() as s:
        outils = s.lister_outils()                       # format « function calling »
        r = s.appeler("rechercher_clause", {...})        # Resultat(texte, est_erreur, octets)

Session(url, jeton=None, delai_s=None) : le jeton porteur (à défaut PHAROS_JETON) identifie l'appelant
(LAB 9 et suivants) ; delai_s (à défaut PHAROS_DELAI_S, 20 s) est le budget de temps d'un appel d'outil —
le timeout d'un outil doit lui rester inférieur (LAB 10). appeler(…, correlation=…) transmet l'identifiant
de la trace au serveur, dans _meta, pour son journal.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from dataclasses import dataclass

import httpx
from fastmcp import Client
from mcp.shared.exceptions import MCPError

from pharos.openrouter import outils_openai

URL_DEFAUT = os.environ.get("PHAROS_URL", "http://observateur:8101/mcp")
DELAI_DEFAUT_S = float(os.environ.get("PHAROS_DELAI_S", "20"))
CLE_CORRELATION = "pharos/correlation"


@dataclass(frozen=True)
class Resultat:
    texte: str
    est_erreur: bool
    octets: int


def _exige_une_identite(url) -> bool:
    """Après un échec d'ouverture : le serveur répond-il 401 à une requête sans jeton ?"""
    if not isinstance(url, str):
        return False
    try:
        return httpx.post(url, json={}, timeout=5).status_code == 401
    except httpx.HTTPError:
        return False


class Session:
    """Session synchrone sur un serveur MCP (URL, ou objet FastMCP pour les tests)."""

    def __init__(self, url=URL_DEFAUT, jeton: str | None = None, delai_s: float | None = None):
        self.url = url if isinstance(url, str) else getattr(url, "name", "mémoire")
        jeton = jeton or os.environ.get("PHAROS_JETON") or None
        self.delai_s = delai_s or DELAI_DEFAUT_S
        self._client = Client(url, auth=jeton) if jeton and isinstance(url, str) else Client(url)
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
            if pret.done():
                raise
            # échec avant que la session soit prête (ex. serveur injoignable) : __enter__ échoue via
            # « pret », et __exit__ ne sera jamais appelé pour récupérer cette tâche — ne pas la laisser
            # se terminer sur une exception non récupérée (bruit « Task exception was never retrieved »).
            pret.set_exception(exc)

    def __enter__(self) -> "Session":
        self._fil.start()

        async def demarrer():
            self._fin = asyncio.Event()
            pret = asyncio.get_running_loop().create_future()
            self._tache = asyncio.create_task(self._tenir(pret))
            await pret

        try:
            self._executer(demarrer())
        except BaseException as exc:
            self._arreter()
            if _exige_une_identite(self.url):
                raise PermissionError("HTTP 401 : ce serveur exige une identité. Relancer avec PHAROS_JETON=… "
                                      "(les jetons de salle : make lab9-identites).") from exc
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

    def appeler(self, nom: str, arguments: dict, correlation: str | None = None) -> Resultat:
        meta = {CLE_CORRELATION: correlation} if correlation else None
        try:
            r = self._executer(self._client.call_tool(nom, arguments, raise_on_error=False,
                                                      timeout=self.delai_s, meta=meta))
        except (TimeoutError, MCPError) as exc:
            if not isinstance(exc, TimeoutError) and "timed out" not in str(exc).casefold():
                raise
            texte = (f"L'outil {nom} n'a pas répondu dans le budget de tour ({self.delai_s:.0f} s) : "
                     "résultat inconnu, ne rien en conclure.")
            return Resultat(texte, True, len(texte.encode("utf-8")))
        texte = "\n".join(getattr(b, "text", "") or "" for b in r.content)
        if not texte and r.structured_content is not None:
            texte = json.dumps(r.structured_content, ensure_ascii=False)
        return Resultat(texte, bool(r.is_error), len(texte.encode("utf-8")))

    def lister_ressources(self) -> list[dict]:
        return [{"uri": str(r.uri), "nom": r.name, "mime_type": r.mime_type, "taille": r.size}
                for r in self._executer(self._client.list_resources())]

    def lire_ressource(self, uri: str) -> str:
        return "\n".join(getattr(c, "text", "") or "" for c in self._executer(self._client.read_resource(uri)))
