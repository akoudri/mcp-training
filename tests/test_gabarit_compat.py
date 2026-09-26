"""Le module compat fourni au LAB 3 (gabarit) : poignée de main 2025-11-25, sessions, journal."""

import json
from pathlib import Path

import pytest

from tests.aides import charger_module

compat = charger_module(Path("gabarits/lab03/serveurs/pharos_legacy/compat.py"), "gabarit_lab3_compat")


def test_sessions():
    s = compat.Sessions()
    sid = s.ouvrir("vscode")
    assert s.lire(sid) == {"client": "vscode", "curseur": None}
    assert s.lire(None) is None and s.lire("inconnue") is None
    assert s.fermer(sid) and not s.fermer(sid)


def test_repondre_initialize_ouvre_une_session():
    s = compat.Sessions()
    r = compat.repondre_initialize(s, 1, {"clientInfo": {"name": "ancien"}}, {"tools": {}}, {"name": "x", "version": "1"})
    corps = json.loads(r.body)
    assert corps["result"]["protocolVersion"] == "2025-11-25"
    assert s.lire(r.headers["mcp-session-id"])["client"] == "ancien"


@pytest.mark.parametrize("session_id, statut", [(None, 400), ("inconnue", 404)])
def test_refus_sans_session(session_id, statut):
    r = compat.refuser_sans_session(3, session_id)
    assert r.status_code == statut and json.loads(r.body)["error"]["code"] == -32600


def test_journal_une_ligne_json_par_appel(tmp_path, monkeypatch):
    chemin = tmp_path / "sous" / "dossier" / "journal.jsonl"
    monkeypatch.setenv("PHAROS_JOURNAL_LEGACY", str(chemin))
    monkeypatch.setenv("PHAROS_INSTANCE", "b")
    compat.journaliser("2025-11-25", "initialize")
    compat.journaliser("2026-07-28", "tools/call", "pharos-test", "etat_escale")
    lignes = [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines()]
    assert [l["revision"] for l in lignes] == ["2025-11-25", "2026-07-28"]
    assert lignes[1] | {"horodatage": None} == {"horodatage": None, "instance": "b", "revision": "2026-07-28",
                                                "methode": "tools/call", "outil": "etat_escale", "client": "pharos-test"}
    assert lignes[0]["horodatage"].startswith("2026-10-06")          # horloge fictive
