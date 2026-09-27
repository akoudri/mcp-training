import gc
import logging
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


def test_session_injoignable_ne_journalise_pas_de_tache_perdue(client, caplog):
    """Échec de connexion : la tâche de maintien qui échoue avant d'être prête ne doit jamais être
    récupérée sans que son exception ait été lue — sinon asyncio journalise du bruit sur stderr."""
    transport, *_ = client
    with caplog.at_level(logging.DEBUG, logger="asyncio"):
        with pytest.raises(Exception):
            with transport.Session("http://127.0.0.1:1/mcp"):
                pass
        gc.collect()  # force la collecte du cycle Session -> tâche -> coroutine -> Session
    bruit = [r.getMessage() for r in caplog.records
             if r.name == "asyncio" and "Task exception was never retrieved" in r.getMessage()]
    assert not bruit, bruit


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


def test_delai_depasse_devient_une_erreur_lisible(client):
    import asyncio

    transport, *_ = client
    mcp = FastMCP("lent")

    @mcp.tool
    async def lent() -> str:
        """Répond trop tard."""
        await asyncio.sleep(3)
        return "fini"

    with transport.Session(mcp, delai_s=1) as s:
        r = s.appeler("lent", {})
    assert r.est_erreur and "budget de tour (1 s)" in r.texte and "ne rien en conclure" in r.texte


def test_delai_par_defaut_de_salle(client, monkeypatch):
    transport, *_ = client
    assert transport.DELAI_DEFAUT_S == 20.0
    with transport.Session(serveur_demo()) as s:
        assert s.delai_s == 20.0


def test_correlation_transmise_dans_meta(client):
    from fastmcp import Context

    transport, *_ = client
    mcp = FastMCP("meta")

    @mcp.tool
    def correlation(ctx: Context) -> str:
        """Rend la corrélation reçue."""
        meta = ctx.request_context.meta
        brut = meta.model_dump(by_alias=True) if hasattr(meta, "model_dump") else dict(meta or {})
        return brut.get("pharos/correlation") or "aucune"

    with transport.Session(mcp) as s:
        assert s.appeler("correlation", {}, correlation="c-7").texte == "c-7"
        assert s.appeler("correlation", {}).texte == "aucune"


def test_jeton_porteur(client, monkeypatch):
    from pharos import autorisation
    from tests.aides import servir

    transport, *_ = client
    mcp = FastMCP("id", auth=autorisation.verificateur())

    @mcp.tool
    def qui() -> str:
        """Nom de l'appelant."""
        return autorisation.identite().nom

    with servir(mcp.http_app(path="/mcp", json_response=True)) as url:
        with transport.Session(f"{url}/mcp", jeton="jeton-iroise") as s:
            assert s.appeler("qui", {}).texte == "Consignation Iroise"
        monkeypatch.setenv("PHAROS_JETON", "jeton-rance")
        with transport.Session(f"{url}/mcp") as s:
            assert s.appeler("qui", {}).texte == "Agence Maritime Rance"
            assert s.url == f"{url}/mcp"


def test_trace_resultat_et_serveur(client):
    _, _, trace, _ = client
    e = trace.Enregistrement("c", 1, "outil", {}, 1.0, 2, 3)
    assert (e.resultat, e.serveur) == ("", "")
    assert trace.borner("court") == "court"
    long = trace.borner("é" * 5000)
    assert long.startswith("é" * 4000) and long.endswith("[10000 octets au total]")


def test_sans_jeton_le_refus_dit_quoi_faire(client, monkeypatch):
    from pharos import autorisation
    from tests.aides import servir

    transport, *_ = client
    monkeypatch.delenv("PHAROS_JETON", raising=False)
    mcp = FastMCP("id", auth=autorisation.verificateur())
    with servir(mcp.http_app(path="/mcp", json_response=True)) as url:
        with pytest.raises(PermissionError, match="PHAROS_JETON"):
            with transport.Session(f"{url}/mcp"):
                pass
