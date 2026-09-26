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
