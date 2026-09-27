"""Tâches côté client (LAB 11) — FOURNI. API synchrone, comme transport.Session.

Importer ce module fait déclarer l'extension Tasks à tout client fastmcp du processus (c'est l'import de
fastmcp_tasks qui l'active) : sans lui, le serveur voit un client qui ne sait pas suivre une tâche.

    from pharos_client import taches
    r = taches.appeler_ou_suivre(session, "recalculer_plan_quai", {"date": "2026-10-08"})
    # Si le serveur répond directement : le Resultat, comme session.appeler(...).
    # S'il rend une tâche : elle est suivie jusqu'au bout — chaque progression nouvelle est affichée, au rythme
    # que le serveur suggère (pollIntervalMs) — puis le résultat FINAL est rendu, comme un appel ordinaire.

    t = taches.soumettre(session, nom, arguments)       # Tache, ou Resultat si le serveur a répondu directement
    taches.suivre(t)                                    # ce que fait appeler_ou_suivre après soumettre
    t.etat()        # EtatTache(statut, message, intervalle_s) — statut : working, input_required, completed…
    t.resultat()    # attend la fin ; Resultat (texte, est_erreur, octets)
    t.annuler()     # tasks/cancel

Trois issues, toutes rendues en Resultat : terminé (le résultat de l'outil, éventuellement en erreur — une
exception de l'outil termine la tâche avec un résultat en erreur), annulé (« tâche annulée »), échoué (faute de
protocole). Le budget de tour (PHAROS_DELAI_S) borne la SOUMISSION, pas le travail : un appel ordinaire
(session.appeler) sur un outil qui répond en tâche attend la fin en silence, et coupe au bout du budget.

Issue inconnue, rendue elle aussi en Resultat en erreur, comme session.appeler : une soumission qui dépasse le
budget de tour, ou une tâche que le serveur ne connaît plus (redémarré pendant le calcul) — « résultat inconnu,
ne rien en conclure » : le travail a pu avoir lieu, ou non.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import fastmcp_tasks  # noqa: F401 — enregistre l'extension Tasks côté client : voir la documentation du module
from fastmcp_tasks import ToolTask
from fastmcp_tasks.client_models import ClientCreateTaskResult
from mcp.shared.exceptions import MCPError

from pharos_client.transport import CLE_CORRELATION, Resultat, Session

TERMINAUX = ("completed", "failed", "cancelled")
INTERVALLE_MIN_S = 0.2
INTERVALLE_DEFAUT_S = 5.0


@dataclass(frozen=True)
class EtatTache:
    statut: str
    message: str | None
    intervalle_s: float


def _intervalle(poll_interval_ms: int | None) -> float:
    return max(poll_interval_ms / 1000, INTERVALLE_MIN_S) if poll_interval_ms is not None else INTERVALLE_DEFAUT_S


def _inconnu(texte: str) -> Resultat:
    return Resultat(texte, True, len(texte.encode("utf-8")))


def _depasse(exc: Exception) -> bool:
    return isinstance(exc, TimeoutError) or "timed out" in str(exc).casefold()


def hors_budget(nom: str, delai_s: float) -> Resultat:
    """Le texte de transport.Session.appeler pour un appel qui dépasse le budget de tour : issue inconnue."""
    return _inconnu(f"L'outil {nom} n'a pas répondu dans le budget de tour ({delai_s:.0f} s) : "
                    "résultat inconnu, ne rien en conclure.")


def _perdue(nom: str, exc: Exception) -> Resultat:
    cause = "sans réponse du serveur" if _depasse(exc) else "perdue côté serveur"
    return _inconnu(f"Tâche {nom} {cause} ({exc}) : résultat inconnu, ne rien en conclure.")


def _resultat(brut) -> Resultat:
    texte = "\n".join(getattr(b, "text", "") or "" for b in brut.content)
    if not texte and getattr(brut, "structured_content", None) is not None:
        texte = json.dumps(brut.structured_content, ensure_ascii=False)
    return Resultat(texte, bool(brut.is_error), len(texte.encode("utf-8")))


class Tache:
    """Une tâche en cours côté serveur, pilotée de façon synchrone."""

    def __init__(self, session: Session, nom: str, cree: ClientCreateTaskResult):
        self._session, self.nom = session, nom
        self._tache = ToolTask(session._client, nom, cree, raise_on_error=False)
        self.intervalle_s = _intervalle(cree.poll_interval_ms)

    @property
    def identifiant(self) -> str:
        return self._tache.task_id

    def etat(self) -> EtatTache:
        e = self._session._executer(self._tache.status())
        self.intervalle_s = _intervalle(e.poll_interval_ms) if e.poll_interval_ms is not None else self.intervalle_s
        return EtatTache(e.status, e.status_message, self.intervalle_s)

    def resultat(self) -> Resultat:
        try:
            return _resultat(self._session._executer(self._tache.result()))
        except (TimeoutError, MCPError) as exc:
            return _perdue(self.nom, exc)

    def annuler(self) -> None:
        self._session._executer(self._tache.cancel())


def soumettre(session: Session, nom: str, arguments: dict, correlation: str | None = None) -> Tache | Resultat:
    """Soumet l'appel : Tache si le serveur a décidé d'en faire une tâche, Resultat s'il a répondu directement."""
    meta = {CLE_CORRELATION: correlation} if correlation else None
    try:
        brut = session._executer(session._client.session.call_tool(
            name=nom, arguments=arguments, meta=meta, read_timeout_seconds=session.delai_s, allow_claimed=True))
    except (TimeoutError, MCPError) as exc:
        if not _depasse(exc):
            raise
        return hors_budget(nom, session.delai_s)
    return Tache(session, nom, brut) if isinstance(brut, ClientCreateTaskResult) else _resultat(brut)


def suivre(tache: Tache, *, afficher=print, delai_max_s: float = 900.0) -> Resultat:
    """Suit une tâche jusqu'au bout : affiche chaque progression nouvelle, puis rend le résultat final."""
    afficher(f"    … {tache.nom} : tâche {tache.identifiant[:12]} acceptée par le serveur")
    dernier, fin = None, time.monotonic() + delai_max_s
    while True:
        try:
            etat = tache.etat()
        except (TimeoutError, MCPError) as exc:
            return _perdue(tache.nom, exc)
        if etat.message and etat.message != dernier:
            afficher(f"    … {tache.nom} : {etat.message}")
            dernier = etat.message
        if etat.statut in TERMINAUX:
            return tache.resultat()
        if time.monotonic() > fin:
            tache.annuler()
            texte = (f"Tâche {tache.nom} abandonnée côté client après {delai_max_s:.0f} s : résultat inconnu, "
                     "ne rien en conclure.")
            return Resultat(texte, True, len(texte.encode("utf-8")))
        time.sleep(etat.intervalle_s)


def appeler_ou_suivre(session: Session, nom: str, arguments: dict, *, correlation: str | None = None,
                      afficher=print, delai_max_s: float = 900.0) -> Resultat:
    """Appelle l'outil ; si c'est une tâche, affiche chaque progression nouvelle et rend le résultat final."""
    soumis = soumettre(session, nom, arguments, correlation)
    if isinstance(soumis, Resultat):
        return soumis
    return suivre(soumis, afficher=afficher, delai_max_s=delai_max_s)
