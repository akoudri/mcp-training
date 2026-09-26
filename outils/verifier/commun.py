"""Cadre des vérificateurs : un critère de réussite du brief = une fonction, dans l'ordre du brief.

✅ vérifié · ❌ à corriger (avec ce qu'il faut faire) · 👁 à constater par vous · ⏭ sauté (sans modèle).
"""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass, field
from enum import Enum

import httpx


class Etat(Enum):
    OK = "✅"
    ECHEC = "❌"
    CONSTAT = "👁"
    SAUTE = "⏭"


class Echec(Exception):
    """Critère non satisfait ; le message dit quoi corriger."""


@dataclass
class Resultat:
    libelle: str
    etat: Etat
    detail: str = ""


@dataclass
class Contexte:
    url: str
    sans_modele: bool
    cache: dict = field(default_factory=dict)


@dataclass
class Rapport:
    titre: str
    resultats: list[Resultat]

    @property
    def code_sortie(self) -> int:
        return 1 if any(r.etat is Etat.ECHEC for r in self.resultats) else 0

    def texte(self) -> str:
        lignes = [self.titre, ""]
        for r in self.resultats:
            lignes.append(f"  {r.etat.value} {r.libelle}")
            lignes += [f"       → {ligne}" for ligne in r.detail.splitlines() if ligne.strip()]
        compte = {e: sum(r.etat is e for r in self.resultats) for e in Etat}
        lignes += ["", "Bilan : " + " · ".join(f"{compte[e]} {e.value}" for e in Etat)]
        return "\n".join(lignes)


@dataclass
class _Critere:
    libelle: str
    fonction: object
    genre: str          # "auto" | "modele" | "constat"


class Verification:
    def __init__(self, titre: str, url: str, demarrage: str):
        self.titre, self.url, self.demarrage = titre, url, demarrage
        self._criteres: list[_Critere] = []

    def critere(self, libelle: str, *, modele: bool = False):
        def decorer(fonction):
            self._criteres.append(_Critere(libelle, fonction, "modele" if modele else "auto"))
            return fonction
        return decorer

    def constat(self, libelle: str):
        def decorer(fonction):
            self._criteres.append(_Critere(libelle, fonction, "constat"))
            return fonction
        return decorer

    async def _panne(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=5) as http:
                r = await http.post(url, json={})
        except httpx.HTTPError as exc:
            return exc.__class__.__name__
        return f"HTTP {r.status_code}" if r.status_code >= 500 else None

    async def executer(self, url: str | None = None, sans_modele: bool | None = None) -> Rapport:
        url = url or self.url
        if sans_modele is None:
            sans_modele = os.environ.get("SANS_MODELE") == "1"
        panne = await self._panne(url)
        if panne:
            return Rapport(self.titre, [Resultat(
                "Le serveur répond à travers l'observateur.", Etat.ECHEC,
                f"{url} ne répond pas ({panne}) : lancer « {self.demarrage} », puis relancer la vérification.")])
        ctx = Contexte(url, sans_modele)
        resultats = []
        for c in self._criteres:
            if c.genre == "modele" and sans_modele:
                resultats.append(Resultat(c.libelle, Etat.SAUTE, "sans modèle (SANS_MODELE=1)"))
                continue
            try:
                valeur = c.fonction(ctx)
                if inspect.isawaitable(valeur):
                    valeur = await valeur
            except Echec as exc:
                resultats.append(Resultat(c.libelle, Etat.ECHEC, str(exc)))
            except Exception as exc:  # un vérificateur ne plante jamais : il dit ce qu'il a vu
                resultats.append(Resultat(c.libelle, Etat.ECHEC,
                                          f"erreur inattendue pendant la vérification : {exc.__class__.__name__}: {exc}"))
            else:
                etat = Etat.CONSTAT if c.genre == "constat" else Etat.OK
                resultats.append(Resultat(c.libelle, etat, valeur or ""))
        return Rapport(self.titre, resultats)
