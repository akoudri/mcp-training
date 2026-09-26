import httpx
import pytest

from outils import doctor

URLS = {"observateur": "http://observateur:8081/"}


def client(gestionnaire):
    return httpx.Client(transport=httpx.MockTransport(gestionnaire))


def test_socle_ok():
    v = doctor.verifier_socle(client(lambda r: httpx.Response(200)), URLS)
    assert v.ok and v.nom == "socle"


def test_socle_service_absent():
    urls = {"observateur": "http://observateur:8081/", "autre": "http://autre:1234/"}

    def g(r):
        if r.url.host == "autre":
            raise httpx.ConnectError("nom inconnu")
        return httpx.Response(401)

    v = doctor.verifier_socle(client(g), urls)
    assert not v.ok and "autre" in v.detail and "make up" in v.detail


@pytest.mark.parametrize("cle", [None, ""])
def test_modele_cle_absente(cle):
    v = doctor.verifier_modele(client(lambda r: httpx.Response(200)), cle, "google/gemini-3.6-flash")
    assert not v.ok and "absente" in v.detail and ".env" in v.detail


@pytest.mark.parametrize("statut, attendu", [(401, "invalide"), (402, "crédit"), (404, "modèle")])
def test_modele_erreurs_http(statut, attendu):
    v = doctor.verifier_modele(client(lambda r: httpx.Response(statut, json={"error": {"message": "x"}})), "sk-or-x", "m")
    assert not v.ok and attendu in v.detail


def test_modele_sans_appel_d_outil():
    reponse = {"choices": [{"message": {"content": "Il est midi.", "tool_calls": None}}]}
    v = doctor.verifier_modele(client(lambda r: httpx.Response(200, json=reponse)), "sk-or-x", "m")
    assert not v.ok and "outil" in v.detail


def test_modele_ok_et_requete_conforme():
    vu = {}

    def g(r):
        import json
        vu["corps"] = json.loads(r.content)
        vu["auth"] = r.headers["authorization"]
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [
            {"id": "1", "type": "function", "function": {"name": "donner_l_heure", "arguments": "{}"}}]}}]})
    v = doctor.verifier_modele(client(g), "sk-or-x", "google/gemini-3.6-flash")
    assert v.ok
    assert vu["auth"] == "Bearer sk-or-x"
    assert vu["corps"]["model"] == "google/gemini-3.6-flash"
    assert "parallel_tool_calls" not in vu["corps"]
    assert vu["corps"]["tools"][0]["function"]["name"] == "donner_l_heure"


async def test_serveur_injoignable():
    v = await doctor.verifier_serveur("http://127.0.0.1:1/mcp")
    assert not v.ok and "make lab0-up" in v.detail
