"""Moteur de planification du LAB 11 : sur une base simulée (mocks servis dans le processus), puis sur la vraie."""

import asyncio
from datetime import date, datetime

import httpx
import pytest

from pharos import horloge
from pharos_ops import planification
from tests.aides import base_requise

JEUDI = date(2026, 10, 8)
QUAIS = {1: {"quai": 1, "longueur_m": 220.0, "tirant_eau_max_m": 10.5, "latitude": 48.3812, "longitude": -4.4931},
         3: {"quai": 3, "longueur_m": 300.0, "tirant_eau_max_m": 13.5, "latitude": 48.3799, "longitude": -4.4839},
         4: {"quai": 4, "longueur_m": 340.0, "tirant_eau_max_m": 14.5, "latitude": 48.3791, "longitude": -4.4786}}


def _h(heure: float) -> datetime:
    return datetime(2026, 10, 8, int(heure), int(heure % 1 * 60), tzinfo=horloge.FUSEAU)


def _escale(ident, quai, debut, fin, tirant=8.0, longueur=150.0):
    return {"escale_id": ident, "navire": f"Navire {ident}", "longueur_m": longueur, "quai": quai,
            "debut": _h(debut), "fin": _h(fin), "tirant_eau_m": tirant}


ESCALES = [_escale("E1", 1, 6, 9), _escale("E2", 3, 7, 10, tirant=13.0), _escale("E3", 1, 8, 11),
           _escale("E4", 4, 15, 16)]


def lire(escales=ESCALES):
    async def lire_simule(jour, quais):
        return [e for e in escales if quais is None or e["quai"] in quais], QUAIS
    return lire_simule


@pytest.fixture(autouse=True)
def rapide(monkeypatch, mocks_servis):
    monkeypatch.setenv("PHAROS_VITESSE", "1000")


async def test_journee_progression_a_chaque_escale_et_decisions():
    vus = []
    plan = await planification.recalculer(JEUDI, None, lambda t, n: vus.append((t, n)), lire=lire())
    assert vus == [(1, 4), (2, 4), (3, 4), (4, 4)] and plan.escales == 4
    par_id = {p.escale_id: p for p in plan.placements}
    assert (par_id["E1"].statut, par_id["E1"].quai_propose) == ("maintenue", 1)
    assert (par_id["E2"].statut, par_id["E2"].quai_propose) == ("deplacee", 4)          # 13,0 m > 13,5 − 1,0
    assert "tirant d'eau" in par_id["E2"].motifs[0]
    assert (par_id["E3"].statut, par_id["E3"].quai_propose) == ("deplacee", 3)          # chevauche E1 au quai 1
    assert par_id["E4"].statut == "a_decaler" and "coup de vent" in par_id["E4"].motifs[-1]   # 15 h – 16 h jeudi
    d = plan.en_dict()
    assert d["quais"] == "tous" and d["resume"] == {"maintenue": 1, "deplacee": 2, "a_decaler": 1}
    assert d["placements"][0]["debut"] == "2026-10-08T06:00+02:00"


async def test_un_quai_seul_rappel_asynchrone_et_pas_de_deplacement():
    vus = []

    async def rappel(t, n):
        await asyncio.sleep(0)
        vus.append(f"{t} escales sur {n}")

    plan = await planification.recalculer(JEUDI, [3], rappel, lire=lire())
    assert vus == ["1 escales sur 1"] and plan.en_dict()["quais"] == [3]
    [p] = plan.placements
    assert p.statut == "a_deplacer" and p.quai_propose is None and "journée entière" in p.motifs[-1]


async def test_durees_et_vitesse(monkeypatch):
    monkeypatch.setenv("PHAROS_VITESSE", "rapide")
    assert planification._facteur() == 10.0
    monkeypatch.setenv("PHAROS_VITESSE", "")
    assert planification._facteur() == 1.0
    monkeypatch.setenv("PHAROS_VITESSE", "20")
    debut = asyncio.get_running_loop().time()
    await planification.recalculer(JEUDI, None, None, lire=lire(ESCALES[:2]))
    assert asyncio.get_running_loop().time() - debut >= 2 * 5.0 / 20


async def test_panne_meteo_pendant_le_calcul(mocks_servis):
    vus = []

    def rappel(t, n):
        vus.append(t)
        if t == 2:
            httpx.post(f"{mocks_servis}/_config", json={"panne": "meteo"})

    with pytest.raises(planification.MeteoIndisponible) as exc:
        await planification.recalculer(JEUDI, None, rappel, lire=lire())
    assert vus == [1, 2] and (exc.value.traitees, exc.value.total) == (2, 4)
    assert str(exc.value) == "Météo marine indisponible pendant le recalcul (HTTP 503), après 2 escales sur 4."
    assert "meteo-salle-2026" not in str(exc.value) and exc.value.__cause__ is None


async def test_annulation_en_cours():
    vus = []
    tache = asyncio.create_task(planification.recalculer(JEUDI, None, lambda t, n: vus.append(t),
                                                         lire=lire(ESCALES * 50)))
    while not vus:
        await asyncio.sleep(0.01)
    tache.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tache
    assert len(vus) < 200


@base_requise
async def test_journee_de_jeudi_dans_la_vraie_base(base_de_test, monkeypatch, tmp_path):
    escales, quais = await planification.lire_journee(JEUDI, None)
    assert len(escales) == 24 and sorted(quais) == [1, 2, 3, 4, 5, 6, 7]
    [vent] = [e for e in escales if e["escale_id"] == "ESC-2026-0412"]
    assert (vent["navire"], vent["tirant_eau_m"], vent["quai"]) == ("Vent d'Autan", 12.9, 3)
    assert [e["escale_id"] for e in (await planification.lire_journee(JEUDI, [3]))[0]] == \
        ["ESC-2026-0412", "ESC-2026-0413"]
