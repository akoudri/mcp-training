"""Demandes d'entrée (MRTR), côté client (LAB 12) — FOURNI. API synchrone, comme transport.Session.

    from pharos_client import entrees
    with entrees.SessionElicitation(url) as session:        # comme transport.Session, et déclare l'élicitation
        r = entrees.appeler_brut(session, nom, arguments)
        if isinstance(r, entrees.DemandeEntree):             # ni succès, ni erreur : le serveur demande quelque chose
            reponses = {cle: entrees.demander_utilisateur(d) for cle, d in r.demandes.items()}
            r = entrees.appeler_brut(session, nom, arguments, reponses=reponses, etat=r.etat)   # LE MÊME appel
        # r : un Resultat (texte, est_erreur, octets), comme session.appeler(...)

DemandeEntree(demandes, etat) : demandes = {cle: {"message": …, "schema": {…}}} ; etat = le requestState reçu,
opaque (scellé par le SDK du serveur) — à rendre tel quel, sans le lire ni le modifier.

demander_utilisateur(demande) -> {"action": "accept" | "decline" | "cancel", "content": {…}} : par défaut, la
question est posée au terminal. C'est un point de remplacement : les vérificateurs le remplacent par une
réponse scriptée (entrees.demander_utilisateur = …) — l'appeler toujours par le module, jamais par un import direct.

Le serveur peut aussi répondre par une tâche (LAB 11) : appeler_brut la suit alors comme taches.appeler_ou_suivre.
Un requestState refusé par le SDK du serveur (altéré, expiré, ou rejoué avec d'autres arguments) revient en
Resultat en erreur — « refus du protocole » — plutôt qu'en exception.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import mcp_types
from fastmcp import Client
from fastmcp_tasks.client_models import ClientCreateTaskResult
from mcp.shared.exceptions import MCPError

from pharos_client import taches
from pharos_client.transport import CLE_CORRELATION, URL_DEFAUT, Resultat, Session


@dataclass(frozen=True)
class DemandeEntree:
    demandes: dict[str, dict]
    etat: str | None


async def _ne_pas_piloter(message, response_type, params, context):
    """Déclare l'élicitation sans jamais répondre seul : c'est la boucle qui rejoue, par appeler_brut."""
    from fastmcp.client.elicitation import ElicitResult
    return ElicitResult(action="decline")


class SessionElicitation(Session):
    """transport.Session, dont le client déclare l'élicitation dans ses capacités (lues par le serveur dans _meta)."""

    def __init__(self, url=URL_DEFAUT, jeton: str | None = None, delai_s: float | None = None):
        super().__init__(url, jeton=jeton, delai_s=delai_s)
        jeton = jeton or os.environ.get("PHAROS_JETON") or None
        options = {"elicitation_handler": _ne_pas_piloter}
        self._client = Client(url, auth=jeton, **options) if jeton and isinstance(url, str) else Client(url, **options)


def _demandes(brut: mcp_types.InputRequiredResult) -> dict[str, dict]:
    demandes = {}
    for cle, requete in (brut.input_requests or {}).items():
        params = getattr(requete, "params", None)
        demandes[cle] = {"message": getattr(params, "message", ""),
                         "schema": getattr(params, "requested_schema", None) or {}}
    return demandes


def appeler_brut(session: Session, nom: str, arguments: dict, *, reponses: dict | None = None,
                 etat: str | None = None, correlation: str | None = None, afficher=print) -> Resultat | DemandeEntree:
    """Un tools/call : Resultat, ou DemandeEntree si le serveur demande une entrée. reponses et etat : le rejeu."""
    entrees = {cle: mcp_types.ElicitResult(action=r.get("action", "accept"), content=r.get("content"))
               for cle, r in (reponses or {}).items()} or None
    meta = {CLE_CORRELATION: correlation} if correlation else None
    try:
        brut = session._executer(session._client.session.call_tool(
            name=nom, arguments=arguments, input_responses=entrees, request_state=etat, meta=meta,
            read_timeout_seconds=session.delai_s, allow_input_required=True, allow_claimed=True))
    except MCPError as exc:
        texte = f"Refus du protocole : {exc}. Rien n'a été exécuté."
        return Resultat(texte, True, len(texte.encode("utf-8")))
    if isinstance(brut, mcp_types.InputRequiredResult):
        return DemandeEntree(_demandes(brut), brut.request_state)
    if isinstance(brut, ClientCreateTaskResult):
        return taches.suivre(taches.Tache(session, nom, brut), afficher=afficher)
    return taches._resultat(brut)


def demander_utilisateur(demande: dict) -> dict:
    """Pose la question au terminal. Oui/non pour un booléen ; toute autre réponse, ou aucune, vaut « non »."""
    print(f"\n  ?  {demande['message']}")
    contenu = {}
    for champ, proprietes in (demande["schema"].get("properties") or {}).items():
        if proprietes.get("type") != "boolean":
            continue
        try:
            reponse = input(f"     {proprietes.get('title', champ)} (oui/non) : ").strip().casefold()
        except EOFError:
            print("     (pas de terminal : réponse refusée)", file=sys.stderr)
            return {"action": "decline", "content": None}
        contenu[champ] = reponse in ("o", "oui", "y", "yes")
    return {"action": "accept", "content": contenu}
