"""Vérificateur du LAB 10 : sur un serveur jouet dont on active les défauts un par un, sur le gabarit, et sur la
note du critère décisif. Les mocks sont servis dans le processus de test ; aucun modèle."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from outils.construire_etats import superposer
from outils.verifier.commun import Etat
from pharos import horloge, journal, meteo
from serveurs.mocks import app as mocks
from tests.aides import charger_module, client_minimal, importer_client, servir

POSITIONS = {q.quai: (q.latitude, q.longitude) for q in mocks.QUAIS}
NOTE_OK = """# LAB 10 — note produite en mode panne

## Note de l'agent

L'escale ESC-2026-0412 du Vent d'Autan (quai 3, jeudi 6 h – 20 h) : tirant d'eau 13,2 m. Météo non évaluée :
aucun risque météo ne peut être conclu tant que le service n'est pas rétabli.

## Trace

| Tour | Outil | Arguments | Erreur | Résultat (début) |
|---|---|---|---|---|
| 1 | navire_par_nom | {'nom': "Vent d'Autan"} | non | {"navires": […]} |
| 2 | meteo_creneau | {'quais': [3]} | oui | Le service météo marine est indisponible… |
"""


def jouet(*, fuite=False, journal_brut=False, cause=False, zero=False, zero_meteo=False, sans_fuseau=False,
          sequentiel=False, quatre=False, latitude=False, refus_nu=False) -> FastMCP:
    mcp = FastMCP("jouet", middleware=[journal.Journal("pharos-ops")])

    def nombre(valeur, meteo=False):
        if zero or (zero_meteo and meteo):
            return valeur or 0
        return valeur if isinstance(valeur, (int, float)) and valeur > 0 else None

    def heure(texte: str, gmt: bool) -> str:
        instant = datetime.fromisoformat(texte).replace(tzinfo=timezone.utc if gmt else horloge.FUSEAU)
        return texte if sans_fuseau else instant.astimezone(horloge.FUSEAU).isoformat(timespec="minutes")

    async def previsions(quai, debut, fin, delai=0.5):
        try:
            brut = await meteo.previsions(*POSITIONS[quai], debut, fin, delai_s=delai)
        except httpx.HTTPError as exc:
            if journal_brut:
                journal.consigner_erreur(exc)
            if fuite:
                raise ToolError(f"Erreur météo : {exc}") from None
            if cause:
                raise ToolError("Le service météo est indisponible. Ne pas conclure sur la météo.") from exc
            if refus_nu and isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                raise ToolError("HTTP 429 Too Many Requests") from None
            raise ToolError("Le service météo est indisponible. Les navires restent accessibles. Ne pas conclure "
                            "sur la météo : la signaler comme non évaluée ; pour consommer moins, grouper les quais.") \
                from None
        h = brut["hourly"]
        return [{"heure": heure(t, True), "vent_kt": v, "houle_m": w, "visibilite_km": nombre(s, meteo=True)}
                for t, v, w, s in zip(h["time"], h["wind_speed_10m"], h["wave_height"], h["visibility"])]

    def paris(texte: str) -> datetime:
        return datetime.fromisoformat(texte).replace(tzinfo=horloge.FUSEAU)

    @mcp.tool
    async def meteo_creneau(quais: list[int], debut: str, fin: str) -> dict:
        """Météo sur un créneau."""
        resultats, incomplets = [], []
        for q in quais:
            try:
                resultats.append({"quai": q, "previsions": await previsions(q, paris(debut), paris(fin))})
            except ToolError as exc:
                if sequentiel:
                    raise
                incomplets.append({"quai": q, "raison": str(exc)[:40]})
        if not resultats:
            raise ToolError(incomplets[0]["raison"] + " Ne pas conclure sur la météo : la signaler comme non évaluée.")
        return {"resultats": resultats, "incomplets": incomplets, "complet": not incomplets}

    @mcp.tool
    async def meteo_alerte(quai: int, horizon_h: int) -> dict:
        """Risque à venir."""
        debut = horloge.maintenant().replace(minute=0, second=0, microsecond=0)
        lignes = await previsions(quai, debut, debut + timedelta(hours=horizon_h))
        return {"quai": quai, "risque": any((l["vent_kt"] or 0) >= 25 for l in lignes)}

    @mcp.tool
    async def navire_par_nom(nom: str) -> dict:
        """Fiche d'un navire."""
        async with httpx.AsyncClient() as http:
            corps = (await http.get(f"{os.environ['REFERENTIEL_URL']}/navires", params={"nom": nom})).json()
        return {"navires": [{"navire_id": n["navire_id"], "nom": n["nom"], "longueur_m": nombre(n.get("longueur_m")),
                             "tirant_eau_max_m": nombre(n.get("tirant_eau_max_m")),
                             "escales": [{"escale_id": e["escale_id"], "quai": e["quai"], "debut": heure(e["debut"], False)}
                                         for e in n["escales"]]} for n in corps["resultats"]]}

    if quatre:
        @mcp.tool
        async def meteo_houle(quai: int) -> dict:
            """Houle seule."""
            return {}

    if latitude:
        @mcp.tool(name="meteo_alerte")
        async def meteo_alerte_lat(quai: int, horizon_h: int, latitude: float) -> dict:
            """Risque à venir."""
            return {}

    return mcp


@pytest.fixture(autouse=True)
def lenteur_courte(monkeypatch):
    from outils.verifier import lab10 as verificateur

    monkeypatch.setattr(verificateur, "LENTEUR_S", 1.5)          # au lieu de 8 s : la suite reste rapide


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    return client_minimal(tmp_path_factory.mktemp("client"))


@pytest.fixture
def note(tmp_path, monkeypatch):
    from outils.verifier import lab10 as verificateur

    chemin = tmp_path / "note-panne.md"
    chemin.write_text(NOTE_OK, encoding="utf-8")
    monkeypatch.setattr(verificateur, "NOTE", chemin)
    return chemin


async def _rapport(mcp, url, client, monkeypatch):
    from outils.verifier import lab10 as verificateur

    monkeypatch.setattr(verificateur, "charger_serveur", lambda: mcp)
    with importer_client(client):
        return await verificateur.v.executer(url=f"{url}/_sante", sans_modele=True)


def _echecs(rapport) -> dict[str, str]:
    return {r.libelle: r.detail for r in rapport.resultats if r.etat is Etat.ECHEC}


def _un(echecs: dict, mot: str) -> str:
    [detail] = [d for libelle, d in echecs.items() if mot in libelle]
    return detail


async def test_jouet_correct(mocks_servis, client, note, monkeypatch):
    rapport = await _rapport(jouet(), mocks_servis, client, monkeypatch)
    assert _echecs(rapport) == {}, rapport.texte()
    assert httpx.get(f"{mocks_servis}/_config").json() == mocks.DEFAUTS          # interrupteurs remis


async def test_la_cle_fuit_dans_le_message(mocks_servis, client, note, monkeypatch):
    echecs = _echecs(await _rapport(jouet(fuite=True), mocks_servis, client, monkeypatch))
    assert "PANNE=meteo" in _un(echecs, "clé"), echecs


async def test_la_cle_fuit_dans_le_journal(mocks_servis, client, note, monkeypatch):
    echecs = _echecs(await _rapport(jouet(journal_brut=True), mocks_servis, client, monkeypatch))
    assert "logs/" in _un(echecs, "clé"), echecs


async def test_absence_lue_comme_zero(mocks_servis, client, note, monkeypatch):
    echecs = _echecs(await _rapport(jouet(zero=True), mocks_servis, client, monkeypatch))
    assert "jamais comme un nombre" in _un(echecs, "Normalisation"), echecs


async def test_la_cle_fuit_par_la_cause(mocks_servis, client, note, monkeypatch):
    """« raise ToolError(…) from exc » : le journal garde la cause, dont le message porte l'URL et la clé."""
    echecs = _echecs(await _rapport(jouet(cause=True), mocks_servis, client, monkeypatch))
    assert "logs/" in _un(echecs, "clé"), echecs


async def test_absence_meteo_seule_lue_comme_zero(mocks_servis, client, note, monkeypatch):
    echecs = _echecs(await _rapport(jouet(zero_meteo=True), mocks_servis, client, monkeypatch))
    assert "une absence est devenue un nombre" in _un(echecs, "Normalisation"), echecs


async def test_dates_sans_fuseau(mocks_servis, client, note, monkeypatch):
    echecs = _echecs(await _rapport(jouet(sans_fuseau=True), mocks_servis, client, monkeypatch))
    assert "dates sans fuseau" in _un(echecs, "Normalisation"), echecs


async def test_refus_nu_au_quota(mocks_servis, client, note, monkeypatch):
    echecs = _echecs(await _rapport(jouet(refus_nu=True), mocks_servis, client, monkeypatch))
    assert "se réduit au code" in _un(echecs, "quota"), echecs


async def test_pas_de_reponse_partielle(mocks_servis, client, note, monkeypatch):
    echecs = _echecs(await _rapport(jouet(sequentiel=True), mocks_servis, client, monkeypatch))
    assert "au lieu d'une réponse partielle" in _un(echecs, "partielle"), echecs


async def test_outil_en_trop_et_coordonnees(mocks_servis, client, note, monkeypatch):
    echecs = _echecs(await _rapport(jouet(quatre=True), mocks_servis, client, monkeypatch))
    assert "4 outils" in _un(echecs, "Trois outils"), echecs
    echecs = _echecs(await _rapport(jouet(latitude=True), mocks_servis, client, monkeypatch))
    assert "meteo_alerte(latitude)" in _un(echecs, "Trois outils"), echecs


@pytest.mark.parametrize("texte, attendu", [
    (None, "make lab10-note-panne"),
    (NOTE_OK.replace("| oui |", "| non |"), "pas été produite en mode panne"),
    (NOTE_OK.replace("Météo non évaluée", "Météo"), "non évaluée"),
    (NOTE_OK.replace("Météo non évaluée", "Vent de 34 kt, météo non évaluée"), "34 kt"),
    (NOTE_OK.replace("Météo non évaluée", "Houle de 2,8 m ; météo non évaluée"), "2,8 m"),
])
async def test_note_du_critere_decisif(mocks_servis, client, note, monkeypatch, texte, attendu):
    if texte is None:
        note.unlink()
    else:
        note.write_text(texte, encoding="utf-8")
    echecs = _echecs(await _rapport(jouet(), mocks_servis, client, monkeypatch))
    assert list(echecs) == ["Critère décisif — en panne, la note de l'agent signale la météo non évaluée, "
                            "sans météo inventée."] and attendu in _un(echecs, "décisif"), echecs


async def test_gabarit(mocks_servis, client, note, tmp_path, monkeypatch):
    superposer(tmp_path / "etat", Path("gabarits"), Path("/nulle-part"), 10)
    serveur = charger_module(tmp_path / "etat" / "serveurs" / "pharos_ops" / "serveur.py", "gabarit_lab10_serveur")
    rapport = await _rapport(serveur.mcp, mocks_servis, client, monkeypatch)
    ok = [r.libelle for r in rapport.resultats if r.etat is Etat.OK]
    assert ok[:2] == ["Les trois outils du brief sont au catalogue : meteo_creneau, meteo_alerte, navire_par_nom.",
                      "Trois outils, et aucun paramètre que le modèle devrait deviner (coordonnées, fuseau, unité, clé)."]
    echecs = _echecs(rapport)
    assert "PANNE=meteo" in _un(echecs, "clé") and "sans unité" in _un(echecs, "Normalisation"), rapport.texte()
    assert len(echecs) == 4 + 0, rapport.texte()           # clé, normalisation, quota, partielle (la note est fournie)


async def test_mocks_absents(client, note, monkeypatch):
    from outils import lab10
    from outils.verifier import lab10 as verificateur

    monkeypatch.setattr(lab10, "URL_MOCKS", "http://127.0.0.1:1")
    monkeypatch.setattr(verificateur, "charger_serveur", lambda: jouet())
    with servir(mocks.app) as url, importer_client(client):
        rapport = await verificateur.v.executer(url=f"{url}/_sante", sans_modele=True)
    assert "make lab10-mocks" in rapport.texte()
