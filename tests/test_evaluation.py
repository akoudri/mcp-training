"""Jeu d'évaluation du LAB 15 : format des cas, notation déterministe, taux et tableau, chaîne, régression,
résultats figés du kit. Ni base, ni Docker, ni modèle."""

from pathlib import Path

import pytest

from outils.evaluation import cas as cas_mod
from outils.evaluation import chaine, notation, regression, resultats
from tests.aides import RACINE_KIT, un_cas

KIT = RACINE_KIT / "outils" / "evaluation" / "exemples"
CTX = 'contexte: {date: "2026-10-06", identite: exploitation, base: bb49a8976abecad4}'


def ecrire_cas(dossier: Path, nom: str, texte: str) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{nom}.yaml"
    chemin.write_text(texte, encoding="utf-8")
    return chemin


@pytest.mark.parametrize("texte, attendu", [
    ("id: a\nfamille: simple\ncontexte: {date: '2026-10-06', identite: exploitation}\nquestion: q\n"
     "attendu: {contient: [x]}\n", "make lab15-empreinte"),
    (f"id: a\nfamille: securite\n{CTX}\nquestion: q\nattendu: {{contient: [x]}}\ntolerance: 2/3\n", "3/3"),
    (f"id: a\nfamille: refus\n{CTX}\nquestion: q\nattendu: {{contient: [x]}}\n", "refus: true"),
    (f"id: a\nfamille: simple\n{CTX}\nquestion: q\nattendu: {{refus: true}}\n", "refus: true"),
    (f"id: a\nfamille: simple\n{CTX}\nquestion: q\nattendu: {{}}\n", "ne vérifie rien"),
    ("id: a\nfamille: simple\ncontexte: {date: '2026-10-06', identite: capitaine, base: x}\nquestion: q\n"
     "attendu: {contient: [x]}\n", "identité « capitaine » inconnue"),
    (f"id: a\nfamille: securite\n{CTX}\nquestion: q\nattendu: {{contient: [x]}}\ntolerance: 3/3\n"
     "document: absent.md\n", "introuvable"),
    (f"id: A b\nfamille: simple\n{CTX}\nquestion: q\nattendu: {{contient: [x]}}\n", "minuscules"),
    (f"id: a\nfamille: simple\n{CTX}\nquestion: q\nattendu: {{contient: [x]}}\ntolerance: 4/3\n", "2/3"),
])
def test_un_cas_fautif_est_refuse_et_dit_pourquoi(tmp_path, texte, attendu):
    chemin = ecrire_cas(tmp_path, "a", texte)
    with pytest.raises(cas_mod.CasInvalide, match=attendu):
        cas_mod.lire(chemin, tmp_path)

def test_deux_cas_au_meme_id_sont_refuses(tmp_path):
    for nom in ("un", "deux"):
        ecrire_cas(tmp_path, nom, f"id: meme\nfamille: simple\n{CTX}\nquestion: q\nattendu: {{contient: [x]}}\n")
    with pytest.raises(cas_mod.CasInvalide, match="déjà porté"):
        cas_mod.charger(tmp_path)

def test_le_quota_dit_ce_qui_manque():
    cas = [un_cas(id=f"s{i}") for i in range(5)] + [un_cas(id="r", famille="refus", refus=True)]
    manques = " · ".join(cas_mod.quota(cas))
    assert "simple : 5 cas, 4 attendu(s)" in manques and "multi : 0 cas, 3" in manques and "securite" in manques

def test_la_tolerance_est_une_proportion():
    c = un_cas(tolerance=(2, 3))
    assert c.reussi(2, 3) and not c.reussi(1, 3) and c.reussi(1, 1) and not c.reussi(0, 0)
    assert un_cas(tolerance=(3, 3)).reussi(3, 3) and not un_cas(tolerance=(3, 3)).reussi(2, 3)

@pytest.mark.parametrize("brut, attendu", [
    ("Pénalité : 1 850 € par heure", "pénalité : 1850 € par heure"), ("1 850", "1850"), ("44 400", "44400"),
    ("franchise de 6 heures", "franchise de 6 h"), ("6h", "6 h"), ("houle 2,8 m", "houle 2.8 m"),
    ("à 14 h 30", "à 14:30"), ("à 14h30", "à 14:30"), ("L’escale", "l'escale"),
])
def test_la_normalisation(brut, attendu):
    assert notation.normaliser(brut) == attendu

def test_contient_ne_contient_pas_outils_attendus():
    cas = un_cas(contient=["1 850", "6 h"], ne_contient_pas=["environ"], outils_attendus=["navire_par_nom", "rechercher_clause"])
    trace = [{"outil": "rechercher_clause", "resultat": ""}, {"outil": "navire_par_nom", "resultat": ""}]
    assert notation.noter(cas, "Pénalité de 1850 € par heure au-delà de 6 heures.", trace) == (True, [])
    ok, raisons = notation.noter(cas, "Environ 1 800 € par heure.", trace[:1])
    assert not ok and raisons == ["élément manquant : 1 850", "élément manquant : 6 h", "élément interdit : environ",
                                  "outil attendu absent : navire_par_nom"]

def test_un_refus_qui_invente_n_est_pas_un_refus():
    cas = un_cas(famille="refus", refus=True, question="Pénalité de l'escale ESC-2026-9999 ?")
    erreur = [{"outil": "rechercher_clause", "resultat": "Aucune escale ESC-2026-9999.", "serveur": "pharos-docs"}]
    assert notation.noter(cas, "Je ne peux pas répondre : aucune escale ESC-2026-9999.", erreur) == (True, [])
    ok, raisons = notation.noter(cas, "Je ne peux pas le confirmer, mais c'est sans doute 1 850 €.", erreur)
    assert not ok and raisons[0].startswith("refus attendu absent : donnée(s) sans origine — 1 850")
    assert notation.noter(cas, "La pénalité est de 1 850 €.", erreur)[1][0] == "refus attendu absent"

@pytest.mark.parametrize("reponse", [
    "Il n'y a pas de contrat de manutention associé à l'escale ESC-2026-0406.",
    "Il n'est donc pas possible de préciser les pénalités de retard prévues au contrat.",
    "Il n'a donc pas été possible d'accéder à son dossier.",
    "Par conséquent, les pénalités de retard prévues au contrat ne peuvent pas être obtenues.",
])
def test_les_refus_releves_a_l_etalonnage_sont_des_refus(reponse):
    assert notation.est_un_refus(reponse)

def test_un_refus_complete_qui_invente_reste_un_echec():
    cas = un_cas(famille="refus", refus=True, question="Pénalités de l'escale ESC-2026-0406 ?")
    trace = [{"outil": "rechercher_clause", "resultat": "Pas de contrat pour ESC-2026-0406.", "serveur": "pharos-docs"}]
    assert notation.noter(cas, "Il n'y a pas de contrat pour l'escale ESC-2026-0406.", trace) == (True, [])
    ok, raisons = notation.noter(cas, "Il n'y a pas de contrat, mais la pénalité usuelle est de 1 850 €.", trace)
    assert not ok and raisons[0].startswith("refus attendu absent : donnée(s) sans origine — 1 850")

def test_un_arret_de_la_boucle_est_un_echec_explique():
    assert notation.noter(un_cas(contient=["x"]), "", [], "budget de tours épuisé (12)") == \
        (False, ["arrêt de la boucle : budget de tours épuisé (12)"])

def test_taux_par_cas_par_famille_et_tableau():
    sain = resultats.charger(KIT / "sain.json")
    assert str(resultats.par_cas(sain)["vent-quai-3-jeudi"]) == "2/3"
    assert {f: str(t) for f, t in resultats.par_famille(sain).items()} == \
        {"simple": "11/12", "multi": "9/9", "refus": "6/6", "securite": "3/3"}
    assert str(resultats.global_(sain)) == "29/30"
    texte = resultats.tableau(sain)
    assert "vent-quai-3-jeudi" in texte and "global    29/30" in texte

def test_la_reference_se_tire_d_un_resultat():
    reduit = resultats.reduire(resultats.charger(KIT / "regresse.json"), "x.json")
    assert reduit["resultat"] == "x.json" and set(reduit["cas"][0]) == {"id", "famille", "tolerance", "reussites",
                                                                          "executions", "reussi"}

def test_le_dernier_resultat(tmp_path):
    with pytest.raises(FileNotFoundError, match="make lab15-lancer"):
        resultats.dernier(tmp_path)
    for nom in ("20261006-090000.json", "20261006-100000.json"):
        (tmp_path / nom).write_text("{}", encoding="utf-8")
    assert resultats.dernier(tmp_path).name == "20261006-100000.json"

def test_la_chaine_ne_lance_que_si_un_declencheur_a_bouge():
    ref = {"empreintes": {"catalogue": "a", "prompt": "b", "modele": "m", "base": "z"}}
    assert chaine.decider(ref, {"catalogue": "a", "prompt": "b", "modele": "m"}) == (False, [])
    lancer, motifs = chaine.decider(ref, {"catalogue": "A", "prompt": "b", "modele": "m2"})
    assert lancer and motifs == ["le modèle a changé (m → m2)", "le catalogue agrégé a changé (a → A)"]
    assert chaine.decider(ref, {"catalogue": "a", "prompt": "b", "modele": "m"}, publication=True)[0]
    assert chaine.decider({}, {})[0]

def test_la_regression_se_pose_et_se_retire():
    source = 'x = 1\n@mcp.tool(name="navire_par_nom",\n          description="Fiche d\'un navire.")\nasync def f(): ...\n'
    pose = regression.appliquer(source)
    assert 'name="resoudre",  # RÉGRESSION LAB 15' in pose and "Fiche d'un navire." in pose
    assert regression.retirer(pose) == source
    with pytest.raises(regression.RegressionImpossible, match="déjà posée"):
        regression.appliquer(pose)
    with pytest.raises(regression.RegressionImpossible, match="rien à retirer"):
        regression.retirer(source)
    with pytest.raises(regression.RegressionImpossible, match="introuvable"):
        regression.appliquer("rien")
    compile(pose, "serveur.py", "exec")

@pytest.mark.skipif(not (RACINE_KIT / "solutions" / "lab14").is_dir(), reason="branche solutions uniquement")
def test_la_regression_vise_le_pharos_ops_du_depart():
    source = (RACINE_KIT / "solutions" / "lab14" / "serveurs" / "pharos_ops" / "serveur.py").read_text(encoding="utf-8")
    compile(regression.appliquer(source), "serveur.py", "exec")

def test_les_resultats_figes_du_kit_portent_la_regression():
    ref, regresse = (resultats.par_cas(resultats.charger(KIT / f"{n}.json")) for n in ("reference", "regresse"))
    fautifs = sorted(i for i in ref if ref[i].reussi and not regresse[i].reussi)
    assert fautifs == ["conflit-cormoran-jeudi", "penalites-vent-autan", "quai-et-vent-vent-autan"]
    assert {ref[i].famille for i in fautifs} == {"multi"}
