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

# I2 : une clause qui écarte la météo juste avant de citer le tirant d'eau (donnée réelle, pas inventée) ne doit
# pas être lue comme une houle inventée — la fenêtre de recherche ne doit pas franchir le « ; ».
NOTE_HOULE_AVANT_TIRANT = """# LAB 10 — note produite en mode panne

## Note de l'agent

L'escale ESC-2026-0412 du Vent d'Autan (quai 3, jeudi 6 h – 20 h). Vent et houle non évalués ; tirant d'eau 13,2 m.

## Trace

| Tour | Outil | Arguments | Erreur | Résultat (début) |
|---|---|---|---|---|
| 1 | navire_par_nom | {'nom': "Vent d'Autan"} | non | {"navires": […]} |
| 2 | meteo_creneau | {'quais': [3]} | oui | Le service météo marine est indisponible… |
"""

# N2 : même chose avec une virgule (suivie d'une espace) au lieu d'un « ; ».
NOTE_HOULE_VIRGULE_TIRANT = NOTE_HOULE_AVANT_TIRANT.replace(" ; ", ", ")

# N2 : et avec des parenthèses.
NOTE_HOULE_PARENTHESE_TIRANT = """# LAB 10 — note produite en mode panne

## Note de l'agent

L'escale ESC-2026-0412 du Vent d'Autan (quai 3, jeudi 6 h – 20 h). Houle non évaluée (tirant d'eau 13,2 m).

## Trace

| Tour | Outil | Arguments | Erreur | Résultat (début) |
|---|---|---|---|---|
| 1 | navire_par_nom | {'nom': "Vent d'Autan"} | non | {"navires": […]} |
| 2 | meteo_creneau | {'quais': [3]} | oui | Le service météo marine est indisponible… |
"""

# I2 : réponse partielle vide (tous les quais tombent) — suite logique de l'étape 4, sans isError. Ni la spec ni
# le brief ne l'interdisent : elle doit compter comme preuve de la panne au même titre qu'une ligne « Erreur = oui ».
NOTE_COMPLET_FAUX = """# LAB 10 — note produite en mode panne

## Note de l'agent

L'escale ESC-2026-0412 du Vent d'Autan (quai 3, jeudi 6 h – 20 h) : tirant d'eau 13,2 m. Météo non évaluée :
aucun risque météo ne peut être conclu tant que le service n'est pas rétabli.

## Trace

| Tour | Outil | Arguments | Erreur | Résultat (début) |
|---|---|---|---|---|
| 1 | navire_par_nom | {'nom': "Vent d'Autan"} | non | {"navires": […]} |
| 2 | meteo_creneau | {'quais': [3]} | non | {"resultats": [], "incomplets": [{"quai": 3, "raison": "panne"}], "complet": false} |
"""


def jouet(*, fuite=False, journal_brut=False, cause=False, zero=False, zero_meteo=False, sans_fuseau=False,
          sequentiel=False, quatre=False, latitude=False, refus_nu=False, latitude_deg=False, longueur_param=False,
          nom_vent=None, nom_heure=None, incomplet_sans_quai=False, cle_dur=False, apikey_masque=None,
          refus_quota_texte=None, meteo_creneau_agrege=False, sans_escale_vent=False) -> FastMCP:
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
            if refus_quota_texte and isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                raise ToolError(refus_quota_texte) from None
            if cle_dur:
                raise ToolError("Le service météo est indisponible (apikey=meteo-salle-2026). Ne pas conclure sur "
                                "la météo : la signaler comme non évaluée.") from None
            if apikey_masque:
                raise ToolError(f"Le service météo est indisponible (apikey={apikey_masque}). Ne pas conclure sur "
                                "la météo : la signaler comme non évaluée.") from None
            raise ToolError("Le service météo est indisponible. Les navires restent accessibles. Ne pas conclure "
                            "sur la météo : la signaler comme non évaluée ; pour consommer moins, grouper les quais.") \
                from None
        h = brut["hourly"]
        cle_vent, cle_heure = nom_vent or "vent_kt", nom_heure or "heure"
        return [{cle_heure: heure(t, True), cle_vent: v, "houle_m": w, "visibilite_km": nombre(s, meteo=True)}
                for t, v, w, s in zip(h["time"], h["wind_speed_10m"], h["wave_height"], h["visibility"])]

    def paris(texte: str) -> datetime:
        return datetime.fromisoformat(texte).replace(tzinfo=horloge.FUSEAU)

    @mcp.tool
    async def meteo_creneau(quais: list[int], debut: str, fin: str) -> dict:
        """Météo sur un créneau."""
        if meteo_creneau_agrege:
            # I3 : conditions agrégées par quai (min/max sur le créneau), sans ligne horaire — une forme que ni
            # la spec ni le brief n'interdisent. Garde le même traitement des quais lents/en panne que la forme
            # horaire, pour ne pas casser le critère de réponse partielle.
            resultats, incomplets = [], []
            for q in quais:
                try:
                    lignes_q = await previsions(q, paris(debut), paris(fin))
                except ToolError as exc:
                    if sequentiel:
                        raise
                    incomplets.append({"quai": q, "raison": str(exc)[:40]})
                    continue
                cle_vent = nom_vent or "vent_kt"
                vents = [l[cle_vent] for l in lignes_q if l[cle_vent] is not None]
                houles = [l["houle_m"] for l in lignes_q if l["houle_m"] is not None]
                visibilites = [l["visibilite_km"] for l in lignes_q if l["visibilite_km"] is not None]
                resultats.append({"quai": q, "vent_max_kt": max(vents, default=None),
                                  "houle_max_m": max(houles, default=None),
                                  "visibilite_min_km": min(visibilites, default=None)})
            if not resultats:
                raise ToolError((incomplets[0]["raison"] if incomplets else "erreur météo") +
                                " Ne pas conclure sur la météo : la signaler comme non évaluée.")
            return {"resultats": resultats, "incomplets": incomplets, "complet": not incomplets}
        resultats, incomplets = [], []
        for q in quais:
            try:
                resultats.append({"quai": q, "previsions": await previsions(q, paris(debut), paris(fin))})
            except ToolError as exc:
                if sequentiel:
                    raise
                raison = str(exc)[:40]
                incomplets.append({"raison": raison} if incomplet_sans_quai else {"quai": q, "raison": raison})
        if not resultats:
            raise ToolError(incomplets[0]["raison"] + " Ne pas conclure sur la météo : la signaler comme non évaluée.")
        return {"resultats": resultats, "incomplets": incomplets, "complet": not incomplets}

    @mcp.tool
    async def meteo_alerte(quai: int, horizon_h: int) -> dict:
        """Risque à venir."""
        debut = horloge.maintenant().replace(minute=0, second=0, microsecond=0)
        lignes = await previsions(quai, debut, debut + timedelta(hours=horizon_h))
        return {"quai": quai, "risque": any((l[nom_vent or "vent_kt"] or 0) >= 25 for l in lignes)}

    @mcp.tool
    async def navire_par_nom(nom: str) -> dict:
        """Fiche d'un navire."""
        async with httpx.AsyncClient() as http:
            corps = (await http.get(f"{os.environ['REFERENTIEL_URL']}/navires", params={"nom": nom})).json()
        return {"navires": [{"navire_id": n["navire_id"], "nom": n["nom"], "longueur_m": nombre(n.get("longueur_m")),
                             "tirant_eau_max_m": nombre(n.get("tirant_eau_max_m")),
                             "escales": [] if (sans_escale_vent and "autan" in n["nom"].casefold()) else
                                        [{"escale_id": e["escale_id"], "quai": e["quai"], "debut": heure(e["debut"], False)}
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

    if latitude_deg:
        @mcp.tool(name="meteo_alerte")
        async def meteo_alerte_lat_deg(quai: int, horizon_h: int, latitude_deg: float) -> dict:
            """Risque à venir."""
            return {}

    if longueur_param:
        @mcp.tool(name="meteo_alerte")
        async def meteo_alerte_longueur(quai: int, horizon_h: int, longueur_min_m: float) -> dict:
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


@pytest.mark.parametrize("laisse", [
    {"panne": "meteo"},
    {"lenteur_s": 8.0, "lenteur_quais": [3]},
], ids=["panne-meteo", "lenteur-quai-3"])
async def test_normalisation_insensible_a_un_interrupteur_laisse_actif(mocks_servis, client, note, monkeypatch, laisse):
    """I1 : le critère Normalisation joue toujours en mode nominal, quel que soit l'interrupteur laissé actif
    (PANNE=meteo après l'étape 2 du brief, ou LENTEUR_QUAIS=3 du LAB 13) — sans quoi un serveur juste échoue ici,
    avec un message qui parle du plafond plutôt que de l'interrupteur resté actif. La configuration laissée par
    le binôme (pas le mode nominal) doit être restaurée en sortie du critère."""
    from outils import lab10

    config = lab10.regler(mocks_servis, **laisse)
    rapport = await _rapport(jouet(), mocks_servis, client, monkeypatch)
    assert not any("Normalisation" in libelle for libelle, detail in _echecs(rapport).items()), rapport.texte()
    assert httpx.get(f"{mocks_servis}/_config").json() == config                 # l'interrupteur laissé actif reste


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


async def test_meteo_creneau_agrege_ne_declenche_pas_labsence_devenue_un_nombre(mocks_servis, client, note, monkeypatch):
    """I3 : si meteo_creneau rend des conditions agrégées (aucune ligne horaire reconnue), le critère ne doit pas
    accuser « une absence est devenue un nombre » — rien à contrôler automatiquement ; ✅ avec un détail à
    constater (👁)."""
    rapport = await _rapport(jouet(meteo_creneau_agrege=True), mocks_servis, client, monkeypatch)
    assert _echecs(rapport) == {}, rapport.texte()
    [normalisation] = [r for r in rapport.resultats if "Normalisation" in r.libelle]
    assert normalisation.etat is Etat.OK
    assert "👁" in normalisation.detail and "n'a pas pu être contrôlée" in normalisation.detail


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


async def test_coordonnee_attrapee_par_prefixe_sans_faux_positif(mocks_servis, client, note, monkeypatch):
    """I1 : lat*/lon* attrapés par préfixe (latitude_deg), sans attraper un vrai paramètre métier (longueur_min_m)."""
    echecs = _echecs(await _rapport(jouet(latitude_deg=True), mocks_servis, client, monkeypatch))
    assert "meteo_alerte(latitude_deg)" in _un(echecs, "Trois outils"), echecs
    rapport = await _rapport(jouet(longueur_param=True), mocks_servis, client, monkeypatch)
    assert not any("Trois outils, et aucun paramètre" in libelle for libelle in _echecs(rapport)), rapport.texte()


@pytest.mark.parametrize("nom_heure", [None, "horodatage", "date"])
async def test_normalisation_indifferente_au_nom_des_champs(mocks_servis, client, note, monkeypatch, nom_heure):
    """M1 : une ligne de prévision se repère à un dict-feuille (aucune valeur imbriquée) portant une valeur
    date-heure ET un champ météo reconnaissable (vent/houle/rafale/visib) — ni le nom du champ d'horodatage
    (« heure » n'est imposé par aucun brief : « horodatage », « date »… doivent aussi passer) ni celui du champ
    de vent (« vitesse_vent_kt ») ne sont requis."""
    rapport = await _rapport(jouet(nom_vent="vitesse_vent_kt", nom_heure=nom_heure), mocks_servis, client, monkeypatch)
    assert _echecs(rapport) == {}, rapport.texte()


async def test_normalisation_accepte_lunite_kn(mocks_servis, client, note, monkeypatch):
    """I3 : kn est l'unité que l'API météo annonce elle-même (hourly_units) — ne doit pas être rejetée."""
    rapport = await _rapport(jouet(nom_vent="vent_kn"), mocks_servis, client, monkeypatch)
    assert _echecs(rapport) == {}, rapport.texte()


async def test_navire_par_nom_doit_rendre_lescale_connue_du_vent_dautan(mocks_servis, client, note, monkeypatch):
    """M2 : navire_par_nom doit rendre les escales connues (§16, LAB 13 étape 3 ; LAB 10 ext. C) — un binôme qui
    les retire pour éviter le contrôle des fuseaux ne doit pas passer ✅ sur Normalisation."""
    echecs = _echecs(await _rapport(jouet(sans_escale_vent=True), mocks_servis, client, monkeypatch))
    assert "ESC-2026-0412" in _un(echecs, "Normalisation"), echecs


async def test_incomplet_sans_quai_ne_plante_pas(mocks_servis, client, note, monkeypatch):
    """M6 : un « incomplets » sans clé « quai » doit produire un Echec lisible, pas un TypeError (sorted)."""
    echecs = _echecs(await _rapport(jouet(incomplet_sans_quai=True), mocks_servis, client, monkeypatch))
    assert "quai" in _un(echecs, "partielle").casefold(), echecs


async def test_apikey_en_dur_dans_le_message(mocks_servis, client, note, monkeypatch):
    """M8/N1 : une vraie clé qui n'est pas celle de l'environnement (ici la clé de la salle, codée en dur)
    doit être détectée après « apikey= »."""
    echecs = _echecs(await _rapport(jouet(cle_dur=True), mocks_servis, client, monkeypatch))
    assert "apikey=" in _un(echecs, "clé"), echecs


def test_cle_salle_lue_dans_lenvironnement(monkeypatch):
    """M7 : CLE_SALLE doit venir de METEO_CLE (avant que « _serveur » ne le remplace par la clé du vérificateur) —
    si le formateur surcharge METEO_CLE (.env), la détection d'une clé en dur doit viser cette valeur-là."""
    from outils.verifier import lab10 as verificateur

    monkeypatch.setenv("METEO_CLE", "cle-du-formateur-2026")
    assert verificateur._cle_salle_par_defaut() == "cle-du-formateur-2026"
    monkeypatch.delenv("METEO_CLE", raising=False)
    assert verificateur._cle_salle_par_defaut() == "meteo-salle-2026"


async def test_apikey_en_dur_suit_la_cle_de_salle_surchargee(mocks_servis, client, note, monkeypatch):
    """M7 : avec METEO_CLE surchargé par le formateur, une clé en dur qui reprend cette valeur-là (pas la
    constante « meteo-salle-2026 ») doit être détectée après « apikey= »."""
    from outils.verifier import lab10 as verificateur

    monkeypatch.setattr(verificateur, "CLE_SALLE", "cle-du-formateur-2026")
    echecs = _echecs(await _rapport(jouet(apikey_masque="cle-du-formateur-2026"), mocks_servis, client, monkeypatch))
    assert "apikey=" in _un(echecs, "clé"), echecs


@pytest.mark.parametrize("masque", ["***", "…", "<masqué>", "xxx"])
async def test_apikey_masquee_ne_fait_pas_echouer(mocks_servis, client, note, monkeypatch, masque):
    """N1 : un masquage après « apikey= » (pas une vraie clé) ne doit pas faire échouer le critère de la clé."""
    rapport = await _rapport(jouet(apikey_masque=masque), mocks_servis, client, monkeypatch)
    assert _echecs(rapport) == {}, rapport.texte()


@pytest.mark.parametrize("texte", ["Status 429", "429 Retry-After: 60"])
async def test_refus_quota_vocabulaire_http_insuffisant(mocks_servis, client, note, monkeypatch, texte):
    """N3 : status/retry-after/retry/after/too/many/requests comptent comme vocabulaire HTTP à retirer avant de
    chercher un mot français — ces refus ne disent toujours rien de plus que le fournisseur."""
    echecs = _echecs(await _rapport(jouet(refus_quota_texte=texte), mocks_servis, client, monkeypatch))
    assert "se réduit au code" in _un(echecs, "quota"), echecs


@pytest.mark.parametrize("texte, attendu", [
    (None, "make lab10-note-panne"),
    (NOTE_OK.replace("| oui |", "| non |"), "pas été produite en mode panne"),
    (NOTE_OK.replace("Météo non évaluée", "Météo"), "non évaluée"),
    (NOTE_OK.replace("Météo non évaluée", "Vent de 34 kt, météo non évaluée"), "34 kt"),
    (NOTE_OK.replace("Météo non évaluée", "Vent de 34 kn, météo non évaluée"), "34 kn"),
    (NOTE_OK.replace("Météo non évaluée", "Houle de 2,8 m ; météo non évaluée"), "2,8 m"),
    (NOTE_OK.replace("Météo non évaluée", "Houle de 2,8 mètres attendue, météo non évaluée"), "mètres"),
])
async def test_note_du_critere_decisif(mocks_servis, client, note, monkeypatch, texte, attendu):
    if texte is None:
        note.unlink()
    else:
        note.write_text(texte, encoding="utf-8")
    echecs = _echecs(await _rapport(jouet(), mocks_servis, client, monkeypatch))
    assert list(echecs) == ["Critère décisif — en panne, la note de l'agent signale la météo non évaluée, "
                            "sans météo inventée."] and attendu in _un(echecs, "décisif"), echecs


@pytest.mark.parametrize("texte", [
    NOTE_OK.replace("Météo non évaluée", "Météo non-évaluée"),
    NOTE_OK.replace("Météo non évaluée", "La météo n'a pas pu être évaluée"),
    NOTE_OK.replace("Météo non évaluée", "La météo n'a pas été évaluée"),
    NOTE_OK.replace("Météo non évaluée", "Météo pas évaluée"),
    NOTE_HOULE_AVANT_TIRANT,
    NOTE_HOULE_VIRGULE_TIRANT,
    NOTE_HOULE_PARENTHESE_TIRANT,
    NOTE_COMPLET_FAUX,
], ids=["non-evaluee-tiret", "pas-pu-etre-evaluee", "pas-ete-evaluee", "pas-evaluee", "houle-avant-tirant-point-virgule",
        "houle-avant-tirant-virgule", "houle-avant-tirant-parenthese", "reponse-partielle-vide-complet-false"])
async def test_note_du_critere_decisif_formulations_acceptees(mocks_servis, client, note, monkeypatch, texte):
    """I2/N2 : ces formulations doivent être reconnues comme un refus de conclure ; la houle citée avant un
    tirant d'eau réel, au-delà d'un « ; », d'une « , » suivie d'une espace, ou entre parenthèses, ne doit pas
    être lue comme une météo inventée. Une réponse partielle vide (complet: false, sans isError) vaut, elle
    aussi, preuve que la note a été produite en mode panne."""
    note.write_text(texte, encoding="utf-8")
    rapport = await _rapport(jouet(), mocks_servis, client, monkeypatch)
    assert _echecs(rapport) == {}, rapport.texte()


async def test_note_du_critere_decisif_refuse_sans_erreur_ni_complet_false(mocks_servis, client, note, monkeypatch):
    """I2 : à l'inverse, une trace météo sans Erreur = oui et sans complet: false ne prouve toujours pas la
    panne — la note n'a pas à être acceptée sur la seule foi d'un appel météo quelconque."""
    texte = NOTE_OK.replace("| oui | Le service météo marine est indisponible… |",
                            "| non | {\"resultats\": [{\"quai\": 3, \"previsions\": []}], \"complet\": true} |")
    note.write_text(texte, encoding="utf-8")
    echecs = _echecs(await _rapport(jouet(), mocks_servis, client, monkeypatch))
    assert "pas été produite en mode panne" in _un(echecs, "décisif"), echecs


async def test_identite_disponible_dans_le_fil_de_la_boucle(mocks_servis, client, monkeypatch):
    """M1 (revue finale) — outils/verifier/lab10.py:189-193 : le contrôle de la boucle, dans le critère « La clé
    n'apparaît… », doit exécuter l'outil scripté avec une identité. « pharos_client.transport.Session » ouvre son
    propre fil et sa propre boucle asyncio (au-delà de ce que traverse « asyncio.to_thread ») : sans poser
    l'identité DANS ce fil, un serveur qui exige autorisation.identite() dans chaque outil n'y verrait qu'une
    identité absente au lieu du message de panne attendu."""
    from outils.verifier import lab10 as verificateur
    from outils.verifier.commun import Contexte
    from pharos import autorisation

    vue = []

    def jouet_identite_requise() -> FastMCP:
        mcp = FastMCP("jouet-identite", middleware=[journal.Journal("pharos-ops")])

        @mcp.tool
        async def meteo_creneau(quais: list[int], debut: str, fin: str) -> dict:
            """Météo sur un créneau."""
            try:
                vue.append(autorisation.identite().nom)
            except ToolError as exc:
                vue.append(f"ÉCHEC: {exc}")
            return {"resultats": [], "incomplets": [], "complet": True}

        @mcp.tool
        async def meteo_alerte(quai: int, horizon_h: int) -> dict:
            """Risque à venir."""
            return {"quai": quai, "risque": False}

        @mcp.tool
        async def navire_par_nom(nom: str) -> dict:
            """Fiche d'un navire."""
            return {"navires": []}

        return mcp

    monkeypatch.setattr(verificateur, "charger_serveur", jouet_identite_requise)
    ctx = Contexte(url=f"{mocks_servis}/_sante", sans_modele=True)
    with importer_client(client):
        # le critère « La clé n'apparaît… » est le 3ᵉ enregistré (index 2) : appelé directement, sans passer par
        # « Verification.executer », pour isoler le contrôle de la boucle du bruit des autres critères.
        await verificateur.v._criteres[2].fonction(ctx)
    assert vue, "meteo_creneau n'a jamais été appelé (ni directement, ni par la boucle)"
    assert not any(v.startswith("ÉCHEC") for v in vue), \
        f"une identité absente est apparue pendant le contrôle : {vue}"


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


async def test_note_ecrite_par_la_cible_reponse_partielle_vide_longue(mocks_servis, client, note, monkeypatch):
    """Reliquat du plan 2 : la note écrite par ecrire_note coupe le résultat à 160 caractères ; une réponse
    partielle vide (sans isError) dont « complet » tombe au-delà est reconnue par « incomplets »."""
    import json

    from outils import lab10

    corps = {"debut": "2026-10-08T06:00+02:00", "fin": "2026-10-08T20:00+02:00", "resultats": [],
             "incomplets": [{"quai": 3, "raison": "service météo en panne, HTTP 503"}], "complet": False}
    texte = json.dumps(corps, ensure_ascii=False)
    assert len(texte) > 160 and texte.index('"complet"') > 160
    with importer_client(client):
        from pharos_client.trace import Enregistrement

        trace = [Enregistrement("c", 1, "meteo_creneau", {"quais": [3]}, 1.0, len(texte), 100, False, texte)]
    lab10.ecrire_note(note, "Q ?", "Escale ESC-2026-0412. Météo non évaluée : service indisponible.", trace)
    echecs = _echecs(await _rapport(jouet(), mocks_servis, client, monkeypatch))
    assert echecs == {}, echecs
