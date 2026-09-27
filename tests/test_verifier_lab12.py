"""Vérificateur du LAB 12 : sur deux instances jouettes derrière le répartiteur du kit, dont on active les défauts
un par un. Mocks, instances et répartiteur sont servis dans le processus ; aucun modèle."""

import contextlib
import itertools
import json
import shutil
import types
import uuid
from pathlib import Path

import mcp_types
import pytest
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.server.request_state import RequestStateSecurity

from outils.repartiteur import creer_repartiteur
from outils.servir import servir
from outils.verifier.commun import Etat
from pharos import canal, journal
from tests.aides import BOUCLE_MINIMALE, importer_client

CLE = "cle-de-test-lab12-au-moins-trente-deux-octets"
BOUCLE_ENTREES = BOUCLE_MINIMALE.replace(
    "from pharos_client import modele", "from pharos_client import entrees, modele").replace(
    "with Session(url) as s:", "with entrees.SessionElicitation(url) as s:").replace(
    "res = s.appeler(a.nom, a.arguments, correlation=correlation)",
    "res = entrees.appeler_brut(s, a.nom, a.arguments)\n"
    "                if isinstance(res, entrees.DemandeEntree):\n"
    "                    rep = {k: entrees.demander_utilisateur(d) for k, d in res.demandes.items()}\n"
    "                    res = entrees.appeler_brut(s, a.nom, a.arguments, reponses=rep, etat=res.etat)")
# Reconnaît la demande et ouvre la bonne session, mais ne rejoue pas.
BOUCLE_SANS_REJEU = BOUCLE_ENTREES.replace(
    "rep = {k: entrees.demander_utilisateur(d) for k, d in res.demandes.items()}",
    "rep = None").replace(
    "res = entrees.appeler_brut(s, a.nom, a.arguments, reponses=rep, etat=res.etat)",
    "res = Resultat('demande reçue', False, 0)").replace(
    "from pharos_client.transport import Session", "from pharos_client.transport import Resultat, Session")
BOUCLE_QUI_S_ARRETE = '''"""Boucle qui s'arrête comme celle du LAB 4 : une exception qui porte la trace."""


class EchecNonRecuperable(Exception):
    def __init__(self, message, trace):
        super().__init__(message)
        self.trace = trace


def executer(question, *, url, **_):
    raise EchecNonRecuperable("serveur injoignable ou transport en échec", [])
'''


def instance(racine: Path, *, direct=False, defaut_vrai=False, sans_destinataire=False, sans_repli=False,
             cle_ephemere=False, brouillon=False, ignore_non=False, en_memoire=None, sans_etat=False,
             majuscules=False, repli_sans_note=False) -> FastMCP:
    securite = None if cle_ephemere else RequestStateSecurity(keys=[CLE], audience="pharos-ops")
    mcp = FastMCP("pharos-ops", middleware=[journal.Journal("pharos-ops")], request_state_security=securite)

    async def publier(escale_id, niveau, destinataire, note):
        await canal.publier(escale_id, niveau, destinataire, note)
        return {"publiee": True}

    async def publier_alerte(escale_id: str, niveau: str, ctx: Context, destinataire: str = "exploitation",
                             note: str = "") -> dict:
        if direct:
            return await publier(escale_id, niveau, destinataire, note)
        if not ctx.input_responses:
            if brouillon:
                (racine / "labs" / "lab12").mkdir(parents=True, exist_ok=True)
                (racine / "labs" / "lab12" / "brouillon.md").write_text(note or "brouillon", encoding="utf-8")
            meta = ctx.request_context.meta
            brut = meta.model_dump(by_alias=True) if hasattr(meta, "model_dump") else dict(meta or {})
            if "elicitation" not in (brut.get("io.modelcontextprotocol/clientCapabilities") or {}) and not sans_repli:
                if repli_sans_note:
                    raise ToolError("Publication impossible sans confirmation : publier depuis un client qui la demande.")
                raise ToolError("Publication impossible sans confirmation : préparer la note sans la publier.")
            demande = uuid.uuid4().hex
            if en_memoire is not None:
                en_memoire[demande] = True                   # le piège : l'appel en attente gardé par l'instance
            cible = "" if sans_destinataire else f" à {destinataire.capitalize() if majuscules else destinataire}"
            return mcp_types.InputRequiredResult(
                input_requests={"confirmation": mcp_types.ElicitRequest(params=mcp_types.ElicitRequestFormParams(
                    message=f"Publier l'alerte {niveau.upper() if majuscules else niveau} pour {escale_id}{cible} ?",
                    requested_schema={"type": "object", "properties": {
                        "confirmer": {"type": "boolean", "default": defaut_vrai}}}))},
                request_state=json.dumps({"escale_id": escale_id, "demande": demande}))
        etat = json.loads(ctx.request_state or "{}")
        if not sans_etat and etat.get("escale_id") != escale_id:      # la confirmation porte sur CET appel
            raise ToolError("La confirmation ne porte pas sur cette publication : rien n'est parti.")
        if en_memoire is not None and not en_memoire.get(etat.get("demande")):
            raise ToolError("Aucune demande en attente pour cette escale.")
        reponse = ctx.input_responses["confirmation"]
        if ignore_non or (reponse.action == "accept" and (reponse.content or {}).get("confirmer")):
            return await publier(escale_id, niveau, destinataire, note)
        return {"publiee": False}

    if sans_destinataire:
        @mcp.tool(name="publier_alerte")
        async def sans(escale_id: str, niveau: str, ctx: Context) -> dict:
            """Publie une alerte."""
            return await publier_alerte(escale_id, niveau, ctx)
    else:
        mcp.tool(name="publier_alerte", description="Publie une alerte, après confirmation.")(publier_alerte)

    return mcp


@contextlib.contextmanager
def repartis(racine: Path, **defauts):
    memoires = ({}, {}) if defauts.pop("etat_en_memoire", False) else (None, None)
    a, b = instance(racine, en_memoire=memoires[0], **defauts), instance(racine, en_memoire=memoires[1], **defauts)
    with servir(a.http_app(path="/mcp", json_response=True)) as ua, \
            servir(b.http_app(path="/mcp", json_response=True)) as ub, servir(creer_repartiteur(ua, ub)) as ur:
        yield f"{ur}/mcp"


def _client(dossier: Path, boucle: str) -> Path:
    for gabarit in ("lab04", "lab11", "lab12"):
        shutil.copytree(f"gabarits/{gabarit}/client", dossier, dirs_exist_ok=True)
    (dossier / "pharos_client" / "boucle.py").write_text(boucle, encoding="utf-8")
    return dossier


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    return _client(tmp_path_factory.mktemp("client12"), BOUCLE_ENTREES)


@pytest.fixture(scope="module")
def client_sans_rejeu(tmp_path_factory):
    return _client(tmp_path_factory.mktemp("client12-nu"), BOUCLE_MINIMALE)


@pytest.fixture
def racine(tmp_path, monkeypatch, mocks_servis):
    from outils.verifier import lab12

    (tmp_path / "labs" / "lab12").mkdir(parents=True)
    (tmp_path / "labs" / "lab12" / "mesures.md").write_text(
        "| Alertes parties à l'étape 1 (trois conversations) | 2, 1, 3 |\n", encoding="utf-8")
    monkeypatch.setattr(lab12, "RACINE", tmp_path)
    monkeypatch.setattr(lab12, "MESURES", tmp_path / "labs" / "lab12" / "mesures.md")
    monkeypatch.setenv("CANAL_URL", f"{mocks_servis}/canal")
    return tmp_path


async def _rapport(url, client):
    from outils.verifier import lab12

    with importer_client(client):
        return await lab12.v.executer(url=url, sans_modele=True)


def _echecs(rapport) -> dict[str, str]:
    return {r.libelle: r.detail for r in rapport.resultats if r.etat is Etat.ECHEC}


def _un(echecs: dict, mot: str) -> str:
    [detail] = [d for libelle, d in echecs.items() if mot in libelle]
    return detail


async def test_jouet_correct(racine, client):
    with repartis(racine) as url:
        rapport = await _rapport(url, client)
    assert _echecs(rapport) == {}, rapport.texte()


@pytest.mark.parametrize("defaut, critere, attendu", [
    ({"direct": True}, "Aucun chemin", "sans rejeu"),
    ({"defaut_vrai": True}, "demande est conforme", "default: false"),
    ({"sans_destinataire": True}, "catalogue", "destinataire"),
    ({"sans_repli": True}, "Repli", "pas un refus"),
    ({"cle_ephemere": True}, "Deux instances", "même clé"),
    ({"etat_en_memoire": True}, "Deux instances", "rien ne doit rester en mémoire"),
    ({"brouillon": True}, "décisif", "brouillon.md"),
    ({"ignore_non": True}, "décisif", "« non »"),
    ({"sans_etat": True}, "décisif", "réponses sans requestState"),
    ({"repli_sans_note": True}, "Repli", "le vérificateur attend cette alternative-là"),
])
async def test_defauts(racine, client, defaut, critere, attendu):
    with repartis(racine, **defaut) as url:
        echecs = _echecs(await _rapport(url, client))
    assert attendu in _un(echecs, critere), echecs


async def test_demande_en_majuscules(racine, client):
    with repartis(racine, majuscules=True) as url:
        rapport = await _rapport(url, client)
    assert _echecs(rapport) == {}, rapport.texte()


@pytest.mark.parametrize("decalage", [0, 1])
async def test_deux_instances_sans_alternance_stricte(racine, client, monkeypatch, decalage):
    """Une requête intercalée (un autre client sur 8203) : le rejeu peut atterrir sur l'instance de la demande."""
    from outils import repartiteur

    ordre = "aabb"[decalage:] + "aabb"[:decalage]
    monkeypatch.setattr(repartiteur, "itertools", types.SimpleNamespace(cycle=lambda _: itertools.cycle(ordre)))
    with repartis(racine) as url:
        rapport = await _rapport(url, client)
    assert _echecs(rapport) == {}, rapport.texte()


async def test_boucle_avec_une_session_ordinaire(racine, client_sans_rejeu):
    with repartis(racine) as url:
        echecs = _echecs(await _rapport(url, client_sans_rejeu))
    detail = _un(echecs, "MÊME appel")
    assert "ne déclare pas l'élicitation" in detail and "entrees.SessionElicitation" in detail, echecs


async def test_boucle_sans_rejeu(racine, tmp_path_factory):
    client = _client(tmp_path_factory.mktemp("client12-sans-rejeu"), BOUCLE_SANS_REJEU)
    with repartis(racine) as url:
        echecs = _echecs(await _rapport(url, client))
    assert "n'a pas reposé l'appel" in _un(echecs, "MÊME appel"), echecs


async def test_boucle_qui_s_arrete(racine, tmp_path_factory):
    client = _client(tmp_path_factory.mktemp("client12-arret"), BOUCLE_QUI_S_ARRETE)
    with repartis(racine) as url:
        echecs = _echecs(await _rapport(url, client))
    assert "la boucle s'est arrêtée : serveur injoignable" in _un(echecs, "MÊME appel"), echecs


async def test_etape_1_non_consignee(racine, client):
    (racine / "labs" / "lab12" / "mesures.md").write_text("| Alertes parties à l'étape 1 | |\n", encoding="utf-8")
    with repartis(racine) as url:
        echecs = _echecs(await _rapport(url, client))
    assert list(echecs) == ["Le chiffre de l'étape 1 (sans garde-fou) est consigné dans labs/lab12/mesures.md."]
