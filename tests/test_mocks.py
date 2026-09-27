"""Mocks des systèmes externes (LAB 10 à 14) : météo, référentiel, canal, interrupteurs à chaud ; client pharos.meteo."""

import asyncio
import time
from datetime import datetime

import httpx
import pytest
from starlette.testclient import TestClient

from donnees.base import generer
from donnees.referentiel import generer as referentiel
from outils.servir import servir
from pharos import horloge, meteo
from serveurs.mocks import app as mocks

CLE = "meteo-salle-2026"
QUAI3 = next(q for q in generer.quais() if q.quai == 3)
JEUDI = {"latitude": QUAI3.latitude, "longitude": QUAI3.longitude, "start_hour": "2026-10-08T04:00",
         "end_hour": "2026-10-08T17:00", "apikey": CLE}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mocks, "etat", mocks.Etat())
    with TestClient(mocks.app) as c:
        yield c


def test_previsions_brutes_et_coup_de_vent_de_jeudi(client):
    r = client.get("/meteo/previsions", params=JEUDI)
    assert r.status_code == 200
    corps = r.json()
    assert corps["timezone"] == "GMT" and corps["hourly_units"]["wind_speed_10m"] == "kn"
    heures = corps["hourly"]["time"]
    assert heures[0] == "2026-10-08T04:00" and len(heures) == 14             # bornes incluses, GMT sans fuseau
    vent = dict(zip(heures, corps["hourly"]["wind_speed_10m"]))
    rafales = dict(zip(heures, corps["hourly"]["wind_gusts_10m"]))
    houle = dict(zip(heures, corps["hourly"]["wave_height"]))
    # 14 h – 18 h à Paris = 12 h – 16 h GMT
    assert [vent[f"2026-10-08T{h}:00"] for h in (12, 13, 14, 15)] == [34.0] * 4
    assert rafales["2026-10-08T12:00"] == 42.0 and houle["2026-10-08T15:00"] == 2.8
    assert vent["2026-10-08T11:00"] < 25 and vent["2026-10-08T16:00"] < 25
    assert client.get("/meteo/previsions", params=JEUDI).json() == corps      # déterministe


def test_visibilite_parfois_absente(client):
    semaine = {**JEUDI, "start_hour": "2026-10-05T00:00", "end_hour": "2026-10-11T23:00"}
    visibilite = client.get("/meteo/previsions", params=semaine).json()["hourly"]["visibility"]
    assert None in visibilite and any(v is not None for v in visibilite)


def test_la_position_designe_le_quai(client):
    assert {mocks.quai_le_plus_proche(q.latitude, q.longitude) for q in generer.quais()} == {1, 2, 3, 4, 5, 6, 7}


@pytest.mark.parametrize("parametres, statut", [
    ({**JEUDI, "apikey": "fausse"}, 403),
    ({k: v for k, v in JEUDI.items() if k != "apikey"}, 403),
    ({k: v for k, v in JEUDI.items() if k != "latitude"}, 400),
    ({**JEUDI, "start_hour": "jeudi"}, 400),
    ({**JEUDI, "start_hour": "2026-10-20T00:00", "end_hour": "2026-10-20T03:00"}, 400),
    ({**JEUDI, "start_hour": "2026-10-01T00:00", "end_hour": "2026-10-09T00:00"}, 400),
])
def test_erreurs(client, parametres, statut):
    assert client.get("/meteo/previsions", params=parametres).status_code == statut


def test_panne_quota_et_compteur(client):
    client.post("/_config", json={"panne": "meteo"})
    assert client.get("/meteo/previsions", params=JEUDI).status_code == 503
    client.post("/_config", json={"quota": 2})                               # nominal, quota 2
    codes = [client.get("/meteo/previsions", params=JEUDI).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    r = client.get("/meteo/previsions", params=JEUDI)
    assert r.headers["retry-after"] == "60"
    assert client.get("/_compteur").json()["routes"] == {"GET /meteo/previsions": 5}
    client.post("/_config", json={})
    assert client.get("/meteo/previsions", params=JEUDI).status_code == 200
    client.post("/_raz")
    assert client.get("/_compteur").json() == {"routes": {}, "alertes": {}}
    assert client.get("/_config").json() == mocks.DEFAUTS


def test_lenteur_sur_les_quais_choisis(client):
    client.post("/_config", json={"lenteur_s": 0.3})                          # quais 5 et 7 par défaut
    quai = {q.quai: q for q in generer.quais()}
    for numero, lent in ((3, False), (5, True), (7, True)):
        debut = time.monotonic()
        client.get("/meteo/previsions", params={**JEUDI, "latitude": quai[numero].latitude,
                                                 "longitude": quai[numero].longitude})
        assert (time.monotonic() - debut >= 0.3) is lent
    client.post("/_config", json={"lenteur_s": 0.3, "lenteur_quais": [3]})
    debut = time.monotonic()
    client.get("/meteo/previsions", params=JEUDI)
    assert time.monotonic() - debut >= 0.3


def test_cle_supplementaire(client):
    assert client.get("/meteo/previsions", params={**JEUDI, "apikey": "verif-123"}).status_code == 403
    client.post("/_cles", json={"cle": "verif-123"})
    assert client.get("/meteo/previsions", params={**JEUDI, "apikey": "verif-123"}).status_code == 200
    assert client.get("/meteo/previsions", params=JEUDI).status_code == 200


def test_config_refusee(client):
    assert client.post("/_config", json={"panne": "tout"}).status_code == 400
    assert client.post("/_config", json={"vitesse": 2}).status_code == 400


def test_referentiel_recherche_tolerante(client):
    for nom in ("Vent d'Autan", "vent d’autan", "VENT D AUTAN", "autan"):
        corps = client.get("/referentiel/navires", params={"nom": nom}).json()
        assert [n["navire_id"] for n in corps["resultats"]] == ["NAV-0007"], nom
    [fiche] = corps["resultats"]
    assert [e["escale_id"] for e in fiche["escales"]] == ["ESC-2026-0412"]
    assert fiche["escales"][0]["debut"] == "2026-10-08T06:00"                # heure locale, sans fuseau
    assert client.get("/referentiel/navires", params={"nom": "Titanic"}).json()["resultats"] == []
    tout = client.get("/referentiel/navires").json()
    assert (tout["total"], tout["pages"], len(tout["resultats"])) == (32, 4, 10)


def test_referentiel_ment_comme_annonce(client):
    fiches = {n["nom"]: n for p in (1, 2, 3, 4)
              for n in client.get("/referentiel/navires", params={"page": p}).json()["resultats"]}
    assert "longueur_m" not in fiches["Macareux"]
    assert fiches["Glénan"]["longueur_m"] is None
    assert fiches["Molène"]["longueur_m"] == 0 and fiches["Molène"]["tirant_eau_max_m"] == 0


def test_canal(client):
    assert client.post("/canal/alertes", json={"escale_id": "ESC-2026-0412"}).status_code == 400
    for destinataire in ("exploitation", "exploitation", "externe@exemple.invalid"):
        r = client.post("/canal/alertes", json={"escale_id": "ESC-2026-0412", "niveau": "orange",
                                                "destinataire": destinataire, "note": "vent"})
        assert r.status_code == 201
    assert client.get("/_compteur").json()["alertes"] == {"exploitation": 2, "externe@exemple.invalid": 1}
    [premiere, *_] = client.get("/_journal").json()["alertes"]
    assert premiere["alerte_id"] == "ALR-0001" and premiere["note"] == "vent"
    assert premiere["recue"].startswith(horloge.aujourdhui().isoformat())
    client.post("/_raz")
    assert client.get("/_journal").json() == {"alertes": []}


def test_referentiel_fichier_a_jour():
    assert referentiel.FICHIER.read_text(encoding="utf-8") == referentiel.rendre(), \
        "donnees/referentiel/navires.yaml est périmé : python -m donnees.referentiel"


def _minute(instant: datetime) -> datetime:
    return instant.astimezone(generer.FUSEAU).replace(second=0, microsecond=0)


def test_referentiel_egal_a_la_base_hors_menteurs():
    d = generer.generer()
    fiches = {f["navire_id"]: f for f in referentiel.charger()}
    assert len(fiches) == len(d.navires)
    for n in d.navires:
        f = fiches[n.navire_id]
        assert (f["nom"], f["imo"], f["pavillon"]) == (n.nom, n.imo, n.pavillon)
        menteur = referentiel.MENTEURS.get(n.nom, {})
        for champ in ("longueur_m", "tirant_eau_max_m"):
            if champ not in menteur:
                assert f[champ] == getattr(n, champ)
        escales = [(e.escale_id, e.quai, _minute(e.debut), _minute(e.fin)) for e in d.escales
                   if e.navire_id == n.navire_id and e.statut != "annulee"]
        assert sorted(escales) == sorted((e["escale_id"], e["quai"],
                                          datetime.fromisoformat(e["debut"]).replace(tzinfo=generer.FUSEAU),
                                          datetime.fromisoformat(e["fin"]).replace(tzinfo=generer.FUSEAU))
                                         for e in f["escales"])
    assert "Vent d'Autan" not in referentiel.MENTEURS


# ------------------------------------------------------------------ pharos.meteo, contre le mock servi

@pytest.fixture
def url_meteo(monkeypatch):
    monkeypatch.setattr(mocks, "etat", mocks.Etat())
    with servir(mocks.app) as url:
        monkeypatch.setenv("METEO_URL", f"{url}/meteo")
        monkeypatch.setenv("METEO_CLE", CLE)
        yield url


async def test_client_meteo_brut(url_meteo):
    debut = datetime(2026, 10, 8, 14, tzinfo=horloge.FUSEAU)
    brut = await meteo.previsions(QUAI3.latitude, QUAI3.longitude, debut, datetime(2026, 10, 8, 17, tzinfo=horloge.FUSEAU))
    assert brut["hourly"]["time"] == ["2026-10-08T12:00", "2026-10-08T13:00", "2026-10-08T14:00", "2026-10-08T15:00"]
    assert brut["hourly"]["wind_speed_10m"] == [34.0] * 4


async def test_client_meteo_heure_sans_fuseau_refusee(url_meteo):
    with pytest.raises(ValueError, match="sans fuseau"):
        await meteo.previsions(QUAI3.latitude, QUAI3.longitude, datetime(2026, 10, 8, 14), datetime(2026, 10, 8, 17))


async def test_le_piege_de_la_cle_est_reel(url_meteo):
    """En panne, l'exception de httpx porte l'URL complète — clé comprise (bloc 17.1)."""
    httpx.post(f"{url_meteo}/_config", json={"panne": "meteo"})
    debut = datetime(2026, 10, 8, 14, tzinfo=horloge.FUSEAU)
    with pytest.raises(httpx.HTTPStatusError) as exc:
        await meteo.previsions(QUAI3.latitude, QUAI3.longitude, debut, debut)
    assert exc.value.response.status_code == 503 and CLE in str(exc.value)


async def test_client_meteo_delai(url_meteo):
    httpx.post(f"{url_meteo}/_config", json={"lenteur_s": 2, "lenteur_quais": [3]})
    debut = datetime(2026, 10, 8, 14, tzinfo=horloge.FUSEAU)
    with pytest.raises(httpx.TimeoutException):
        await meteo.previsions(QUAI3.latitude, QUAI3.longitude, debut, debut, delai_s=0.5)
    await asyncio.sleep(0)


async def test_client_meteo_sans_cle(url_meteo, monkeypatch):
    monkeypatch.delenv("METEO_CLE")
    debut = datetime(2026, 10, 8, 14, tzinfo=horloge.FUSEAU)
    with pytest.raises(RuntimeError, match="METEO_CLE"):
        await meteo.previsions(QUAI3.latitude, QUAI3.longitude, debut, debut)
