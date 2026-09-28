"""Durcissement admin de la salle : avec SALLE_CLE_ADMIN, les routes /_ exigent la clé dès le démarrage.
Sans la variable, le comportement d'origine est conservé (back-compat des tests et de la CI). Ni base, ni modèle."""

import importlib

from starlette.testclient import TestClient


def _service(monkeypatch, tmp_path, cle_admin=None):
    monkeypatch.setenv("SALLE_JOURNAL", str(tmp_path / "journal.jsonl"))
    if cle_admin is None:
        monkeypatch.delenv("SALLE_CLE_ADMIN", raising=False)
    else:
        monkeypatch.setenv("SALLE_CLE_ADMIN", cle_admin)
    from serveurs.salle import app as S
    importlib.reload(S)
    return S, TestClient(S.app)


def test_config_exige_la_cle_des_le_premier_appel(monkeypatch, tmp_path):
    S, client = _service(monkeypatch, tmp_path, cle_admin="cle-admin-test")
    # sans jeton : refusé dès le premier /_config (la course est fermée)
    assert client.post("/_config", json={"n": 5}).status_code == 403
    # avec la clé : accepté
    r = client.post("/_config", json={"n": 5}, headers={"X-Jeton": "cle-admin-test"})
    assert r.status_code == 200
    # la clé d'admin reste le jeton formateur (b == 0) après configuration
    assert r.json()["jetons"]["cle-admin-test"] == 0
    # /_manche et /_raz l'exigent aussi
    assert client.post("/_manche", json={"manche": 2}).status_code == 403
    assert client.post("/_manche", json={"manche": 2}, headers={"X-Jeton": "cle-admin-test"}).status_code == 200
    assert client.post("/_raz", headers={"X-Jeton": "cle-admin-test"}).status_code == 200


def test_sans_variable_le_comportement_est_conserve(monkeypatch, tmp_path):
    S, client = _service(monkeypatch, tmp_path, cle_admin=None)
    # back-compat : premier /_config ouvert (tests, CI salle-locale)
    assert client.post("/_config", json={"n": 5}).status_code == 200
