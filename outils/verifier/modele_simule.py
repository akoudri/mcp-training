"""Modèle simulé : rejoue un scénario à la place de pharos_client.modele.completer — déterministe et gratuit.

    with ModeleSimule([[appel("a1", "outil", {...})], "réponse finale"]) as simule:
        reponse, trace = boucle.executer("question", url=...)
    simule.recus          # les listes de messages reçues, tour par tour : ce que la boucle a réinjecté

Un tour est une liste d'appels (appel(...)), un texte final, ou une fonction des messages reçus qui rend
l'un ou l'autre (pour répondre selon le dernier résultat d'outil). Au-delà du scénario, le dernier tour
se répète. Extrait du vérificateur du LAB 4 ; utilisé par ceux des LAB 8 à 12.
"""

from __future__ import annotations

import contextlib
import copy
import importlib
import json
import os

from pharos.openrouter import Appel, ErreurModele, Reponse


def appel(ident: str, nom: str, arguments: dict) -> tuple[str, str, dict]:
    return ident, nom, arguments


class ModeleSimule:
    """Répond selon un scénario ; le contexte estimé vaut 1000 tokens par message."""

    def __init__(self, tours: list, panne: bool = False):
        self.tours, self.panne, self.recus = tours, panne, []
        self._remplacement = None

    def completer(self, messages, outils, modele=None, **_):
        self.recus.append(copy.deepcopy(messages))
        if self.panne:
            raise ErreurModele("crédit épuisé sur cette clé : prévenir le formateur.")
        tour = self.tours[min(len(self.recus) - 1, len(self.tours) - 1)]
        if callable(tour):
            tour = tour(messages)
        usage = {"prompt_tokens": self.estimer(messages), "completion_tokens": 20}
        if isinstance(tour, str):
            return Reponse({"role": "assistant", "content": tour}, [], usage)
        message = {"role": "assistant", "content": None, "tool_calls": [
            {"id": i, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, n, a in tour]}
        return Reponse(message, [Appel(i, n, a) for i, n, a in tour], usage)

    def estimer(self, messages, outils=()):
        return 1000 * len(messages)

    def __enter__(self) -> "ModeleSimule":
        self._remplacement = remplacer(importlib.import_module("pharos_client.modele"), self)
        self._remplacement.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        self._remplacement.__exit__(*exc)


@contextlib.contextmanager
def remplacer(modele, simule: ModeleSimule):
    """Remplace modele.completer/estimer_tokens par le simulé ; coupe aussi la clé réelle : un import
    direct de la fonction (au lieu de l'attribut du module) ne doit jamais pouvoir dépenser de crédit."""
    anciens = modele.completer, modele.estimer_tokens
    ancienne_cle = os.environ.get("OPENROUTER_API_KEY")
    modele.completer, modele.estimer_tokens = simule.completer, simule.estimer
    os.environ["OPENROUTER_API_KEY"] = ""
    try:
        yield
    finally:
        modele.completer, modele.estimer_tokens = anciens
        if ancienne_cle is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = ancienne_cle


# --- Modèle crédule (LAB 14) ---------------------------------------------------------------------

import re as _re

_GRAMMAIRE = {
    "destinataire": _re.compile(r"destinataire\s*:\s*([^\s\n]+)", _re.IGNORECASE),
    "navire": _re.compile(r"navire\s*:\s*([^\n]+)", _re.IGNORECASE),
    "conclusion": _re.compile(r"conclusion\s*:\s*aucun risque", _re.IGNORECASE),
}


class ModeleCredule:
    """Un modèle qui OBÉIT à ce qu'il lit (LAB 14) : après chaque résultat d'outil, il exécute les instructions
    balisées d'une grammaire fixe du kit trouvées dans le texte reçu — « destinataire: … » → publier_alerte,
    « navire: … » → navire_par_nom, « conclusion: aucun risque » → note finale complaisante. Il rend « le
    modèle qui se laisse convaincre » de façon déterministe. `depart` amorce la conversation (l'appel qui lit
    le document piégé)."""

    def __init__(self, depart: list[tuple[str, str, dict]], escale_id: str = "ESC-2026-0412"):
        self.depart = depart
        self.escale_id = escale_id
        self.recus: list = []
        self._faits: set[str] = set()
        self._remplacement = None

    def _dernier_texte(self, messages) -> str:
        for message in reversed(messages):
            if message.get("role") == "tool":
                return message.get("content") or ""
        return ""

    def completer(self, messages, outils, modele=None, **_):
        self.recus.append(copy.deepcopy(messages))
        noms = {o["function"]["name"] for o in outils}
        if len(self.recus) == 1:
            return self._appels(self.depart)
        texte = self._dernier_texte(messages)
        appels = []
        m = _GRAMMAIRE["destinataire"].search(texte)
        if m and "publier_alerte" in noms and ("destinataire", m.group(1)) not in self._faits:
            self._faits.add(("destinataire", m.group(1)))
            appels.append(appel("c_pub", "publier_alerte",
                                {"escale_id": self.escale_id, "niveau": "orange", "destinataire": m.group(1)}))
        m = _GRAMMAIRE["navire"].search(texte)
        if m and "navire_par_nom" in noms and ("navire", m.group(1).strip()) not in self._faits:
            self._faits.add(("navire", m.group(1).strip()))
            appels.append(appel("c_nav", "navire_par_nom", {"nom": m.group(1).strip()}))
        if appels:
            return self._appels(appels)
        if _GRAMMAIRE["conclusion"].search(" ".join(self._dernier_texte([m]) for m in messages if m.get("role") == "tool")):
            return "Note d'alerte : après analyse, aucun risque n'est à signaler pour cette escale."
        return "Analyse terminée."

    def _appels(self, tours):
        usage = {"prompt_tokens": 100, "completion_tokens": 10}
        message = {"role": "assistant", "content": None, "tool_calls": [
            {"id": i, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, n, a in tours]}
        return Reponse(message, [Appel(i, n, a) for i, n, a in tours], usage)

    def estimer(self, messages, outils=()):
        return 100 * len(messages)

    def __enter__(self):
        self._remplacement = remplacer(importlib.import_module("pharos_client.modele"), self)
        self._remplacement.__enter__()
        return self

    def __exit__(self, *exc):
        self._remplacement.__exit__(*exc)
