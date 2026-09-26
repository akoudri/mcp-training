"""Vérificateur du LAB 6 : relit avant.md et apres.md, confronte au catalogue servi."""

import pytest

from outils import mesure_quai
from outils.verifier.commun import Etat
from tests.aides import servir
from tests.test_mesure_quai import ORIGINE as NOMS_D_ORIGINE, _modele_qui_choisit, serveur_quai

QUESTIONS = ["Quelles escales sont prévues aujourd'hui ?", "Quel est le tirant d'eau maximal du quai 3 ?",
             "Le Vent d'Autan a-t-il un créneau jeudi matin ?", "Quelles escales sont prévues au quai 3 demain ?",
             "À quelle heure le Vent d'Autan peut-il accoster jeudi ?"]
ORIGINE = ["get_data", "info_quai", "search", "get_data_2", "process"]
RENOMMES = ["escales_du_jour", "caracteristiques_quai", "creneaux_du_navire", "escales_du_quai", "heure_accostage"]


async def _mesure(serveur, choisis: list[str]) -> str:
    executions, noms = await mesure_quai.mesurer(serveur, completer=_modele_qui_choisit(dict(zip(QUESTIONS, choisis))))
    return mesure_quai.rapport(executions, noms)


def _origine():
    return serveur_quai(NOMS_D_ORIGINE)


async def _verifier(tmp_path, monkeypatch, serveur, **fichiers):
    from outils.verifier import lab6
    (tmp_path / "labs" / "lab6").mkdir(parents=True)
    for nom, texte in fichiers.items():
        (tmp_path / "labs" / "lab6" / f"{nom}.md").write_text(texte, encoding="utf-8")
    monkeypatch.setattr(lab6, "RACINE", tmp_path)
    with servir(serveur.http_app(path="/mcp", json_response=True)) as base:
        return await lab6.v.executer(url=f"{base}/mcp", sans_modele=True)


def _etat(rapport, debut: str):
    return next(r for r in rapport.resultats if r.libelle.startswith(debut))


async def test_rien_de_mesure(tmp_path, monkeypatch):
    rapport = await _verifier(tmp_path, monkeypatch, _origine())
    avant = _etat(rapport, "`avant.md`")
    assert avant.etat is Etat.ECHEC and "make lab6-mesurer SORTIE=labs/lab6/avant.md" in avant.detail
    assert _etat(rapport, "La réécriture").etat is Etat.OK
    assert rapport.code_sortie == 1


async def test_reecriture_qui_progresse_de_deux(tmp_path, monkeypatch):
    avant = await _mesure(_origine(), ["get_data", "info_quai", "search", "get_data", "search"])
    apres = await _mesure(serveur_quai(), RENOMMES)
    rapport = await _verifier(tmp_path, monkeypatch, serveur_quai(), avant=avant, apres=apres)
    assert [r for r in rapport.resultats if r.etat is Etat.ECHEC] == [], rapport.texte()
    assert "gagnées : 4, 5" in _etat(rapport, "Critère décisif").detail
    assert "Questions ratées dans avant.md : 4, 5" in _etat(rapport, "Chaque échec").detail


async def test_progression_insuffisante(tmp_path, monkeypatch):
    avant = await _mesure(_origine(), ["get_data", "info_quai", "search", "get_data", "search"])
    apres = await _mesure(serveur_quai(), RENOMMES[:4] + ["creneaux_du_navire"])
    rapport = await _verifier(tmp_path, monkeypatch, serveur_quai(), avant=avant, apres=apres)
    decisif = _etat(rapport, "Critère décisif")
    assert decisif.etat is Etat.ECHEC and "3/5 → 4/5" in decisif.detail


async def test_plafond_a_cinq_sur_cinq_avec_un_seul_rate_au_depart(tmp_path, monkeypatch):
    """avant.md ne ratait qu'une question (4/5) : l'écart de deux est impossible dès qu'apres.md atteint 5/5."""
    avant = await _mesure(_origine(), ["get_data", "info_quai", "search", "get_data", "process"])
    apres = await _mesure(serveur_quai(), RENOMMES)
    rapport = await _verifier(tmp_path, monkeypatch, serveur_quai(), avant=avant, apres=apres)
    decisif = _etat(rapport, "Critère décisif")
    assert decisif.etat is Etat.ECHEC
    assert "5/5 atteint" in decisif.detail
    assert "n'a raté que 1 question" in decisif.detail
    assert "variance du modèle" in decisif.detail
    assert "le signaler au formateur" in decisif.detail
    assert "ne pas remesurer avant.md" in decisif.detail
    assert "Reprendre le diagnostic" not in decisif.detail


async def test_schemas_modifies(tmp_path, monkeypatch):
    rapport = await _verifier(tmp_path, monkeypatch, serveur_quai(filtre_decrit=True))
    r = _etat(rapport, "La réécriture")
    assert r.etat is Etat.ECHEC and "get_data_2" in r.detail


async def test_apres_mesure_sur_l_ancien_catalogue(tmp_path, monkeypatch):
    avant = await _mesure(_origine(), ORIGINE)
    rapport = await _verifier(tmp_path, monkeypatch, serveur_quai(), avant=avant, apres=avant)
    r = _etat(rapport, "`apres.md`")
    assert r.etat is Etat.ECHEC and "après la réécriture" in r.detail


async def test_avant_mesure_apres_reecriture(tmp_path, monkeypatch):
    apres = await _mesure(serveur_quai(), RENOMMES)
    rapport = await _verifier(tmp_path, monkeypatch, serveur_quai(), avant=apres, apres=apres)
    r = _etat(rapport, "`avant.md`")
    assert r.etat is Etat.ECHEC and "catalogue fourni" in r.detail
    assert "git stash" in r.detail and "git stash pop" in r.detail
    assert "git checkout -- labs/lab6/avant.md" in r.detail
    # Le critère décisif ne doit pas donner un conseil trompeur en repartant d'un avant.md invalide.
    decisif = _etat(rapport, "Critère décisif")
    assert decisif.etat is Etat.ECHEC
    assert decisif.detail == "avant.md n'est pas une mesure initiale valable : corriger d'abord le premier critère."


@pytest.mark.parametrize("texte", ["", "| 1 | a | b | c | d |\n"])
async def test_fichier_retouche_a_la_main(tmp_path, monkeypatch, texte):
    rapport = await _verifier(tmp_path, monkeypatch, _origine(), avant=texte)
    r = _etat(rapport, "`avant.md`")
    assert r.etat is Etat.ECHEC and "sans le retoucher à la main" in r.detail
