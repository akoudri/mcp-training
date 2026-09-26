from pathlib import Path

import pytest
from fastmcp import FastMCP

from pharos import openrouter
from tests.aides import importer_client, serveur_demo

GABARIT = Path("gabarits/lab04/client")


@pytest.fixture
def client():
    with importer_client(GABARIT):
        import pharos_client.boucle as boucle
        import pharos_client.modele as modele
        import pharos_client.trace as trace
        import pharos_client.transport as transport
        yield transport, modele, trace, boucle


def test_session_outils_et_appels(client):
    transport, *_ = client
    with transport.Session(serveur_demo()) as s:
        outils = s.lister_outils()
        ok = s.appeler("etat", {"escale_id": "ESC-2026-0412"})
        ko = s.appeler("etat", {"escale_id": "ESC-2026-9999"})
    assert {o["function"]["name"] for o in outils} == {"etat", "echec"}
    assert not ok.est_erreur and '"quai":3' in ok.texte.replace(" ", "") and ok.octets == len(ok.texte.encode())
    assert ko.est_erreur and "Escale inconnue." in ko.texte


def test_session_ressources(client):
    transport, *_ = client
    mcp = FastMCP("r")

    @mcp.resource("pharos://essai/doc", mime_type="text/plain")
    def doc() -> str:
        return "bonjour"

    with transport.Session(mcp) as s:
        [r] = s.lister_ressources()
        texte = s.lire_ressource("pharos://essai/doc")
    assert r["uri"] == "pharos://essai/doc" and r["mime_type"] == "text/plain" and texte == "bonjour"


def test_session_serveur_injoignable(client):
    transport, *_ = client
    with pytest.raises(Exception):
        with transport.Session("http://127.0.0.1:1/mcp"):
            pass


def test_modele_reexporte(client):
    _, modele, *_ = client
    assert modele.completer is openrouter.completer and modele.estimer_tokens is openrouter.estimer_tokens


def test_afficher_arbre(client):
    _, _, trace, _ = client
    E = trace.Enregistrement
    t = [E("c0ffee", 1, "rechercher_clause", {"sujet": "penalites"}, 12.3, 480, 1800),
         E("c0ffee", 1, "lister_documents", {"cle_api": "***"}, 3.0, 90, 1800, erreur=True),
         E("c0ffee", 2, "rechercher_clause", {"sujet": "delais"}, 8.0, 400, 2600)]
    vu = []
    texte = trace.afficher(t, sortie=vu.append)
    assert vu == [texte]
    assert texte.splitlines()[0] == "exécution c0ffee — 3 appel(s), 2 tour(s)"
    assert "├─ tour 1 · contexte 1800 tokens" in texte and "└─ tour 2" in texte
    assert "lister_documents(cle_api=***) · 3 ms · 90 o · isError" in texte
    assert trace.afficher([], sortie=vu.append).startswith("(trace vide")


def test_squelette_pas_encore_ecrit(client):
    *_, boucle = client
    with pytest.raises(NotImplementedError):
        boucle.executer("question")
    assert issubclass(boucle.BudgetDepasse, boucle.ArretBoucle)
    assert boucle.EchecNonRecuperable("m", [1]).trace == [1]
