"""Kit du LAB 15 : table des labs, cibles, dossier du harnais lu par pharos-docs, exemples fournis, rapport du
gabarit, lecture des déclencheurs d'un workflow. Ni base, ni Docker, ni modèle."""

import os
import subprocess
import sys

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
