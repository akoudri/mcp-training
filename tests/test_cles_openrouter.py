import json
from datetime import date

import httpx

from outils import cles_openrouter as co


CLES = [
    {"hash": "h1", "name": "pharos-binome-1", "limit": 5, "usage": 1.2},
    {"hash": "hx", "name": "autre-projet", "limit": 50, "usage": 3},
]


def api(etat, cles=CLES, taille_page=100):
    def g(r: httpx.Request):
        assert r.headers["authorization"] == "Bearer gestion"
        if r.method == "POST":
            corps = json.loads(r.content)
            etat.append(corps)
            n = len(etat)
            return httpx.Response(201, json={"key": f"sk-or-v1-{n}", "data": {"hash": f"h{n}", "name": corps["name"]}})
        if r.method == "GET":
            offset = int(r.url.params.get("offset", 0))
            etat.append(("GET", offset))
            return httpx.Response(200, json={"data": cles[offset:offset + taille_page]})
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
    assert [a for a in appels if a[0] == "DELETE"] == [("DELETE", "/api/v1/keys/h1")]


def test_etat():
    lignes = co.etat(api([]))
    assert lignes == [{"nom": "pharos-binome-1", "plafond": 5, "consomme": 1.2}]


def test_les_cles_sont_lues_sur_toutes_les_pages():
    cles = [{"hash": f"h{n}", "name": f"pharos-binome-{n}", "limit": 5, "usage": 0} for n in range(1, 4)]
    cles.insert(1, {"hash": "hx", "name": "autre-projet", "limit": 50, "usage": 3})
    appels = []
    lignes = co.etat(api(appels, cles=cles, taille_page=2))
    assert [ligne["nom"] for ligne in lignes] == ["pharos-binome-1", "pharos-binome-2", "pharos-binome-3"]
    assert ("GET", 0) in appels and ("GET", 2) in appels


def test_refus_d_openrouter_affiche_un_message_francais(monkeypatch, capsys):
    def refus(r: httpx.Request):
        return httpx.Response(401, json={"error": {"message": "No auth credentials found"}})
    vrai_client = httpx.Client
    monkeypatch.setattr(co.httpx, "Client", lambda **kw: vrai_client(**kw, transport=httpx.MockTransport(refus)))
    monkeypatch.setenv("OPENROUTER_CLE_GESTION", "mauvaise")
    assert co.main(["etat"]) == 1
    erreur = capsys.readouterr().err
    assert "OpenRouter a refusé la requête (HTTP 401) : vérifier OPENROUTER_CLE_GESTION" in erreur
    assert "Traceback" not in erreur
