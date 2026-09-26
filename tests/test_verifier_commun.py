import pytest

from outils.verifier import __main__ as lanceur
from outils.verifier.commun import Echec, Etat, Verification
from tests.aides import serveur_demo, servir


@pytest.fixture(scope="module")
def url():
    with servir(serveur_demo().http_app(path="/mcp", json_response=True)) as base:
        yield f"{base}/mcp"


def verification(journal: list) -> Verification:
    v = Verification("LAB 99 — essai", "http://inutilise/mcp", "make lab99-up")

    @v.critere("Premier critère, réussi.")
    async def _(ctx):
        journal.append("1")
        ctx.cache["vu"] = True

    @v.critere("Deuxième critère, en échec.")
    def _(ctx):
        journal.append("2")
        raise Echec("il manque l'énumération sur sujet.\nAjouter Literal[...].")

    @v.critere("Troisième critère, qui plante.")
    def _(ctx):
        raise RuntimeError("panne du serveur")

    @v.critere("Quatrième critère, avec le modèle.", modele=True)
    def _(ctx):
        journal.append("4")
        return "banc : 3/3"

    @v.constat("Cinquième : le résultat est consigné.")
    def _(ctx):
        assert ctx.cache["vu"]
        return "Ouvrir labs/lab99/resultats.md et le compléter."

    return v


async def test_ordre_etats_et_code(url):
    journal = []
    rapport = await verification(journal).executer(url=url, sans_modele=False)
    assert [r.etat for r in rapport.resultats] == [Etat.OK, Etat.ECHEC, Etat.ECHEC, Etat.OK, Etat.CONSTAT]
    assert journal == ["1", "2", "4"]
    assert rapport.code_sortie == 1
    assert rapport.resultats[3].detail == "banc : 3/3"


async def test_exception_inattendue_isolee(url):
    rapport = await verification([]).executer(url=url, sans_modele=False)
    plante = rapport.resultats[2]
    assert plante.etat is Etat.ECHEC and "erreur inattendue" in plante.detail and "panne du serveur" in plante.detail
    assert rapport.resultats[3].etat is Etat.OK        # la suite s'est exécutée


async def test_sans_modele_saute(url):
    journal = []
    rapport = await verification(journal).executer(url=url, sans_modele=True)
    assert rapport.resultats[3].etat is Etat.SAUTE and "4" not in journal


async def test_sans_modele_lu_dans_l_environnement(url, monkeypatch):
    monkeypatch.setenv("SANS_MODELE", "1")
    rapport = await verification([]).executer(url=url)
    assert rapport.resultats[3].etat is Etat.SAUTE


async def test_prealable_serveur_absent():
    journal = []
    rapport = await verification(journal).executer(url="http://127.0.0.1:1/mcp", sans_modele=True)
    assert len(rapport.resultats) == 1 and rapport.resultats[0].etat is Etat.ECHEC
    assert "make lab99-up" in rapport.resultats[0].detail and journal == []
    assert rapport.code_sortie == 1


async def test_rendu(url):
    texte = (await verification([]).executer(url=url, sans_modele=True)).texte()
    assert texte.startswith("LAB 99 — essai")
    assert "  ❌ Deuxième critère, en échec.\n       → il manque l'énumération sur sujet.\n       → Ajouter Literal[...]." in texte
    assert "Bilan : 1 ✅ · 2 ❌ · 1 👁 · 1 ⏭" in texte


def test_lab_inconnu(capsys):
    assert lanceur.main(["lab99"]) == 2
    assert "Aucun vérificateur" in capsys.readouterr().out
