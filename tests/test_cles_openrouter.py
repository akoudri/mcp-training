import json
from datetime import date

import httpx

from outils import cles_openrouter as co


def api(etat):
    def g(r: httpx.Request):
        assert r.headers["authorization"] == "Bearer gestion"
        if r.method == "POST":
            corps = json.loads(r.content)
            etat.append(corps)
            n = len(etat)
            return httpx.Response(201, json={"key": f"sk-or-v1-{n}", "data": {"hash": f"h{n}", "name": corps["name"]}})
        if r.method == "GET":
            return httpx.Response(200, json={"data": [
                {"hash": "h1", "name": "pharos-binome-1", "limit": 5, "usage": 1.2},
                {"hash": "hx", "name": "autre-projet", "limit": 50, "usage": 3}]})
        if r.method == "DELETE":
            etat.append(("DELETE", r.url.path))
            return httpx.Response(200, json={"deleted": True})
    return httpx.Client(base_url=co.API, transport=httpx.MockTransport(g), headers={"Authorization": "Bearer gestion"})


def test_creer_ecrit_un_env_par_binome(tmp_path):
    appels = []
    chemins = co.creer(api(appels), binomes=5, plafond=5, expiration=date(2026, 10, 10), sortie=tmp_path)
    assert [p.name for p in chemins] == [f"binome-{n}.env" for n in range(1, 6)]
    assert "OPENROUTER_API_KEY=sk-or-v1-3" in (tmp_path / "binome-3.env").read_text()
    assert "PHAROS_BINOME=3" in (tmp_path / "binome-3.env").read_text()
    assert appels[0]["name"] == "pharos-binome-1" and appels[0]["limit"] == 5


def test_revoquer_ne_touche_que_les_cles_pharos():
    appels = []
    assert co.revoquer(api(appels)) == 1
    assert appels == [("DELETE", "/api/v1/keys/h1")]


def test_etat():
    lignes = co.etat(api([]))
    assert lignes == [{"nom": "pharos-binome-1", "plafond": 5, "consomme": 1.2}]
