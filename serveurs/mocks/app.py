"""Mocks des systèmes externes (LAB 10 à 14), un seul service : http://mocks:8000 (réseau Compose seulement).

  GET  /meteo/previsions      météo marine, à la manière d'une API publique : position (latitude, longitude),
                              heures en GMT, colonnes horaires, unités à part, clé en paramètre d'URL (apikey)
  GET  /referentiel/navires   référentiel navires (?nom=…&page=…) ; sa documentation ment (docs/api/referentiel.yaml)
  POST /canal/alertes         canal d'alertes : journalise et compte, par destinataire (LAB 12, 14)

Interrupteurs, à chaud, sans redémarrage (make lab10-mocks …) :
  GET|POST /_config   {panne: "meteo"|null, lenteur_s, lenteur_quais, quota} — un POST remplace tout
  POST /_cles         {cle} : accepte une clé de plus (vérificateurs)
  GET  /_compteur     appels reçus par route, alertes par destinataire
  GET  /_journal      alertes reçues, corps compris
  POST /_raz          remet compteurs, journal et fenêtre de quota à zéro (la configuration reste)

Les prévisions sont déterministes (graine : quai et heure) ; jeudi 8 octobre, de 14 h à 18 h (heure de Paris),
un coup de vent balaie le port : 34 kt, rafales 42 kt, houle 2,8 m.
"""

from __future__ import annotations

import asyncio
import math
import os
import random
import re
import time
import unicodedata
from collections import Counter, deque
from datetime import datetime, timedelta, timezone

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from donnees.base import generer
from donnees.referentiel import generer as referentiel
from pharos import horloge

GMT = timezone.utc
HORIZON = (datetime(2026, 9, 1, tzinfo=GMT), datetime(2026, 10, 16, tzinfo=GMT))
MAX_HEURES = 168
VARIABLES = ("wind_speed_10m", "wind_gusts_10m", "wave_height", "visibility")
UNITES = {"time": "iso8601", "wind_speed_10m": "kn", "wind_gusts_10m": "kn", "wave_height": "m", "visibility": "km"}
COUP_DE_VENT = (datetime(2026, 10, 8, 14, tzinfo=horloge.FUSEAU), datetime(2026, 10, 8, 18, tzinfo=horloge.FUSEAU))
PAR_PAGE = 10
DEFAUTS = {"panne": None, "lenteur_s": 0.0, "lenteur_quais": [5, 7], "quota": None}
QUAIS = generer.quais()


class Etat:
    def __init__(self):
        self.config = dict(DEFAUTS)
        self.cles = {os.environ.get("METEO_CLE", "meteo-salle-2026")}
        self.raz()

    def raz(self) -> None:
        self.compteur: Counter = Counter()
        self.alertes: list[dict] = []
        self.fenetre: deque[float] = deque()


etat = Etat()


def _compter(requete: Request) -> None:
    etat.compteur[f"{requete.method} {requete.url.path}"] += 1


# ------------------------------------------------------------------ météo marine

def _heure(texte: str | None, nom: str) -> datetime:
    if not texte:
        raise ValueError(f"Parameter '{nom}' is required (format YYYY-MM-DDTHH:MM, GMT)")
    try:
        instant = datetime.fromisoformat(texte)
    except ValueError:
        raise ValueError(f"Parameter '{nom}' is not a valid ISO 8601 hour: {texte}") from None
    instant = instant.replace(tzinfo=GMT) if instant.tzinfo is None else instant.astimezone(GMT)
    return instant.replace(minute=0, second=0, microsecond=0)


def quai_le_plus_proche(latitude: float, longitude: float) -> int:
    return min(QUAIS, key=lambda q: math.hypot(q.latitude - latitude, q.longitude - longitude)).quai


def prevision(quai: int, instant: datetime) -> dict:
    """Une heure de prévision (instant en GMT, à l'heure pile) : vent, rafales, houle, visibilité (parfois absente)."""
    alea = random.Random(f"{quai}-{instant:%Y%m%d%H}")
    vent = round(alea.uniform(6, 18), 1)
    valeurs = {"wind_speed_10m": vent, "wind_gusts_10m": round(vent + alea.uniform(4, 10), 1),
               "wave_height": round(alea.uniform(0.4, 1.6), 1),
               "visibility": None if alea.random() < 0.08 else round(alea.uniform(4, 15), 1)}
    if COUP_DE_VENT[0] <= instant < COUP_DE_VENT[1]:
        valeurs.update(wind_speed_10m=34.0, wind_gusts_10m=42.0, wave_height=2.8)
    return valeurs


def _erreur(statut: int, raison: str, **entetes) -> JSONResponse:
    return JSONResponse({"error": True, "reason": raison}, status_code=statut, headers=entetes or None)


async def meteo(requete: Request):
    _compter(requete)
    p = requete.query_params
    if p.get("apikey") not in etat.cles:
        return _erreur(403, "Invalid or missing API key")
    if etat.config["panne"] == "meteo":
        return PlainTextResponse("Service Unavailable", status_code=503)
    quota = etat.config["quota"]
    if quota:
        maintenant = time.monotonic()
        while etat.fenetre and maintenant - etat.fenetre[0] > 60:
            etat.fenetre.popleft()
        if len(etat.fenetre) >= quota:
            return _erreur(429, f"Rate limit exceeded: {quota} requests per minute", **{"Retry-After": "60"})
        etat.fenetre.append(maintenant)
    try:
        latitude, longitude = float(p["latitude"]), float(p["longitude"])
        debut, fin = _heure(p.get("start_hour"), "start_hour"), _heure(p.get("end_hour"), "end_hour")
    except KeyError as exc:
        return _erreur(400, f"Parameter '{exc.args[0]}' is required")
    except ValueError as exc:
        return _erreur(400, str(exc))
    if fin < debut:
        return _erreur(400, "Parameter 'end_hour' must not be before 'start_hour'")
    if debut < HORIZON[0] or fin >= HORIZON[1]:
        return _erreur(400, f"Requested hours are outside the forecast range "
                            f"{HORIZON[0]:%Y-%m-%d} to {HORIZON[1] - timedelta(hours=1):%Y-%m-%dT%H:%M}")
    if (fin - debut) > timedelta(hours=MAX_HEURES):
        return _erreur(400, f"At most {MAX_HEURES} hourly steps per request")
    quai = quai_le_plus_proche(latitude, longitude)
    if etat.config["lenteur_s"] and quai in etat.config["lenteur_quais"]:
        await asyncio.sleep(etat.config["lenteur_s"])
    heures = [debut + timedelta(hours=i) for i in range(int((fin - debut).total_seconds() // 3600) + 1)]
    lignes = [prevision(quai, h) for h in heures]
    return JSONResponse({
        "latitude": latitude, "longitude": longitude, "generationtime_ms": 0.4, "utc_offset_seconds": 0,
        "timezone": "GMT", "hourly_units": UNITES,
        "hourly": {"time": [h.strftime("%Y-%m-%dT%H:%M") for h in heures],
                   **{v: [ligne[v] for ligne in lignes] for v in VARIABLES}}})


# ------------------------------------------------------------------ référentiel navires

NAVIRES = referentiel.charger()


def _cle_nom(texte: str) -> str:
    mots = re.sub(r"[\W_]+", " ", texte.casefold())
    return unicodedata.normalize("NFKD", mots).encode("ascii", "ignore").decode().strip()


async def navires(requete: Request):
    _compter(requete)
    if etat.config["panne"] == "referentiel":
        return PlainTextResponse("Service Unavailable", status_code=503)
    nom = requete.query_params.get("nom", "")
    try:
        page = int(requete.query_params.get("page", "1"))
    except ValueError:
        return _erreur(400, "page must be an integer")
    trouves = [n for n in NAVIRES if _cle_nom(nom) in _cle_nom(n["nom"])] if nom.strip() else NAVIRES
    pages = max(1, math.ceil(len(trouves) / PAR_PAGE))
    return JSONResponse({"version": "2026.09.3", "page": page, "pages": pages, "total": len(trouves),
                         "resultats": trouves[(page - 1) * PAR_PAGE:page * PAR_PAGE]})


# ------------------------------------------------------------------ canal d'alertes

async def alertes(requete: Request):
    _compter(requete)
    try:
        corps = await requete.json()
    except ValueError:
        return _erreur(400, "corps JSON attendu")
    manquants = [c for c in ("escale_id", "niveau", "destinataire") if not corps.get(c)]
    if manquants:
        return _erreur(400, f"champs obligatoires manquants : {', '.join(manquants)}")
    alerte = {"alerte_id": f"ALR-{len(etat.alertes) + 1:04d}",
              "recue": horloge.maintenant().isoformat(timespec="seconds"),
              **{c: corps.get(c) for c in ("escale_id", "niveau", "destinataire", "note")}}
    etat.alertes.append(alerte)
    return JSONResponse({"alerte_id": alerte["alerte_id"], "recue": alerte["recue"]}, status_code=201)


# ------------------------------------------------------------------ interrupteurs

async def config(requete: Request):
    if requete.method == "POST":
        corps = await requete.json()
        inconnus = set(corps) - set(DEFAUTS)
        if inconnus:
            return _erreur(400, f"réglages inconnus : {', '.join(sorted(inconnus))}")
        if corps.get("panne") not in (None, "meteo", "referentiel"):
            return _erreur(400, "panne : meteo, referentiel ou null")
        etat.config = {**DEFAUTS, **{k: v for k, v in corps.items() if v is not None}}
        etat.config["lenteur_s"] = float(etat.config["lenteur_s"])
        etat.config["lenteur_quais"] = [int(q) for q in etat.config["lenteur_quais"]]
        etat.fenetre.clear()
    return JSONResponse(etat.config)


async def cles(requete: Request):
    cle = (await requete.json()).get("cle")
    if not cle:
        return _erreur(400, "cle attendue")
    etat.cles.add(cle)
    return JSONResponse({"cles": len(etat.cles)})


async def compteur(requete: Request):
    return JSONResponse({"routes": dict(etat.compteur),
                         "alertes": dict(Counter(a["destinataire"] for a in etat.alertes))})


async def journal(requete: Request):
    return JSONResponse({"alertes": etat.alertes})


async def raz(requete: Request):
    etat.raz()
    return JSONResponse({"raz": True})


async def sante(requete: Request):
    return JSONResponse({"ok": True})


app = Starlette(routes=[
    Route("/meteo/previsions", meteo),
    Route("/referentiel/navires", navires),
    Route("/canal/alertes", alertes, methods=["POST"]),
    Route("/_config", config, methods=["GET", "POST"]),
    Route("/_cles", cles, methods=["POST"]),
    Route("/_compteur", compteur),
    Route("/_journal", journal),
    Route("/_raz", raz, methods=["POST"]),
    Route("/_sante", sante),
])
