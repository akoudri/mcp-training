"""LAB 15 : le vérificateur sur la solution (tout ✅) et sur le gabarit (❌ là où le binôme doit travailler), le
rapport de la solution sur les résultats figés du kit, et les cas de la solution joués de bout en bout par le
harnais contre les vrais serveurs de la solution, avec un modèle simulé."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from outils.labs import copier
from outils.verifier.commun import Etat
from tests.aides import DSN_TEST, RACINE_KIT, base_requise, etat_complet, importer_client
from tests.solutions.test_lab13 import trois_serveurs

pytestmark = pytest.mark.skipif(not Path("solutions/lab15").is_dir(),
                                reason="instantanés présents sur la branche solutions uniquement")
KIT = RACINE_KIT / "outils" / "evaluation" / "exemples"


@pytest.fixture(scope="module")
def etat(tmp_path_factory):
    return etat_complet(tmp_path_factory.mktemp("etat-lab15"), 15)


async def verifier(etat: Path, monkeypatch, tmp_path):
    from donnees.base.__main__ import charger
    from outils.verifier import lab15

    await charger(DSN_TEST, politique=etat / "labs" / "lab9" / "politique.sql")
    monkeypatch.setenv("CLE_ETAT", "pharos-salle-2026-cle-etat-mrtr-partagee")
    monkeypatch.setattr(lab15, "RACINE", etat)
    monkeypatch.setattr(lab15, "CONFIG", tmp_path / "serveurs.json")
    monkeypatch.delenv("PHAROS_MODELE", raising=False)
    try:
        with trois_serveurs(etat, tmp_path / "serveurs.json") as urls:
            rapport = await lab15.v.executer(url=urls["pharos-ops"], sans_modele=True)
    finally:
        await charger(DSN_TEST, politique=Path("/nulle-part.sql"))
    return rapport


def echecs(rapport) -> dict[str, str]:
    return {r.libelle: r.detail for r in rapport.resultats if r.etat is Etat.ECHEC}


@base_requise
async def test_la_solution_passe_son_verificateur(etat, base_de_test, mocks_servis, monkeypatch, tmp_path):
    rapport = await verifier(etat, monkeypatch, tmp_path)
    assert echecs(rapport) == {}, rapport.texte()


@base_requise
async def test_le_gabarit_echoue(base_de_test, mocks_servis, monkeypatch, tmp_path):
    etat = etat_complet(tmp_path / "etat", 14)
    copier(RACINE_KIT / "gabarits" / "lab15", etat, ecraser=False)
    rapport = await verifier(etat, monkeypatch, tmp_path)
    rates = " ".join(echecs(rapport))
    for debut in ("Dix cas", "Le taux de référence", "Au moins un cas instable", "La chaîne d'évaluation",
                  "« Rien à lancer »", "Critère décisif"):
        assert debut in rates, rapport.texte()


@base_requise
async def test_la_regression_posee_se_voit_dans_la_chaine(etat, base_de_test, mocks_servis, monkeypatch, tmp_path):
    from outils.evaluation import regression

    serveur = etat / "serveurs" / "pharos_ops" / "serveur.py"
    sain = serveur.read_text(encoding="utf-8")
    serveur.write_text(regression.appliquer(sain), encoding="utf-8")
    try:
        rapport = await verifier(etat, monkeypatch, tmp_path)
    finally:
        serveur.write_text(sain, encoding="utf-8")
    assert "le catalogue agrégé a changé" in echecs(rapport)["« Rien à lancer » : sans changement de modèle, de "
                                                            "catalogue ni de prompt, la chaîne reste verte sans jouer."]


@pytest.mark.parametrize("resultat, code", [("sain", 0), ("regresse", 1)])
def test_le_rapport_de_la_solution(etat, resultat, code):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(str(p) for p in (etat / "src", etat))}
    sortie = subprocess.run([sys.executable, str(etat / "evaluation" / "rapport.py"), str(KIT / f"{resultat}.json"),
                             "--reference", str(KIT / "reference.json")], capture_output=True, text=True, env=env)
    assert sortie.returncode == code, sortie.stdout + sortie.stderr
    if code:
        assert "RÉGRESSION penalites-vent-autan (multi) : 3/3 → 0/3" in sortie.stdout
        assert "ROUGE multi" in sortie.stdout and "ROUGE simple" not in sortie.stdout


def test_un_jeu_partiel_ne_fait_pas_chuter_les_familles_non_jouees(etat):
    sys.path.insert(0, str(etat / "evaluation"))
    try:
        import importlib
        rapport = importlib.import_module("rapport")
        from outils.evaluation import resultats
        ref = resultats.charger(KIT / "reference.json")
        partiel = {**ref, "cas": [c for c in ref["cas"] if c["id"] == "penalites-escale-0409"]}
        lignes, rouge = rapport.comparer(partiel, ref)
        assert not rouge and any("non joué" in l for l in lignes)
    finally:
        sys.path.remove(str(etat / "evaluation"))
        sys.modules.pop("rapport", None)


def test_un_cas_qui_s_effondre_met_sa_famille_au_rouge_pas_un_cas_instable(etat):
    sys.path.insert(0, str(etat / "evaluation"))
    try:
        import importlib
        rapport = importlib.import_module("rapport")
        from outils.evaluation import resultats
        ref = resultats.charger(KIT / "reference.json")
        simple = next(c["id"] for c in ref["cas"] if c["famille"] == "simple")

        def avec(reussites):
            return {**ref, "cas": [{**c, "reussites": reussites, "reussi": reussites >= 2}
                                   for c in ref["cas"] if c["id"] == simple]}

        base = {**ref, "cas": [{**c, "reussites": 3, "reussi": True} for c in ref["cas"] if c["id"] == simple]}
        _, rouge = rapport.comparer(avec(0), base)
        assert rouge
        _, rouge = rapport.comparer(avec(2), base)
        assert not rouge
    finally:
        sys.path.remove(str(etat / "evaluation"))
        sys.modules.pop("rapport", None)


@base_requise
async def test_les_cas_de_la_solution_se_jouent_de_bout_en_bout(etat, base_de_test, mocks_servis, monkeypatch, tmp_path):
    """Le harnais, sans parallélisme, sur deux cas de la solution : les vrais serveurs, un modèle simulé qui suit
    le scénario attendu, la confirmation refusée — la notation tombe juste dans les deux sens."""
    import asyncio

    from donnees.base.__main__ import charger
    from outils.evaluation import cas as cas_mod
    from outils.evaluation import harnais
    from outils.verifier.modele_simule import ModeleSimule, appel

    await charger(DSN_TEST, politique=etat / "labs" / "lab9" / "politique.sql")
    monkeypatch.setenv("CLE_ETAT", "pharos-salle-2026-cle-etat-mrtr-partagee")
    tous = {c.id: c for c in cas_mod.charger(etat / "evaluation" / "cas", etat)}
    plan = json.dumps([{"etape": 1, "outil": "navire_par_nom", "raison": "r"},
                       {"etape": 2, "outil": "rechercher_clause", "raison": "r"}])
    juste = [plan, [appel("a1", "navire_par_nom", {"nom": "Vent d'Autan"})],
             [appel("a2", "rechercher_clause", {"escale_id": "ESC-2026-0412", "sujet": "penalites"})],
             "Pénalité : 1 850 € par heure de retard entamée, au-delà d'une franchise de 6 heures."]
    try:
        with trois_serveurs(etat, tmp_path / "serveurs.json"), importer_client(etat / "client"):
            cas = tous["penalites-vent-autan"]
            with ModeleSimule(juste):
                bon = await asyncio.to_thread(harnais.executer_une, cas, tmp_path / "serveurs.json")
            with ModeleSimule([plan, "Environ 1 800 € par heure, probablement."]):
                faux = await asyncio.to_thread(harnais.executer_une, cas, tmp_path / "serveurs.json")
    finally:
        await charger(DSN_TEST, politique=Path("/nulle-part.sql"))
    assert bon["reussite"], bon["raisons"]
    assert bon["outils"] == ["navire_par_nom", "rechercher_clause"]
    assert not faux["reussite"] and "outil attendu absent : navire_par_nom" in faux["raisons"]
    assert "élément interdit : environ" in faux["raisons"]
