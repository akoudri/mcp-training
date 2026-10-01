"""Kit du LAB 15 : table des labs, cibles, dossier du harnais lu par pharos-docs, exemples fournis, rapport du
gabarit, lecture des déclencheurs d'un workflow. Ni base, ni Docker, ni modèle."""

import os
import subprocess
import sys

import pytest

from outils import labs
from outils.evaluation import cas as cas_mod
from tests.aides import RACINE_KIT

GABARITS = RACINE_KIT / "gabarits" / "lab15"
EXEMPLES = GABARITS / "evaluation" / "exemples"
KIT = RACINE_KIT / "outils" / "evaluation" / "exemples"


def test_le_depart_et_la_sortie_du_lab15():
    assert labs.DEPARTS[15] == "sg1-fin" and labs.SORTIES[15] == "ex2-fin"
    assert labs.PORTS_PRETS[15] == [8101, 8102, 8103] and labs.DEMARRAGE[15][-1] == "lab13-tout"

def test_les_cibles_du_brief_existent():
    mk = (RACINE_KIT / "mk" / "lab15.mk").read_text(encoding="utf-8")
    for cible in ("lab15-scaffold", "lab15-exemple", "lab15-empreinte", "lab15-lancer", "lab15-rapport",
                  "lab15-referencer", "lab15-regression", "lab15-regression-retirer", "lab15-chaine", "lab15-verifier"):
        assert f"\n{cible}:" in f"\n{mk}", cible

def test_pharos_docs_lit_le_dossier_du_harnais():
    compose = (RACINE_KIT / "compose" / "lab14.yaml").read_text(encoding="utf-8")
    assert compose.rstrip().endswith(':contrats-partages/evaluation"')

def test_les_exemples_fournis_sont_valides():
    exemple = cas_mod.lire(EXEMPLES / "penalites-vent-autan.yaml", RACINE_KIT)
    assert exemple.famille == "multi" and exemple.contient == ["1 850", "6 h"] and exemple.tolerance == (2, 3)
    securite = cas_mod.lire(EXEMPLES / "cas_securite.yaml", RACINE_KIT)
    assert securite.tolerance == (3, 3) and securite.document == "gabarits/lab14/pieges/c.md"
    assert securite.contexte.jeton == "jeton-rance" and "ESC-2026-1364" in securite.ne_contient_pas

def test_le_rapport_du_gabarit_dit_ce_qui_reste_a_ecrire(tmp_path):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(str(p) for p in (RACINE_KIT / "src", RACINE_KIT))}
    sortie = subprocess.run([sys.executable, str(GABARITS / "evaluation" / "rapport.py"), str(KIT / "sain.json"),
                             "--reference", str(KIT / "reference.json")], capture_output=True, text=True, env=env)
    assert sortie.returncode == 2 and "comparer(courant, reference) n'est pas encore écrit" in sortie.stdout
    vide = tmp_path / "vide.json"
    vide.write_text("{}", encoding="utf-8")
    sortie = subprocess.run([sys.executable, str(GABARITS / "evaluation" / "rapport.py"), str(KIT / "sain.json"),
                             "--reference", str(vide)], capture_output=True, text=True, env=env)
    assert sortie.returncode == 0 and "make lab15-referencer" in sortie.stdout


def test_la_cle_on_d_un_workflow_se_lit_meme_quand_yaml_la_change_en_true():
    import yaml

    from outils.verifier import lab15

    flux = yaml.safe_load("on:\n  push:\n    paths: [a]\n    tags: ['v*']\n  workflow_dispatch:\n    inputs: {modele: {}}\n")
    assert True in flux
    assert lab15._declencheurs(flux) == {"paths": ["a"], "tags": ["v*"], "manuel": True, "entrees": {"modele": {}}}
    assert lab15._declencheurs({"name": "x"}) == {"paths": [], "tags": [], "manuel": False, "entrees": {}}

def test_declencheurs_ne_plante_jamais_sur_une_forme_inattendue():
    from outils.verifier import lab15

    vide = {"paths": [], "tags": [], "manuel": False, "entrees": {}}
    for flux in (["a", "b"], None, "texte", {"on": ["push"]}, {"on": {"push": ["a"]}},
                 {"on": {"push": {"paths": "a", "tags": [1, None]}}}):
        assert lab15._declencheurs(flux) == vide, flux
    assert lab15._declencheurs({"on": {"push": {"paths": ["a", 3], "tags": ["v*"]}, "workflow_dispatch": None}}) == \
        {"paths": ["a"], "tags": ["v*"], "manuel": True, "entrees": {}}


def _chaine(tmp_path, monkeypatch, evaluation: str):
    import shutil

    from outils.verifier import lab15
    from outils.verifier.commun import Echec

    (tmp_path / ".ci").mkdir(exist_ok=True)
    shutil.copy(GABARITS / ".ci" / "rapide.yaml", tmp_path / ".ci" / "rapide.yaml")
    (tmp_path / ".ci" / "evaluation.yaml").write_text(evaluation, encoding="utf-8")
    monkeypatch.setattr(lab15, "RACINE", tmp_path)
    try:
        return lab15.chaine_separee(None)
    except Echec as exc:
        return f"ÉCHEC {exc}"


DECLENCHEURS = ("name: evaluation\non:\n  push:\n    branches: ['**']\n    paths: [client/pharos_client/consigne.md, "
                "serveurs/**]\n    tags: ['v*']\n  workflow_dispatch:\n    inputs: {modele: {required: true}}\n")


def test_la_chaine_se_lit_dans_les_jobs_pas_dans_les_commentaires(tmp_path, monkeypatch):
    gabarit = (GABARITS / ".ci" / "evaluation.yaml").read_text(encoding="utf-8")
    assert "make lab15-chaine" in gabarit and "OPENROUTER_API_KEY" in gabarit
    verdict = _chaine(tmp_path, monkeypatch, gabarit)
    assert verdict.startswith("ÉCHEC") and "make lab15-chaine" in verdict and "secrets.OPENROUTER_API_KEY" in verdict
    commentes = DECLENCHEURS + ("# make lab15-chaine  ${{ secrets.OPENROUTER_API_KEY }}\njobs:\n  evaluation:\n"
                                "    steps:\n      - run: make construire  # puis make lab15-chaine\n")
    verdict = _chaine(tmp_path, monkeypatch, commentes)
    assert "un job qui lance make lab15-chaine" in verdict and "secrets.OPENROUTER_API_KEY" in verdict
    for env_au in ("jobs:\n  evaluation:\n    env:\n      OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}\n"
                   "    steps:\n      - run: make lab15-chaine\n",
                   "env:\n  OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}\njobs:\n  e:\n    steps:\n"
                   "      - run: |\n          make lab8-base\n          make lab15-chaine PUBLICATION=1\n",
                   "jobs:\n  e:\n    steps:\n      - name: jeu\n        env: {OPENROUTER_API_KEY: '${{ secrets.OPENROUTER_API_KEY }}'}"
                   "\n        run: make lab15-chaine\n"):
        assert not _chaine(tmp_path, monkeypatch, DECLENCHEURS + env_au).startswith("ÉCHEC"), env_au


def test_la_chaine_de_la_solution_passe(tmp_path, monkeypatch):
    solution = RACINE_KIT / "solutions" / "lab15" / ".ci" / "evaluation.yaml"
    if not solution.exists():
        pytest.skip("solution présente sur la branche de travail et la branche solutions uniquement")
    assert not _chaine(tmp_path, monkeypatch, solution.read_text(encoding="utf-8")).startswith("ÉCHEC")


def test_un_rapport_sans_resultat_le_dit_en_une_ligne(tmp_path):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(str(p) for p in (RACINE_KIT / "src", RACINE_KIT))}
    for rapport in (GABARITS / "evaluation" / "rapport.py",
                    RACINE_KIT / "solutions" / "lab15" / "evaluation" / "rapport.py"):
        if not rapport.exists():
            continue
        for argv, attendu in (([], "aucun résultat dans sortie/lab15"), (["absent.json"], "Résultat introuvable")):
            sortie = subprocess.run([sys.executable, str(rapport), *argv], capture_output=True, text=True, env=env,
                                    cwd=tmp_path)
            assert sortie.returncode == 1 and sortie.stderr == "", (rapport, sortie.stderr)
            assert sortie.stdout.count("\n") == 1 and attendu in sortie.stdout, (rapport, sortie.stdout)


def test_sans_cas_instable_le_verificateur_donne_la_sortie(tmp_path, monkeypatch):
    import json

    from outils.verifier import lab15
    from outils.verifier.commun import Echec

    (tmp_path / "evaluation").mkdir()
    (tmp_path / "labs" / "lab15").mkdir(parents=True)
    monkeypatch.setattr(lab15, "RACINE", tmp_path)

    def verdict(taux: dict, consignes: str) -> str:
        cas = [{"id": i, "famille": f, "tolerance": "2/3", "reussites": r, "executions": 3, "reussi": r >= 2}
               for i, (f, r) in taux.items()]
        (tmp_path / "evaluation" / "reference.json").write_text(json.dumps({"cas": cas}), encoding="utf-8")
        (tmp_path / "labs" / "lab15" / "reference.md").write_text(f"# x\n\n## Cas instables\n\n{consignes}\n",
                                                                   encoding="utf-8")
        try:
            return lab15.cas_instable(None)
        except Echec as exc:
            return f"ÉCHEC {exc}"

    stable = verdict({"a": ("simple", 3), "s": ("securite", 2)}, "- `a` : rien")
    assert stable.startswith("ÉCHEC aucun cas instable dans la référence : c'est fréquent avec un bon agent")
    assert "CAS=… FOIS=3" in stable and "complétée, pas remplacée" in stable and "corrigé" not in stable
    oublie = verdict({"a": ("simple", 3), "b": ("refus", 2)}, "- `a` : rien")
    assert oublie.startswith("ÉCHEC la référence a un cas instable — b 2/3") and "a n'y est pas instable" in oublie
    assert verdict({"a": ("simple", 3), "b": ("refus", 2)}, "- `b` — 2/3") == "b 2/3"
