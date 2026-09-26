"""Adaptateur d'autorisation factice (LAB 9 et suivants) : l'identité vient du jeton, jamais d'un argument.

Trois jetons fixes de salle — ce ne sont pas des secrets, le mécanisme réel est traité au module SG2 :
le jour où il remplacera cet adaptateur, aucun outil ne devra changer.

    mcp = FastMCP("pharos-data", auth=autorisation.verificateur())   # sans jeton valide : HTTP 401
    qui = autorisation.identite()                                    # dans un outil

En transport mémoire (tests), il n'y a pas d'en-tête HTTP : « with en_tant_que("jeton-rance"): … ».
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.dependencies import get_access_token


@dataclass(frozen=True)
class Identite:
    nom: str
    profil: str               # "exploitation" | "agent"
    agent_id: str | None      # AG-RANCE, AG-IROISE ; None pour l'exploitation

    @property
    def role(self) -> str:
        """Rôle PostgreSQL à endosser (SET LOCAL ROLE) pour agir au nom de cette identité."""
        return "pharos_exploitation" if self.profil == "exploitation" else "pharos_agent"


JETONS = {
    "jeton-exploitation": Identite("Exploitation du terminal", "exploitation", None),
    "jeton-rance": Identite("Agence Maritime Rance", "agent", "AG-RANCE"),
    "jeton-iroise": Identite("Consignation Iroise", "agent", "AG-IROISE"),
}
_forcee: ContextVar[Identite | None] = ContextVar("pharos_identite_forcee", default=None)


def verificateur() -> StaticTokenVerifier:
    return StaticTokenVerifier(tokens={jeton: {"client_id": i.nom, "scopes": [], "profil": i.profil,
                                                "agent_id": i.agent_id} for jeton, i in JETONS.items()})


@contextmanager
def en_tant_que(jeton: str):
    """Pour les tests en mémoire : les appels faits dans ce bloc portent l'identité du jeton."""
    if jeton not in JETONS:
        raise ValueError(f"jeton inconnu : {jeton} (attendu : {', '.join(JETONS)})")
    marque = _forcee.set(JETONS[jeton])
    try:
        yield JETONS[jeton]
    finally:
        _forcee.reset(marque)


def identite() -> Identite:
    """L'identité de la requête en cours ; ToolError si aucune (le serveur n'a pas branché l'adaptateur)."""
    forcee = _forcee.get()
    if forcee is not None:
        return forcee
    jeton = get_access_token()
    if jeton is not None and jeton.token in JETONS:
        return JETONS[jeton.token]
    raise ToolError("Identité inconnue : la requête ne porte aucun jeton reconnu. "
                    "Relancer le client avec PHAROS_JETON (voir « make lab9-identites »).")
