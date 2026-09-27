"""Agrégation de catalogues (LAB 13) — SQUELETTE : l'ouverture des sessions est fournie ; collisions(), outils(),
serveur_de() et session_de() sont à écrire (étape 1).

    serveurs = lire_config("labs/lab13/serveurs.json")
    with Catalogue(serveurs) as catalogue:
        outils = catalogue.outils()              # le catalogue agrégé, format « function calling »
        session = catalogue.session_de(nom)      # la session du serveur qui expose cet outil
        catalogue.serveur_de(nom)                # « pharos-ops »…, ou None pour un outil inconnu

Une collision de noms (deux serveurs, un même outil) n'est jamais tranchée ici : outils() la refuse, et la
nomme. Le modèle ne voit qu'une liste plate — si deux entrées portent le même nom, la suite dépend du client
(l'une écrase l'autre, ou c'est indéfini) : on préfixe par domaine côté serveur (bloc 21.1).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from pharos_client import entrees

CONFIG = Path("labs/lab13/serveurs.json")


class CollisionDeNoms(Exception):
    """Deux serveurs exposent un même nom d'outil : le catalogue agrégé est ambigu."""


@dataclass(frozen=True)
class Serveur:
    nom: str
    url: str
    jeton: str | None = None


def lire_config(chemin=CONFIG) -> list[Serveur]:
    """labs/lab13/serveurs.json : {"serveurs": [{"nom", "url", "jeton"?}]}, dans l'ordre de présentation."""
    donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    return [Serveur(s["nom"], s["url"], s.get("jeton")) for s in donnees["serveurs"]]


class Catalogue:
    def __init__(self, serveurs: list[Serveur], *, delai_s: float | None = None):
        self.serveurs = list(serveurs)
        self._delai_s = delai_s
        self._sessions: dict[str, entrees.SessionElicitation] = {}
        self._par_serveur: dict[str, list[dict]] = {}

    def __enter__(self) -> "Catalogue":
        try:
            for s in self.serveurs:
                # PHAROS_JETON, s'il est posé, prime sur la configuration : on change d'identité sans la réécrire.
                jeton = os.environ.get("PHAROS_JETON") or s.jeton
                session = entrees.SessionElicitation(s.url, jeton=jeton, delai_s=self._delai_s).__enter__()
                self._sessions[s.nom] = session
                self._par_serveur[s.nom] = session.lister_outils()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc) -> None:
        for session in reversed(list(self._sessions.values())):
            session.__exit__(None, None, None)
        self._sessions.clear()

    def sessions(self) -> dict[str, entrees.SessionElicitation]:
        return dict(self._sessions)

    def outils_par_serveur(self) -> dict[str, list[dict]]:
        return dict(self._par_serveur)

    def collisions(self) -> dict[str, list[str]]:
        """{nom d'outil: [serveurs qui l'exposent]}, pour chaque nom exposé par plus d'un serveur."""
        raise NotImplementedError("Catalogue.collisions : à écrire (LAB 13, étape 1).")

    def outils(self) -> list[dict]:
        """Le catalogue agrégé, liste plate au format « function calling ». Une collision n'est jamais tranchée
        ici : lever CollisionDeNoms, qui la nomme."""
        raise NotImplementedError("Catalogue.outils : à écrire (LAB 13, étape 1).")

    def serveur_de(self, nom: str) -> str | None:
        """Le nom du serveur qui expose cet outil, ou None."""
        raise NotImplementedError("Catalogue.serveur_de : à écrire (LAB 13, étape 1).")

    def session_de(self, nom: str) -> entrees.SessionElicitation:
        """La session du serveur qui expose cet outil (KeyError pour un outil inconnu)."""
        raise NotImplementedError("Catalogue.session_de : à écrire (LAB 13, étape 1).")
