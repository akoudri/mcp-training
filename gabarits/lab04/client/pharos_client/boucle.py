"""pharos-client — la boucle agentique (LAB 4). À écrire.

Fourni : transport.Session, modele.completer, modele.estimer_tokens, trace.Enregistrement, trace.afficher.
Pas fourni : la boucle, la collecte de la trace, les critères d'arrêt. C'est le lab.

Règles du jeu (le vérificateur s'y appuie) :
  - appeler le modèle par modele.completer(...) et estimer par modele.estimer_tokens(...) ;
  - executer() rend (réponse, trace) ; un arrêt anormal lève BudgetDepasse ou EchecNonRecuperable,
    qui portent TOUJOURS la trace complète (attribut .trace).
"""

from __future__ import annotations

from pharos_client import modele  # noqa: F401 — modele.completer, modele.estimer_tokens
from pharos_client.trace import Enregistrement
from pharos_client.transport import URL_DEFAUT, Session  # noqa: F401

CONSIGNE = ("Tu es l'assistant de l'exploitant du terminal portuaire PHAROS. Nous sommes le mardi "
            "6 octobre 2026, à Paris. Utilise les outils disponibles ; si aucun ne permet de répondre, dis-le.")
CLES_SENSIBLES = ("cle", "key", "token", "secret", "password", "mot_de_passe")


class ArretBoucle(Exception):
    """Arrêt anormal de la boucle : porte toujours la trace complète."""

    def __init__(self, message: str, trace: list[Enregistrement]):
        super().__init__(message)
        self.trace = trace


class BudgetDepasse(ArretBoucle):
    """Budget de tours, ou de tokens, épuisé."""


class EchecNonRecuperable(ArretBoucle):
    """Échec que le modèle ne peut pas corriger : modèle indisponible, serveur injoignable."""


def executer(question: str, *, url: str = URL_DEFAUT, max_tours: int = 8,
             max_tokens: int = 30_000) -> tuple[str, list[Enregistrement]]:
    """Pose la question, laisse le modèle appeler les outils, sait s'arrêter. Rend (réponse, trace)."""
    raise NotImplementedError("LAB 4 — la boucle est à écrire.")
