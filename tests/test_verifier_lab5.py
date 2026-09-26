from dataclasses import dataclass, field

from outils.verifier.commun import Etat
from tests.aides import serveur_demo, servir


async def test_sans_ouvrir_dossier(monkeypatch):
    monkeypatch.setenv("CLE_SERVEUR", "cle-de-test")
    from outils.verifier import lab5
    with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
        rapport = await lab5.v.executer(url=f"{base}/mcp", sans_modele=True)
    echec = next(r for r in rapport.resultats if r.etat is Etat.ECHEC)
    assert "ouvrir_dossier" in echec.detail


@dataclass
class _FauxBloc:
    text: str


@dataclass
class _FauxResultat:
    is_error: bool
    content: list = field(default_factory=list)


def test_refus_utile_accepte_ouvrez_a_nouveau():
    from outils.verifier.lab5 import _refus_utile
    r = _FauxResultat(True, [_FauxBloc("Ouvrez à nouveau le dossier de l'escale.")])
    assert _refus_utile(r) is None


def test_refus_utile_rejette_message_muet():
    from outils.verifier.lab5 import _refus_utile
    r = _FauxResultat(True, [_FauxBloc("Handle invalide.")])
    assert _refus_utile(r) is not None
