"""Kit du LAB 9 : analyse syntaxique fournie, message de refus, contournements, identités."""

from pathlib import Path

from outils import lab9
from tests.aides import base_requise, charger_module

PERIMETRE = charger_module(Path("gabarits/lab09/serveurs/pharos_data/perimetre.py"), "gabarit_lab9_perimetre")
DEFINITION = charger_module(Path("gabarits/lab09/serveurs/pharos_data/definition.py"), "gabarit_lab9_definition")


def test_analyse_des_trois_contournements():
    [ecriture], [jointure], colonnes = (lab9.CONTOURNEMENTS[n] for n in (1, 2, 3))
    assert not PERIMETRE.analyser(ecriture).select_seul
    assert PERIMETRE.analyser(jointure).tables == {"escales", "tarifs"}
    assert [PERIMETRE.analyser(sql).tables for sql in colonnes] == [{"escales"}, {"escales"}, {"esc_hdr_legacy"}]
    assert ("escales", "tarif_negocie") in PERIMETRE.analyser(colonnes[0]).colonnes


def test_analyse_des_requetes_legitimes_et_pieges():
    a = PERIMETRE.analyser("select count(*) from mouvements m join escales e using (escale_id) where e.quai = 3")
    assert a.select_seul and a.tables == {"mouvements", "escales"} and not a.etoile
    assert PERIMETRE.analyser("SELECT * FROM escales").etoile
    assert PERIMETRE.analyser("SELECT 1; DROP TABLE escales").instructions == 2


def test_refus_uniforme_sans_rien_de_cache():
    texte = str(PERIMETRE.refus("table ou colonne hors périmètre"))
    assert texte.startswith("Requête refusée (table ou colonne hors périmètre).")
    assert not any(m in texte for m in ("tarif", "esc_hdr_legacy", "armateur"))


def test_definition_2_0():
    assert DEFINITION.DEFINITION_VERSION == "2.0" and DEFINITION.MARGE_TIRANT_EAU_M == 1.0
    assert DEFINITION.CRITERES[:2] == DEFINITION.CRITERES_EVALUES == ("tirant_eau", "conflit_creneau")


@base_requise
def test_identites(base_de_test, capsys):
    assert lab9.identites() == 0
    sortie = capsys.readouterr().out
    assert "jeton-rance" in sortie and "Vent d'Autan" in sortie and "toutes les escales" in sortie
