"""Moteur de planification à quai (LAB 11) — FOURNI. Lent par construction.

    from pharos_ops.planification import recalculer, MeteoIndisponible
    plan = await recalculer(date(2026, 10, 8), None, rappel_progression)     # la journée, tous les quais
    plan = await recalculer(date(2026, 10, 8), [3], rappel_progression)      # un quai seul
    plan.en_dict()                                                           # sérialisable en JSON

- Lit la base directement, sous le rôle en lecture seule pharos_planification — jamais par un autre serveur
  MCP (un serveur MCP n'en appelle pas un autre).
- Interroge la météo marine par pharos.meteo, escale par escale : une panne en cours de calcul lève
  MeteoIndisponible (message propre : ni URL ni clé), le calcul s'arrête là.
- Appelle rappel_progression(traitees, total) après CHAQUE escale traitée (fonction ordinaire ou coroutine) :
  la progression vient du calcul lui-même, jamais d'un minuteur.
- Durée : 5 s par escale pour la journée (24 escales jeudi : deux minutes), 1 s par escale pour un quai seul.
  PHAROS_VITESSE=rapide divise par dix (itérer), un nombre divise par ce nombre ; la vérification finale se
  fait à vitesse réelle. Annulable à tout moment (asyncio) : le moteur n'écrit rien, rien n'est à défaire.

Pour chaque escale, dans l'ordre des débuts : tirant d'eau contre le maximum du quai moins la marge
(1,0 m, définition 2.0), longueur du navire, chevauchement avec les escales déjà placées sur le quai, vent
sur le créneau (quai fermé au-delà de 30 kt). Une escale qui ne tient plus est déplacée vers un autre quai
compatible (journée seulement), ou marquée à décaler.
"""

from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta

import asyncpg
import httpx

from pharos import base, horloge, meteo

MARGE_TIRANT_EAU_M = 1.0
SEUIL_FERMETURE_KT = 30.0
DUREE_ESCALE_S = {"journee": 5.0, "quai": 1.0}
DELAI_METEO_S = 5.0


class MeteoIndisponible(Exception):
    """La météo est tombée pendant le calcul. Le message ne porte ni URL ni clé ; traitees/total disent où."""

    def __init__(self, raison: str, traitees: int, total: int):
        super().__init__(f"Météo marine indisponible pendant le recalcul ({raison}), après {traitees} escales "
                         f"sur {total}.")
        self.raison, self.traitees, self.total = raison, traitees, total


@dataclass
class Placement:
    escale_id: str
    navire: str
    debut: str
    fin: str
    quai_prevu: int
    quai_propose: int | None
    statut: str                     # maintenue | deplacee | a_deplacer | a_decaler
    vent_max_kt: float | None
    motifs: list[str] = field(default_factory=list)


@dataclass
class Plan:
    date: str
    quais: list[int] | None         # None : la journée, tous les quais
    escales: int
    placements: list[Placement]

    def en_dict(self) -> dict:
        resume: dict[str, int] = {}
        for p in self.placements:
            resume[p.statut] = resume.get(p.statut, 0) + 1
        return {"date": self.date, "quais": self.quais if self.quais is not None else "tous",
                "escales": self.escales, "resume": resume, "placements": [asdict(p) for p in self.placements]}


def _facteur() -> float:
    valeur = os.environ.get("PHAROS_VITESSE", "").strip()
    if valeur == "rapide":
        return 10.0
    try:
        return max(float(valeur), 1.0)
    except ValueError:
        return 1.0


def _jour(jour: date) -> tuple[datetime, datetime]:
    debut = datetime.combine(jour, time(0), horloge.FUSEAU)
    return debut, debut + timedelta(days=1)


async def lire_journee(jour: date, quais: list[int] | None) -> tuple[list[dict], dict[int, dict]]:
    """Escales du jour (non annulées, qui touchent la journée de Paris) et caractéristiques des quais."""
    debut, fin = _jour(jour)
    connexion = await asyncpg.connect(base.dsn("pharos_planification"),
                                      server_settings={"application_name": "pharos-ops-planification"})
    try:
        escales = await connexion.fetch(
            "SELECT e.escale_id, n.nom AS navire, n.longueur_m, e.quai, e.debut, e.fin, e.tirant_eau_m "
            "FROM escales e JOIN navires n USING (navire_id) "
            "WHERE e.statut <> 'annulee' AND e.debut < $2 AND $1 < e.fin ORDER BY e.debut, e.quai, e.escale_id",
            debut, fin)
        lignes = await connexion.fetch("SELECT quai, longueur_m, tirant_eau_max_m, latitude, longitude FROM quais")
    finally:
        await connexion.close()
    nombres = ("longueur_m", "tirant_eau_m", "tirant_eau_max_m", "latitude", "longitude")
    convertir = lambda l: {k: float(v) if k in nombres else v for k, v in dict(l).items()}
    # Filtre des quais en Python, pas en SQL : un paramètre tableau ferait introspecter son type par asyncpg,
    # qui appelle set_config — retiré aux rôles applicatifs (LAB 9).
    return ([convertir(e) for e in escales if quais is None or e["quai"] in quais],
            {l["quai"]: convertir(l) for l in lignes})


def _paris(instant: datetime) -> str:
    return instant.astimezone(horloge.FUSEAU).isoformat(timespec="minutes")


async def _vent_max(quai: dict, debut: datetime, fin: datetime, traitees: int, total: int) -> float | None:
    try:
        brut = await meteo.previsions(quai["latitude"], quai["longitude"], debut, fin, delai_s=DELAI_METEO_S)
    except httpx.TimeoutException:
        raise MeteoIndisponible("délai dépassé", traitees, total) from None
    except httpx.HTTPStatusError as exc:
        raise MeteoIndisponible(f"HTTP {exc.response.status_code}", traitees, total) from None
    except (httpx.HTTPError, RuntimeError, ValueError):
        raise MeteoIndisponible("service injoignable", traitees, total) from None
    vents = [v for v in brut["hourly"]["wind_speed_10m"] if v is not None]
    return max(vents) if vents else None


def _chevauche(e: dict, autres: list[dict]) -> dict | None:
    return next((a for a in autres if a["debut"] < e["fin"] and e["debut"] < a["fin"]), None)


def _tient(e: dict, quai: dict) -> list[str]:
    motifs = []
    limite = quai["tirant_eau_max_m"] - MARGE_TIRANT_EAU_M
    if e["tirant_eau_m"] > limite:
        motifs.append(f"tirant d'eau {e['tirant_eau_m']:.1f} m au-delà de {quai['tirant_eau_max_m']:.1f} − "
                      f"{MARGE_TIRANT_EAU_M:.1f} m (quai {quai['quai']})")
    if e["longueur_m"] > quai["longueur_m"]:
        motifs.append(f"longueur {e['longueur_m']:.0f} m au-delà du quai {quai['quai']} ({quai['longueur_m']:.0f} m)")
    return motifs


async def recalculer(jour: date, quais: list[int] | None, rappel_progression=None, *,
                     lire=lire_journee) -> Plan:
    """Recalcule le plan de placement du jour (quais=None : tous). Voir la documentation du module."""
    escales, caracteristiques = await lire(jour, quais)
    total, duree = len(escales), DUREE_ESCALE_S["journee" if quais is None else "quai"] / _facteur()
    debut_jour, fin_jour = _jour(jour)
    places: dict[int, list[dict]] = {}
    placements = []
    for traitees, e in enumerate(escales, start=1):
        await asyncio.sleep(duree)
        quai = caracteristiques[e["quai"]]
        vent = await _vent_max(quai, max(e["debut"], debut_jour), min(e["fin"], fin_jour), traitees - 1, total)
        motifs = _tient(e, quai)
        conflit = _chevauche(e, places.get(e["quai"], []))
        if conflit:
            motifs.append(f"chevauche {conflit['escale_id']} au quai {e['quai']}")
        if vent is not None and vent >= SEUIL_FERMETURE_KT:
            motifs.append(f"coup de vent sur le créneau ({vent:.0f} kt, quai fermé au-delà de "
                          f"{SEUIL_FERMETURE_KT:.0f} kt)")
            statut, propose = "a_decaler", None
        elif not motifs:
            statut, propose = "maintenue", e["quai"]
        elif quais is not None:
            statut, propose = "a_deplacer", None
            motifs.append("autre quai à chercher : recalculer la journée entière")
        else:
            propose = next((q for q, c in sorted(caracteristiques.items())
                            if not _tient(e, c) and not _chevauche(e, places.get(q, []))), None)
            statut = "deplacee" if propose is not None else "a_decaler"
        if propose is not None:
            places.setdefault(propose, []).append(e)
        placements.append(Placement(e["escale_id"], e["navire"], _paris(e["debut"]), _paris(e["fin"]), e["quai"],
                                    propose, statut, vent, motifs))
        if rappel_progression is not None:
            retour = rappel_progression(traitees, total)
            if inspect.isawaitable(retour):
                await retour
    return Plan(jour.isoformat(), quais, total, placements)
