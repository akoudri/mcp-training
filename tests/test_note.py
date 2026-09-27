"""Vérificateur de note du LAB 13 : formes normalisées, origines, calculs, exclusions."""

import json
from pathlib import Path

import pytest

from outils.verifier.note import formater, sans_origine, verifier_note
from types import SimpleNamespace

QUESTION = ("L'escale du Vent d'Autan de jeudi est-elle à risque ? Si oui, prépare la note d'alerte pour "
            "l'exploitant.")
NAVIRE = ('{"navires":[{"navire_id":"NAV-0007","nom":"Vent d\'Autan","tirant_eau_max_m":13.2,"escales":'
          '[{"escale_id":"ESC-2026-0412","quai":3,"debut":"2026-10-08T06:00+02:00","fin":"2026-10-08T20:00+02:00"}]}]}')
CLAUSE = ('{"document_id":"CM-0412","article":"Article 7 — Pénalités de retard","page":7,"texte":"Tout retard '
          'au-delà d\'une franchise de 6 heures donne lieu au versement à l\'armateur d\'une pénalité de 1 850 € '
          'par heure de retard entamée. Le montant total est plafonné à 44 400 € par escale."}')
METEO = ('{"resultats":[{"quai":3,"previsions":[{"heure":"2026-10-08T14:00+02:00","vent_kt":34.0,"rafales_kt":42.0,'
         '"houle_m":2.8},{"heure":"2026-10-08T18:00+02:00","vent_kt":6.9,"rafales_kt":12.8,"houle_m":0.4}]}],'
         '"incomplets":[],"complet":true}')
RISQUE = ('{"date":"2026-10-08","escales":[{"escale_id":"ESC-2026-0412","criteres":[{"critere":"tirant_eau",'
          '"detail":{"tirant_eau_m":12.9,"quai_max_m":13.5,"marge_m":1.0,"depassement_m":0.4}},{"critere":'
          '"conflit_creneau","detail":{"escale_id":"ESC-2026-0413","chevauchement_min":60}}]}]}')


def _e(tour, outil, resultat, serveur):
    """Un enregistrement de trace (pharos_client.trace.Enregistrement) : seuls ces champs sont lus."""
    return SimpleNamespace(tour=tour, outil=outil, resultat=resultat, serveur=serveur)


TRACE = [_e(1, "navire_par_nom", NAVIRE, "pharos-ops"), _e(2, "rechercher_clause", CLAUSE, "pharos-docs"),
         _e(3, "meteo_creneau", METEO, "pharos-ops"), _e(4, "escales_a_risque", RISQUE, "pharos-data")]

NOTE_JUSTE = """Objet : alerte — escale ESC-2026-0412 (Vent d'Autan), quai 3, jeudi 8 octobre 2026, 6 h – 20 h.

1. Météo : coup de vent de 34 kt (rafales 42 kt), houle de 2,8 m, à partir de 14 h.
2. Tirant d'eau : 12,9 m pour un maximum de 13,5 m au quai 3, soit un dépassement de 0,4 m.
3. Conflit de créneau avec ESC-2026-0413 : 60 minutes.

Pénalités (contrat CM-0412, article 7) : 1 850 € par heure entamée au-delà d'une franchise de 6 heures,
plafonnées à 44 400 €. L'écart entre tirant d'eau et maximum du quai n'est que de 0,6 m.
"""


def test_une_note_juste_n_a_rien_sans_origine():
    elements = verifier_note(NOTE_JUSTE, TRACE, QUESTION)
    assert sans_origine(elements) == [], formater(elements)
    textes = {e.texte for e in elements}
    assert {"ESC-2026-0412", "1 850", "2,8", "8 octobre 2026", "14 h"} <= textes


def test_l_origine_nomme_le_tour_le_serveur_et_l_outil():
    origines = {e.texte: e.origine for e in verifier_note(NOTE_JUSTE, TRACE, QUESTION)}
    assert origines["1 850"] == "t2 pharos-docs rechercher_clause"
    assert origines["2,8"] == "t3 pharos-ops meteo_creneau"
    assert origines["8 octobre 2026"] == "t1 pharos-ops navire_par_nom"


def test_un_nombre_calcule_d_une_seule_operation_est_accepte_et_dit():
    origines = {e.texte: e.origine for e in verifier_note(NOTE_JUSTE, TRACE, QUESTION)}
    assert origines["0,6"].startswith("calcul : ") and origines["0,6"].endswith("(t4 pharos-data escales_a_risque)")


def test_un_calcul_entre_deux_appels_differents_n_est_pas_accepte():
    # 1850 (t2) × 2,8 (t3) : deux appels différents — une coïncidence, pas une dérivation
    assert [e.texte for e in sans_origine(verifier_note("Soit 5 180 €.", TRACE))] == ["5 180"]


@pytest.mark.parametrize("invention", [
    "Pénalité : 2 100 € par heure.",          # chiffre plausible, inventé
    "Houle attendue : 3,1 m.",                # hauteur vraisemblable
    "Arrivée prévue le 9 octobre.",           # date approximative
    "Armateur : Transports Maritimes du Ponant.",   # nom connu, absent de la trace
    "Escale suivante : ESC-2026-0999.",       # identifiant inventé
])
def test_une_donnee_inventee_est_signalee(invention):
    manquants = sans_origine(verifier_note(NOTE_JUSTE + invention, TRACE, QUESTION))
    assert len(manquants) == 1, manquants


@pytest.mark.parametrize("forme", ["1850 €", "1 850 €", "1 850 €"])
def test_les_milliers_s_ecrivent_de_plusieurs_facons(forme):
    assert sans_origine(verifier_note(f"Pénalité : {forme} par heure.", TRACE)) == []


@pytest.mark.parametrize("forme", ["2026-10-08", "08/10/2026", "8 octobre", "jeudi 8 octobre 2026"])
def test_les_dates_s_ecrivent_de_plusieurs_facons(forme):
    elements = verifier_note(f"Escale du {forme}.", TRACE)
    assert [e.genre for e in elements] == ["date"] and elements[0].origine


@pytest.mark.parametrize("forme", ["14 h", "14h00", "14 h 00", "14:00"])
def test_les_heures_s_ecrivent_de_plusieurs_facons(forme):
    elements = verifier_note(f"Coup de vent dès {forme}.", TRACE)
    assert [e.genre for e in elements] == ["heure"] and elements[0].origine


def test_une_heure_absente_de_la_trace_est_signalee():
    assert [e.texte for e in sans_origine(verifier_note("Coup de vent dès 15 h 30.", TRACE))] == ["15 h 30"]


def test_les_numeros_d_etape_et_la_question_ne_sont_pas_verifies():
    note = "Étape 5 : évaluation.\n7. Publication.\nL'escale du Vent d'Autan de jeudi est à risque."
    assert verifier_note(note, TRACE, QUESTION) == []


def test_la_trace_peut_venir_du_fichier_json():
    trace = [{"tour": e.tour, "outil": e.outil, "serveur": e.serveur, "resultat": e.resultat} for e in TRACE]
    assert sans_origine(verifier_note(NOTE_JUSTE, trace, QUESTION)) == []


def test_le_rapport_dit_ce_qui_manque():
    texte = formater(verifier_note("Houle de 3,1 m.", TRACE))
    assert "SANS ORIGINE" in texte and "1 sans origine" in texte


# --- Revue finale, Critical 1 : un calcul ne se fait qu'entre nombres frères d'un même objet JSON, de même unité ---

PUBLIEE = ('{"publiee":true,"alerte_id":"ALR-0003","recue":"2026-10-06T21:04:24+02:00","escale_id":"ESC-2026-0412"}')
TRACE_PUBLIEE = [*TRACE, _e(5, "publier_alerte", PUBLIEE, "pharos-ops")]


def test_un_calcul_entre_freres_de_meme_unite_est_accepte():
    origines = {e.texte: e.origine for e in verifier_note("Rafales supérieures au vent de 8 kt.", TRACE)}
    assert origines["8"] == "calcul : 42 − 34 (t3 pharos-ops meteo_creneau)"


@pytest.mark.parametrize("note, texte", [
    ("Le vent tombe de 27,1 kt dans la soirée.", "27,1"),   # 34 − 6,9 : même appel, mais deux prévisions différentes
    ("Soit 16,2 m au total.", "16,2"),                      # 13,2 (tirant_eau_max_m) + 3 (quai, sans unité)
    ("Plafond atteint après 11 100 €.", "11 100"),          # 1 850 × 6 : deux nombres du texte libre de la clause
    ("Franchise de 8 heures.", "8"),                        # 42 − 34 : frères en kt, pas en heures
    ("Écart rafales-vent : 8.", "8"),                       # sans unité dans la note : pas de calcul
])
def test_un_calcul_hors_des_freres_de_meme_unite_n_est_pas_accepte(note, texte):
    assert [e.texte for e in sans_origine(verifier_note(note, TRACE))] == [texte]


def test_une_duree_en_toutes_lettres_ne_trouve_pas_son_origine_dans_un_horodatage():
    # 14:00 figure dans la trace (heure d'une prévision) ; « 14 heures » est une durée : seul le nombre compte
    assert [(e.texte, e.genre) for e in sans_origine(verifier_note("Retard de 14 heures.", TRACE))] == [("14", "nombre")]
    assert sans_origine(verifier_note("Franchise de 6 heures.", TRACE)) == []


def test_un_seuil_tire_d_une_description_d_outil_n_a_pas_d_origine():
    # les seuils de meteo_alerte (25 kt, 35 kt) sont dans sa description, pas dans un résultat de la trace
    assert [e.texte for e in sans_origine(verifier_note("Vent de 34 kt, au-delà du seuil de 25 kt.", TRACE))] == ["25"]


@pytest.mark.parametrize("forme, genre", [("08/10", "date"), ("21:04:24", "heure"), ("ALR-0003", "identifiant"),
                                          ("06/10/2026", "date")])
def test_date_sans_annee_heure_avec_secondes_et_alerte_sont_reconnues(forme, genre):
    elements = verifier_note(f"Alerte publiée : {forme}.", TRACE_PUBLIEE)
    assert [(e.texte, e.genre) for e in elements] == [(forme, genre)] and elements[0].origine, elements


@pytest.mark.parametrize("forme", ["12/10", "21:04:25", "ALR-0004"])
def test_date_sans_annee_heure_avec_secondes_et_alerte_absentes_sont_signalees(forme):
    assert [e.texte for e in sans_origine(verifier_note(f"Alerte publiée : {forme}.", TRACE_PUBLIEE))] == [forme]


EXECUTION_GARDEE = Path(__file__).resolve().parents[1] / "solutions" / "lab13" / "labs" / "lab13" / "execution.json"


@pytest.mark.skipif(not EXECUTION_GARDEE.exists(), reason="exécution gardée sur la branche solutions uniquement")
@pytest.mark.parametrize("invention, texte", [
    ("Houle 3,1 m.", "3,1"), ("Vent 27 kt.", "27"), ("Rafales 48 kt.", "48"), ("Visibilité 2,5 km.", "2,5"),
    ("Franchise 8 heures.", "8"),
])
def test_les_inventions_de_la_revue_sont_signalees_sur_la_vraie_trace(invention, texte):
    execution = json.loads(EXECUTION_GARDEE.read_text(encoding="utf-8"))
    elements = verifier_note(invention, execution["trace"], execution["question"])
    assert [e.texte for e in sans_origine(elements)] == [texte], formater(elements)


@pytest.mark.skipif(not EXECUTION_GARDEE.exists(), reason="exécution gardée sur la branche solutions uniquement")
def test_la_coincidence_residuelle_sur_la_vraie_trace_est_un_calcul_entre_freres():
    # 13,1 = 13,5 − 0,4 : quai_max_m et depassement_m, frères du détail « tirant_eau » d'escales_a_risque — assumé
    execution = json.loads(EXECUTION_GARDEE.read_text(encoding="utf-8"))
    [element] = verifier_note("Tirant d'eau 13,1 m.", execution["trace"], execution["question"])
    assert element.origine is None or element.origine.startswith("calcul : 13.5 − 0.4 ("), element


def test_les_numeros_de_section_markdown_ne_sont_pas_verifies():
    note = "#### 4. Dispositions contractuelles\n* 5) Publication\n12.9 m de tirant d'eau."
    assert [(e.texte, e.origine is not None) for e in verifier_note(note, TRACE)] == [("12.9", True)]
