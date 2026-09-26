"""Code métier de pharos-legacy : escales et mouvements de conteneurs.

Séparé du protocole exprès : le LAB 2 réécrit le protocole sans toucher à ce fichier, et le
LAB 3 exige que la lecture des mouvements n'existe qu'ici, une seule fois.
"""

from __future__ import annotations

import math
from functools import cache

import yaml

from donnees import corpus
from donnees.legacy.mouvements import FICHIER
from pharos import horloge

TAILLE_PAGE = 20


class EscaleInconnue(LookupError):
    """Aucune escale ne porte cet identifiant."""


class PageHorsLimites(ValueError):
    """La page demandée n'existe pas pour cette escale."""


@cache
def _escales() -> dict[str, corpus.Escale]:
    return {e.escale_id: e for e in corpus.charger().escales}


@cache
def lire_mouvements(escale_id: str) -> tuple[dict, ...]:
    """Les mouvements de conteneurs d'une escale, dans l'ordre chronologique."""
    if escale_id not in _escales():
        raise EscaleInconnue(escale_id)
    tous = yaml.safe_load(FICHIER.read_text(encoding="utf-8"))["mouvements"]
    return tuple(tous.get(escale_id) or ())


def etat_escale(escale_id: str) -> dict:
    """Quai, créneau, tirant d'eau et statut (à l'heure fictive de PHAROS)."""
    e = _escales().get(escale_id)
    if e is None:
        raise EscaleInconnue(escale_id)
    maintenant = horloge.maintenant()
    statut = "prévue" if maintenant < e.debut else "à quai" if maintenant < e.fin else "partie"
    return {"escale_id": e.escale_id, "navire": e.navire, "quai": e.quai,
            "creneau": {"debut": e.debut.isoformat(), "fin": e.fin.isoformat()},
            "tirant_eau_m": e.tirant_eau_m, "statut": statut}


def page_de_mouvements(escale_id: str, numero: int) -> dict:
    """La page « numero » (à partir de 1) des mouvements d'une escale."""
    mouvements = lire_mouvements(escale_id)
    pages = max(1, math.ceil(len(mouvements) / TAILLE_PAGE))
    if not 1 <= numero <= pages:
        raise PageHorsLimites(f"page {numero} hors limites (1 à {pages})")
    debut = (numero - 1) * TAILLE_PAGE
    return {"escale_id": escale_id, "page": numero, "pages": pages, "total": len(mouvements),
            "mouvements": list(mouvements[debut:debut + TAILLE_PAGE])}
