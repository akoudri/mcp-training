"""Journal serveur (LAB 8 et suivants) : une ligne JSON par appel d'outil, refus compris.

    mcp = FastMCP("pharos-data", middleware=[journal.Journal("pharos-data")])
    mcp.run(..., middleware=journal.http("pharos-data"))    # refus HTTP (jeton absent : 401)

Fichier : logs/<serveur>.jsonl (dossier git-ignoré). Chaque ligne : horodatage, serveur, correlation
(l'identifiant de la trace du client, porté dans _meta sous « pharos/correlation »), outil, arguments,
identite, issue (ok | refus | erreur), message (ce que le client a reçu), erreur_brute (jamais renvoyée
au client). C'est la trace d'audit qui garde les appels REFUSÉS (LAB 14), et l'endroit où l'erreur brute
de la base est journalisée sans être diffusée (slide 300) : journal.consigner_erreur(exc).
"""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from pathlib import Path

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from starlette.middleware import Middleware as MiddlewareAsgi

from pharos import horloge

CLE_CORRELATION = "pharos/correlation"
_erreur_brute: ContextVar[list | None] = ContextVar("pharos_erreur_brute", default=None)


def dossier() -> Path:
    return Path(os.environ.get("PHAROS_LOGS", Path(__file__).resolve().parents[2] / "logs"))


def ecrire(serveur: str, **champs) -> None:
    chemin = dossier() / f"{serveur}.jsonl"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ligne = {"horodatage": horloge.maintenant().isoformat(timespec="seconds"), "serveur": serveur, **champs}
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")


def lire(serveur: str) -> list[dict]:
    chemin = dossier() / f"{serveur}.jsonl"
    if not chemin.exists():
        return []
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]


def consigner_erreur(exc: BaseException) -> None:
    """À appeler dans un outil qui remplace une erreur brute par un message propre : la brute va au journal."""
    en_cours = _erreur_brute.get()
    if en_cours is not None:
        en_cours.append(f"{exc.__class__.__name__}: {exc}")


def _meta(contexte) -> dict:
    try:
        meta = contexte.fastmcp_context.request_context.meta
    except (AttributeError, RuntimeError):
        return {}
    if meta is None:
        return {}
    return meta.model_dump(by_alias=True) if hasattr(meta, "model_dump") else dict(meta)


def _identite() -> str | None:
    # Import différé : évite un cycle si autorisation journalise un jour, et garde journal.lire() léger pour les
    # vérificateurs, qui n'ont pas besoin de l'authentification du serveur.
    from pharos import autorisation

    try:
        return autorisation.identite().nom
    except ToolError:
        return None


class Journal(Middleware):
    """Intergiciel fastmcp : journalise chaque tools/call, son issue et l'erreur brute éventuelle."""

    def __init__(self, serveur: str):
        self.serveur = serveur

    async def on_call_tool(self, context, call_next):
        erreurs: list[str] = []
        marque = _erreur_brute.set(erreurs)
        champs = {"correlation": _meta(context).get(CLE_CORRELATION), "outil": context.message.name,
                  "arguments": context.message.arguments or {}, "identite": _identite()}
        try:
            resultat = await call_next(context)
        except ToolError as exc:
            if not erreurs and exc.__cause__ is not None:
                erreurs.append(f"{exc.__cause__.__class__.__name__}: {exc.__cause__}")
            ecrire(self.serveur, **champs, issue="refus", message=str(exc), erreur_brute=" | ".join(erreurs) or None)
            raise
        except Exception as exc:
            ecrire(self.serveur, **champs, issue="erreur", message=None,
                   erreur_brute=" | ".join([*erreurs, f"{exc.__class__.__name__}: {exc}"]))
            raise
        finally:
            _erreur_brute.reset(marque)
        issue = "refus" if getattr(resultat, "is_error", False) else "ok"
        ecrire(self.serveur, **champs, issue=issue, message=None, erreur_brute=" | ".join(erreurs) or None)
        return resultat


class _JournalHttp:
    """Intergiciel ASGI : journalise les requêtes refusées avant MCP (401 sans jeton, 403)."""

    def __init__(self, app, serveur: str):
        self.app, self.serveur = app, serveur

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def envoyer(message):
            if message["type"] == "http.response.start" and message["status"] in (401, 403):
                ecrire(self.serveur, correlation=None, outil=None, arguments=None, identite=None, issue="refus",
                       message=f"HTTP {message['status']} sur {scope.get('method')} {scope.get('path')}",
                       erreur_brute=None)
            await send(message)

        return await self.app(scope, receive, envoyer)


def http(serveur: str) -> list[MiddlewareAsgi]:
    return [MiddlewareAsgi(_JournalHttp, serveur=serveur)]
