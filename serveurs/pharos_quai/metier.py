"""Métier de pharos-quai : correct, et séparé du catalogue.

Le LAB 6 ne réécrit que serveur.py (noms et descriptions) ; ce module ne change pas.
Les erreurs sont des erreurs métier (ToolError) dont le message dit quoi faire.
"""

from __future__ import annotations

from datetime import date, time
from functools import lru_cache
from pathlib import Path

import yaml
from fastmcp.exceptions import ToolError

from donnees import corpus

DOSSIER = Path(__file__).resolve().parents[2] / "donnees" / "quai"


@lru_cache(maxsize=1)
def _quais() -> dict:
    return yaml.safe_load((DOSSIER / "quais.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _planning() -> dict:
    return yaml.safe_load((DOSSIER / "creneaux.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _escales() -> tuple[corpus.Escale, ...]:
    return tuple(corpus.charger().escales)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _quai(numero: int) -> dict:
    for q in _quais()["quais"]:
        if q["quai"] == numero:
            return q
    raise ToolError(f"Quai inconnu : {numero}. Le terminal compte les quais 1 à 4.")


def _normaliser(nom: str) -> str:
    s = nom.replace("'", "'").strip().casefold()
    for article in ("le ", "la ", "l'"):
        if s.startswith(article):
            return s[len(article):].strip()
    return s


def _navire(nom: str) -> str:
    """Nom canonique du navire (« le vent d'autan » → « Vent d'Autan »)."""
    connus = {_normaliser(e.navire): e.navire for e in _escales()}
    try:
        return connus[_normaliser(nom)]
    except KeyError:
        raise ToolError(f"Navire inconnu : « {nom} ». Navires connus : {', '.join(sorted(set(connus.values())))}.") from None


def _jour(jour: date) -> dict:
    creneaux = _planning()["creneaux"]
    if jour.isoformat() not in creneaux:
        raise ToolError(f"Pas de planning de créneaux pour le {jour.isoformat()} : il couvre du "
                        f"{min(creneaux)} au {max(creneaux)}.")
    return creneaux[jour.isoformat()]


def _escale(e: corpus.Escale) -> dict:
    return {"escale_id": e.escale_id, "navire": e.navire, "quai": e.quai,
            "debut": e.debut.isoformat(), "fin": e.fin.isoformat()}


def _navire_de(escale_id: str | None) -> str | None:
    return next((e.navire for e in _escales() if e.escale_id == escale_id), None)


def escales_du_jour(jour: date) -> dict:
    """Escales dont l'intervalle [début, fin] touche la date, tous quais confondus."""
    return {"date": jour.isoformat(),
            "escales": [_escale(e) for e in _escales() if e.debut.date() <= jour <= e.fin.date()]}


def escales_du_quai(jour: date, quai: int) -> dict:
    _quai(quai)
    toutes = escales_du_jour(jour)["escales"]
    return {"date": jour.isoformat(), "quai": quai, "escales": [e for e in toutes if e["quai"] == quai]}


def caracteristiques_quai(quai: int) -> dict:
    return dict(_quai(quai))


def _reserves(navire: str, jour: date) -> list[dict]:
    """Créneaux réservés au navire ce jour-là, créneaux contigus d'un même quai fusionnés."""
    fusion: list[dict] = []
    for quai, lignes in sorted(_jour(jour).items()):
        for c in lignes:
            if _navire_de(c["escale_id"]) != navire:
                continue
            if fusion and fusion[-1]["quai"] == quai and fusion[-1]["fin"] == c["debut"]:
                fusion[-1]["fin"] = c["fin"]
            else:
                fusion.append({"quai": quai, "debut": c["debut"], "fin": c["fin"], "escale_id": c["escale_id"]})
    return fusion


def creneaux_du_navire(nom: str, jour: date) -> dict:
    navire = _navire(nom)
    return {"navire": navire, "date": jour.isoformat(), "creneaux": _reserves(navire, jour)}


def disponibilite(quai: int, jour: date, heure: time) -> dict:
    _quai(quai)
    minute = heure.hour * 60 + heure.minute
    for c in _jour(jour)[quai]:
        if _minutes(c["debut"]) <= minute < _minutes(c["fin"]):
            return {"quai": quai, "date": jour.isoformat(), "creneau": {"debut": c["debut"], "fin": c["fin"]},
                    "libre": c["escale_id"] is None, "escale_id": c["escale_id"],
                    "navire": _navire_de(c["escale_id"])}
    raise AssertionError("un créneau couvre chaque minute de la journée")  # garanti par creneaux.yaml


def heure_accostage(nom: str, jour: date) -> dict:
    """Première heure d'accostage possible : créneaux réservés au navire ce jour-là (sinon créneaux libres
    d'un quai assez profond), réduits aux fenêtres de pleine mer si le tirant d'eau dépasse le seuil."""
    navire = _navire(nom)
    tirant = max(e.tirant_eau_m for e in _escales() if e.navire == navire)
    reserves = _reserves(navire, jour)
    if reserves:
        candidats = [(r["quai"], _minutes(r["debut"]), _minutes(r["fin"])) for r in reserves]
    else:
        profonds = [q["quai"] for q in _quais()["quais"] if q["tirant_eau_max_m"] >= tirant]
        candidats = [(q, _minutes(c["debut"]), _minutes(c["fin"]))
                     for q in profonds for c in _jour(jour)[q] if c["escale_id"] is None]
    maree = tirant > _quais()["maree"]["seuil_tirant_eau_m"]
    if maree:
        fenetres = [(_minutes(d), _minutes(f)) for d, f in _planning()["marees"][jour.isoformat()]]
        candidats = [(q, max(d, fd), min(f, ff)) for q, d, f in candidats for fd, ff in fenetres
                     if max(d, fd) < min(f, ff)]
    reponse = {"navire": navire, "date": jour.isoformat(), "tirant_eau_m": tirant, "maree_requise": maree}
    if not candidats:
        return {**reponse, "heure": None, "motif": "aucun créneau compatible ce jour-là (quai, réservation, marée)"}
    quai, debut, fin = min(candidats, key=lambda c: (c[1], c[0]))
    return {**reponse, "heure": _hhmm(debut), "quai": quai, "jusqu_a": _hhmm(fin),
            "reserve": bool(reserves)}
