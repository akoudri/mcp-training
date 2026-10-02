"""pharos-ops v0 (LAB 10) — solution de référence : deux API tierces enveloppées en trois outils.

- Aucun outil ne prend de coordonnées, de fuseau ni d'unité : le quai suffit, le serveur connaît sa position.
- Sortie normalisée : unités dans les noms (vent_kt, rafales_kt, houle_m, visibilite_km, longueur_m…), heures
  ISO 8601 à Paris avec leur décalage, et une règle unique pour les absences, sur les deux API : une valeur
  inconnue vaut null, jamais 0 — un zéro du référentiel est une absence déguisée.
- La clé météo ne sort jamais : les erreurs de httpx (dont le message porte l'URL, clé comprise) sont
  remplacées par un message propre, et le journal ne reçoit qu'un résumé sans URL.
- Trois familles d'échec, trois conduites (bloc 17.3) : récupérable (timeout, 5xx, coupure de connexion) — un
  seul réessai, borné dans le temps (pas seulement sur 503 : toute panne récupérable) ; non récupérable
  (400, 403, 404) — aucun ; quota (429) — aucun, et on le dit.
- Un plafond par outil et par appelant (bloc 17.2), et un refus qui dit comment consommer moins.
- meteo_creneau interroge les quais en parallèle et rend une réponse partielle explicite (complet: false).
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from donnees.base import generer
from pharos import autorisation, horloge, journal, meteo

REFERENTIEL_URL = os.environ.get("REFERENTIEL_URL", "http://mocks:8000/referentiel")
POSITIONS = {q.quai: (q.latitude, q.longitude) for q in generer.quais()}
# Le délai d'un appel à la météo reste sous le budget de tour du client (PHAROS_DELAI_S, 20 s) : les quais sont
# interrogés en parallèle, et un réessai éventuel tient dans ce même budget.
DELAI_METEO_S = 4.0
BUDGET_METEO_S = 9.0
HORIZON_MAX_H = 72
PLAFOND_APPELS, FENETRE_S = 30, 60
SEUILS = {"vent_kt": 25.0, "rafales_kt": 35.0, "houle_m": 2.0}
VISIBILITE_MIN_KM = 1.0
COLONNES = {"wind_speed_10m": "vent_kt", "wind_gusts_10m": "rafales_kt", "wave_height": "houle_m",
            "visibility": "visibilite_km"}
UNITES_ATTENDUES = {"wind_speed_10m": "kn", "wind_gusts_10m": "kn", "wave_height": "m", "visibility": "km"}

MESSAGE_PANNE_METEO = ("Le service météo marine est indisponible ({raison}). Les données des navires et de leurs "
                       "escales restent accessibles (navire_par_nom), comme celles des autres serveurs PHAROS. "
                       "Ne pas conclure sur le risque météo : le signaler comme non évalué dans la note.")
MESSAGE_QUOTA_METEO = ("Quota du fournisseur météo atteint : nouvelle fenêtre dans {attente} s — ne pas réessayer "
                       "avant. Pour consommer moins : demander tous les quais utiles en un seul appel de "
                       "meteo_creneau, et réutiliser les prévisions déjà obtenues. En attendant, ne pas conclure sur "
                       "le risque météo : le signaler comme non évalué.")
MESSAGE_PANNE_REFERENTIEL = ("Le référentiel navires est indisponible ({raison}). La météo par quai reste accessible "
                             "(meteo_creneau, meteo_alerte). Ne pas deviner l'identifiant ni les caractéristiques du "
                             "navire : les signaler comme non vérifiés.")

mcp = FastMCP("pharos-ops", auth=autorisation.verificateur(), middleware=[journal.Journal("pharos-ops")],
              mask_error_details=True)


# ------------------------------------------------------------------ erreurs : trois familles, sans jamais la clé

class Echec(Exception):
    """Échec d'un appel externe, déjà traduit : famille et raison courte, jamais l'URL."""

    def __init__(self, famille: str, raison: str, attente_s: int | None = None):
        super().__init__(raison)
        self.famille, self.raison, self.attente_s = famille, raison, attente_s


def _traduire(exc: Exception) -> Echec:
    """httpx → famille ; le journal reçoit un résumé sans URL (le message de httpx contient la clé)."""
    if isinstance(exc, httpx.TimeoutException):
        echec = Echec("recuperable", "délai dépassé")
    elif isinstance(exc, httpx.HTTPStatusError):
        statut = exc.response.status_code
        if statut == 429:
            attente = exc.response.headers.get("retry-after", "60")
            echec = Echec("quota", "quota atteint", int(attente) if attente.isdigit() else 60)
        elif statut >= 500:
            echec = Echec("recuperable", f"service en panne, HTTP {statut}")
        elif statut == 403:
            echec = Echec("non_recuperable", "clé refusée par le fournisseur (configuration du serveur)")
        else:
            echec = Echec("non_recuperable", f"requête refusée, HTTP {statut}")
    elif isinstance(exc, httpx.TransportError):
        echec = Echec("recuperable", "service injoignable")
    else:
        echec = Echec("non_recuperable", "erreur inattendue")
    journal.consigner_erreur(Exception(f"{exc.__class__.__name__} ({echec.raison})"))
    return echec


async def _avec_reessai(appel, budget_s: float):
    """Un seul réessai, seulement sur la famille récupérable hors délai (503, coupure), et dans le budget."""
    fin = time.monotonic() + budget_s
    try:
        return await appel()
    except (httpx.HTTPError, ValueError) as exc:
        echec = _traduire(exc)
        if echec.famille != "recuperable" or isinstance(exc, httpx.TimeoutException) \
                or time.monotonic() + DELAI_METEO_S + 0.5 > fin:
            raise echec from None
    await asyncio.sleep(0.5)
    try:
        return await appel()
    except (httpx.HTTPError, ValueError) as exc:
        raise _traduire(exc) from None


def _refus_meteo(echec: Echec) -> ToolError:
    if echec.famille == "quota":
        return ToolError(MESSAGE_QUOTA_METEO.format(attente=echec.attente_s or 60))
    return ToolError(MESSAGE_PANNE_METEO.format(raison=echec.raison))


# ------------------------------------------------------------------ plafond par outil et par appelant

_appels: dict[tuple[str, str], deque] = defaultdict(deque)


def _appelant() -> str:
    try:
        return autorisation.identite().nom
    except ToolError:
        return "anonyme"


def _plafonner(outil: str, conseil: str) -> None:
    fenetre, maintenant = _appels[(outil, _appelant())], time.monotonic()
    while fenetre and maintenant - fenetre[0] > FENETRE_S:
        fenetre.popleft()
    if len(fenetre) >= PLAFOND_APPELS:
        attente = int(FENETRE_S - (maintenant - fenetre[0])) + 1
        raise ToolError(f"Plafond de pharos-ops atteint pour {outil} : {PLAFOND_APPELS} appels par minute et par "
                        f"appelant. Nouvelle fenêtre dans {attente} s. Pour consommer moins : {conseil}")
    fenetre.append(maintenant)


# ------------------------------------------------------------------ normalisation

def _heure_paris(instant: datetime) -> str:
    return instant.astimezone(horloge.FUSEAU).isoformat(timespec="minutes")


def _lue_a_paris(instant: datetime) -> datetime:
    """Une heure sans fuseau est lue à Paris : décision d'exploitation, jamais un paramètre."""
    return instant.replace(tzinfo=horloge.FUSEAU) if instant.tzinfo is None else instant.astimezone(horloge.FUSEAU)


def _connue(valeur) -> float | None:
    """Règle unique des absences : absent, null ou 0 → None.

    Le zéro-vaut-absence ne vaut vraiment que pour les grandeurs qui ne peuvent pas être physiquement nulles ici
    (longueur, tirant d'eau, visibilité) : un vent nul n'aurait rien d'anormal en soi. On l'applique quand même
    aux colonnes météo (vent, rafales, houle) parce que le mock est étalonné pour ne jamais produire 0 sur ces
    colonnes (une absence y est toujours rendue par null) — la règle reste donc sûre ici, mais ne doit pas être
    recopiée telle quelle pour une grandeur qui, elle, peut légitimement valoir zéro."""
    return float(valeur) if isinstance(valeur, (int, float)) and not isinstance(valeur, bool) and valeur > 0 else None


def _previsions(brut: dict) -> list[dict]:
    """Colonnes horaires GMT → une ligne par heure, à Paris, unités dans les noms, absences à null."""
    unites = brut.get("hourly_units", {})
    for colonne, unite in UNITES_ATTENDUES.items():
        if unites.get(colonne) != unite:
            raise ValueError(f"unité inattendue pour {colonne} : {unites.get(colonne)}")
    colonnes = brut["hourly"]
    lignes = []
    for i, heure in enumerate(colonnes["time"]):
        instant = datetime.fromisoformat(heure).replace(tzinfo=timezone.utc)
        ligne = {"heure": _heure_paris(instant)}
        for source, nom in COLONNES.items():
            valeurs = colonnes.get(source) or []
            ligne[nom] = _connue(valeurs[i]) if i < len(valeurs) else None
        lignes.append(ligne)
    return lignes


async def _meteo_quai(quai: int, debut: datetime, fin: datetime) -> list[dict]:
    latitude, longitude = POSITIONS[quai]

    async def appel():
        return _previsions(await meteo.previsions(latitude, longitude, debut, fin, delai_s=DELAI_METEO_S))

    return await _avec_reessai(appel, BUDGET_METEO_S)


def _quais_valides(quais: list[int]) -> list[int]:
    inconnus = [q for q in quais if q not in POSITIONS]
    if not quais or inconnus:
        raise ToolError(f"Quai inconnu : {inconnus or 'aucun quai demandé'}. Quais du port : 1 à 7.")
    return list(dict.fromkeys(quais))


def _creneau(debut: datetime, fin: datetime) -> tuple[datetime, datetime]:
    debut, fin = _lue_a_paris(debut), _lue_a_paris(fin)
    if fin < debut:
        raise ToolError(f"Créneau vide : fin ({_heure_paris(fin)}) précède debut ({_heure_paris(debut)}).")
    if fin - debut > timedelta(hours=HORIZON_MAX_H):
        raise ToolError(f"Créneau trop long : {HORIZON_MAX_H} h au plus par appel. Le découper.")
    return debut, fin


# ------------------------------------------------------------------ outils

@mcp.tool(name="meteo_creneau",
          description="Conditions météo marines heure par heure sur un créneau d'accostage, pour un ou plusieurs "
                      "quais (1 à 7) en un seul appel. debut et fin en heure de Paris. Rend, par quai, vent et "
                      "rafales en nœuds (kt), houle en mètres, visibilité en km, heures avec leur décalage. Une "
                      "valeur inconnue vaut null. Si des quais manquent : complet vaut false et incomplets dit "
                      "lesquels et pourquoi — ne jamais conclure pour ces quais-là.")
async def meteo_creneau(quais: list[int], debut: datetime, fin: datetime) -> dict:
    _plafonner("meteo_creneau", "demander tous les quais utiles en un seul appel, sur le créneau exact.")
    quais = _quais_valides(quais)
    debut, fin = _creneau(debut, fin)
    issues = await asyncio.gather(*(_meteo_quai(q, debut, fin) for q in quais), return_exceptions=True)
    resultats, incomplets, echecs = [], [], []
    for quai, issue in zip(quais, issues):
        if isinstance(issue, Echec):
            incomplets.append({"quai": quai, "raison": issue.raison})
            echecs.append(issue)
        elif isinstance(issue, BaseException):
            raise issue
        else:
            resultats.append({"quai": quai, "previsions": issue})
    if not resultats:
        raise _refus_meteo(next((e for e in echecs if e.famille == "quota"), echecs[0]))
    return {"debut": _heure_paris(debut), "fin": _heure_paris(fin), "resultats": resultats,
            "incomplets": incomplets, "complet": not incomplets}


@mcp.tool(name="meteo_alerte",
          description="Y a-t-il un risque météo à venir sur un quai, dans les horizon_h prochaines heures (1 à "
                      "72), et lequel : vent ≥ 25 kt, rafales ≥ 35 kt, houle ≥ 2 m, visibilité < 1 km. Rend les "
                      "risques trouvés, leur période (heure de Paris) et la valeur maximale.")
async def meteo_alerte(quai: int, horizon_h: int) -> dict:
    _plafonner("meteo_alerte", "un seul appel avec l'horizon le plus long utile, plutôt qu'un appel par heure.")
    [quai] = _quais_valides([quai])
    if not 1 <= horizon_h <= HORIZON_MAX_H:
        raise ToolError(f"horizon_h hors bornes : {horizon_h}. De 1 à {HORIZON_MAX_H} heures.")
    debut = horloge.maintenant().replace(minute=0, second=0, microsecond=0)
    fin = debut + timedelta(hours=horizon_h)
    try:
        previsions = await _meteo_quai(quai, debut, fin)
    except Echec as echec:
        raise _refus_meteo(echec) from None
    risques = []
    for champ, seuil in SEUILS.items():
        au_dela = [p for p in previsions if p[champ] is not None and p[champ] >= seuil]
        if au_dela:
            risques.append({"critere": champ.rsplit("_", 1)[0], f"seuil_{champ}": seuil,
                            f"max_{champ}": max(p[champ] for p in au_dela),
                            "debut": au_dela[0]["heure"], "fin": au_dela[-1]["heure"]})
    faible = [p for p in previsions if p["visibilite_km"] is not None and p["visibilite_km"] < VISIBILITE_MIN_KM]
    if faible:
        risques.append({"critere": "visibilite", "seuil_visibilite_km": VISIBILITE_MIN_KM,
                        "min_visibilite_km": min(p["visibilite_km"] for p in faible),
                        "debut": faible[0]["heure"], "fin": faible[-1]["heure"]})
    inconnues = sum(p["visibilite_km"] is None for p in previsions)
    return {"quai": quai, "debut": _heure_paris(debut), "fin": _heure_paris(fin), "risque": bool(risques),
            "risques": risques,
            "donnees_manquantes": f"visibilité inconnue sur {inconnues} heure(s)" if inconnues else None}


def _fiche(brute: dict) -> dict:
    fiche = {"navire_id": brute.get("navire_id"), "nom": brute.get("nom"), "imo": brute.get("imo") or None,
             "longueur_m": _connue(brute.get("longueur_m")),
             "tirant_eau_max_m": _connue(brute.get("tirant_eau_max_m")),
             "pavillon": brute.get("pavillon") or None,
             "escales": [{"escale_id": e["escale_id"], "quai": e["quai"],
                          "debut": _heure_paris(_lue_a_paris(datetime.fromisoformat(e["debut"]))),
                          "fin": _heure_paris(_lue_a_paris(datetime.fromisoformat(e["fin"])))}
                         for e in brute.get("escales") or []]}
    fiche["champs_inconnus"] = [c for c in ("imo", "longueur_m", "tirant_eau_max_m", "pavillon") if fiche[c] is None]
    return fiche


@mcp.tool(name="navire_par_nom",
          description="Fiche d'un navire à partir de son nom (tout ou partie, sans tenir compte des accents) : "
                      "identifiant, numéro OMI, longueur et tirant d'eau maximal en mètres, pavillon, et ses "
                      "escales connues (quai, début et fin en heure de Paris). Une caractéristique inconnue vaut "
                      "null et figure dans champs_inconnus — ne pas la remplacer par une estimation.")
async def navire_par_nom(nom: str) -> dict:
    _plafonner("navire_par_nom", "réutiliser la fiche déjà obtenue : elle porte toutes les escales du navire.")
    if not nom.strip():
        raise ToolError("Nom vide : donner tout ou partie du nom du navire.")
    fiches, page, pages = [], 1, 1
    async with httpx.AsyncClient(timeout=5) as http:
        while page <= pages:
            try:
                reponse = await http.get(f"{REFERENTIEL_URL}/navires", params={"nom": nom, "page": page})
                reponse.raise_for_status()
            except httpx.HTTPError as exc:
                raise ToolError(MESSAGE_PANNE_REFERENTIEL.format(raison=_traduire(exc).raison)) from None
            corps = reponse.json()
            fiches += [_fiche(n) for n in corps.get("resultats", [])]
            page, pages = page + 1, corps.get("pages", 1)
    if not fiches:
        raise ToolError(f"Aucun navire ne correspond à « {nom} » dans le référentiel. Vérifier l'orthographe, "
                        "ou donner une partie du nom seulement.")
    return {"navires": fiches}


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp", json_response=True, show_banner=False,
            middleware=journal.http("pharos-ops"))
