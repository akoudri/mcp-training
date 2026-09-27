"""Kit du LAB 12 : demandes d'entrée côté client (entrees.py), canal d'alertes, outils, deux instances, démarrage.
Serveurs jouets en mémoire ou servis dans le processus ; ni base, ni Docker, ni modèle."""

import builtins
import json
import re
import shutil
from datetime import timedelta
from pathlib import Path

import httpx
import mcp_types
import pytest
from fastmcp import Context, FastMCP
from fastmcp.utilities.tasks import TaskConfig
from fastmcp_tasks import TasksExtension
from mcp.server.request_state import RequestStateSecurity

from outils import labs
from outils.servir import servir
from pharos import canal
from tests.aides import importer_client

CLE = "cle-de-test-kit-lab12-au-moins-32-octets-0001"


def serveur(publiees: list) -> FastMCP:
    mcp = FastMCP("kit12", request_state_security=RequestStateSecurity(keys=[CLE]))
    mcp.add_extension(TasksExtension())            # un outil task=… exige l'extension, sinon le serveur ne démarre pas

    async def confirmer_puis_publier(escale_id: str, ctx: Context) -> dict:
        meta = ctx.request_context.meta
        brut = meta.model_dump(by_alias=True) if hasattr(meta, "model_dump") else dict(meta or {})
        if not ctx.input_responses:
            if "elicitation" not in (brut.get("io.modelcontextprotocol/clientCapabilities") or {}):
                return {"elicitation": False}
            return mcp_types.InputRequiredResult(
                input_requests={"confirmation": mcp_types.ElicitRequest(params=mcp_types.ElicitRequestFormParams(
                    message=f"Publier {escale_id} ?", requested_schema={"type": "object", "properties": {
                        "confirmer": {"type": "boolean", "title": "Publier", "default": False}}}))},
                request_state=json.dumps({"escale_id": escale_id}))
        r = ctx.input_responses["confirmation"]
        if r.action == "accept" and (r.content or {}).get("confirmer"):
            publiees.append(escale_id)
        return {"publiee": escale_id in publiees}

    @mcp.tool
    async def publier(escale_id: str, ctx: Context) -> dict:
        """Demande une confirmation, puis publie."""
        return await confirmer_puis_publier(escale_id, ctx)

    @mcp.tool
    async def publier_alerte(escale_id: str, niveau: str, ctx: Context, destinataire: str = "exploitation",
                             note: str = "") -> dict:
        """La même chose, sous le nom et la signature du LAB 12."""
        return await confirmer_puis_publier(escale_id, ctx)

    @mcp.tool(task=TaskConfig(mode="required", poll_interval=timedelta(seconds=0.05)))
    async def longue(ctx: Context) -> dict:
        """Une tâche."""
        await ctx.report_progress(1, 1, "1 escales sur 1")
        return {"fini": True}

    return mcp


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("client12")
    for gabarit in ("lab04", "lab11", "lab12"):
        shutil.copytree(f"gabarits/{gabarit}/client", dossier, dirs_exist_ok=True)
    return dossier


def test_session_elicitation_demande_rejeu_et_refus_du_protocole(client):
    publiees = []
    with importer_client(client):
        from pharos_client import entrees
        from pharos_client.transport import Session

        with Session(serveur(publiees)) as s:
            sans = entrees.appeler_brut(s, "publier", {"escale_id": "E1"})     # Session ordinaire : pas d'élicitation
        with entrees.SessionElicitation(serveur(publiees)) as s:
            demande = entrees.appeler_brut(s, "publier", {"escale_id": "E1"})
            assert isinstance(demande, entrees.DemandeEntree) and demande.etat
            assert demande.demandes["confirmation"]["message"] == "Publier E1 ?"
            assert demande.demandes["confirmation"]["schema"]["properties"]["confirmer"]["default"] is False
            oui = {"confirmation": {"action": "accept", "content": {"confirmer": True}}}
            fait = entrees.appeler_brut(s, "publier", {"escale_id": "E1"}, reponses=oui, etat=demande.etat)
            echange = entrees.appeler_brut(s, "publier", {"escale_id": "E2"}, reponses=oui, etat=demande.etat)
            lignes = []
            tache = entrees.appeler_brut(s, "longue", {}, afficher=lignes.append)
    assert '"elicitation":false' in sans.texte.replace(" ", "")
    assert not fait.est_erreur and '"publiee"' in fait.texte and publiees == ["E1"]
    assert echange.est_erreur and echange.texte.startswith("Refus du protocole") and publiees == ["E1"]
    assert not tache.est_erreur and "fini" in tache.texte and any("acceptée" in l for l in lignes)


def test_demander_utilisateur_au_terminal(client, monkeypatch):
    demande = {"message": "Publier E1 ?", "schema": {"properties": {"confirmer": {"type": "boolean", "title": "Publier"}}}}
    with importer_client(client):
        from pharos_client import entrees

        for saisie, attendu in (("oui", True), ("non", False), ("", False)):
            monkeypatch.setattr(builtins, "input", lambda invite, s=saisie: s)
            assert entrees.demander_utilisateur(demande) == {"action": "accept", "content": {"confirmer": attendu}}

        def sans_terminal(invite):
            raise EOFError

        monkeypatch.setattr(builtins, "input", sans_terminal)
        assert entrees.demander_utilisateur(demande) == {"action": "decline", "content": None}


async def test_canal_et_outils_du_lab12(mocks_servis, monkeypatch, capsys):
    from outils import lab12

    monkeypatch.setenv("CANAL_URL", f"{mocks_servis}/canal")
    accuse = await canal.publier("ESC-2026-0412", "orange", "exploitation", "note")
    assert accuse["alerte_id"] == "ALR-0001" and lab12.alertes() == {"exploitation": 1}
    assert lab12.main(["compteur"]) == 0
    assert "Alertes réellement parties : 1" in capsys.readouterr().out
    assert lab12.main(["canal"]) == 0 and lab12.alertes() == {}
    with pytest.raises(httpx.HTTPStatusError):
        await canal.publier("", "orange", "exploitation")


async def test_clients_du_lab12(mocks_servis, capsys):
    from outils import lab12

    publiees = []
    mcp = serveur(publiees)
    with servir(mcp.http_app(path="/mcp", json_response=True)) as url:
        await lab12._clients(f"{url}/mcp", "jeton-exploitation", "complet")
        complet = capsys.readouterr().out
        await lab12._clients(f"{url}/mcp", "jeton-exploitation", "defaut")
        defaut = capsys.readouterr().out
    assert "input_required" in complet and "requestState" in complet and "Compteur du canal : 0 → 0" in complet
    assert '"publiee":false' in defaut.replace(" ", "") and publiees == []


def test_depart_cibles_et_deux_instances_du_lab12():
    assert (labs.DEPARTS[12], labs.SORTIES[12]) == ("is3-fin", "sr3-fin")
    assert labs.DEMARRAGE[12] == ["lab8-base", "lab10-mocks", "lab12-deux-instances"] and labs.PORTS_PRETS[12] == [8203]
    cibles = set(re.findall(r"^([a-z0-9-]+):", Path("mk/lab12.mk").read_text(encoding="utf-8"), re.MULTILINE))
    assert {"lab12-canal", "lab12-compteur", "lab12-clients", "lab12-scaffold", "lab12-deux-instances",
            "lab12-verifier"} <= cibles
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    assert "repartiteur-ops:8000@8203" in compose and "127.0.0.1:8203:8203" in compose
    services = Path("compose/lab12.yaml").read_text(encoding="utf-8")
    assert all(s in services for s in ("pharos-ops-a:", "pharos-ops-b:", "repartiteur-ops:"))
    for fichier in ("compose.yaml", "compose/commun/base.yaml"):
        cle = re.search(r'CLE_ETAT: "\$\{CLE_ETAT:-([^}]+)\}"', Path(fichier).read_text(encoding="utf-8")).group(1)
        assert len(cle.encode()) >= 32, fichier                    # le SDK refuse une clé plus courte
