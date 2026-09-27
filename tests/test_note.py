"""Vérificateur de note du LAB 13 : formes normalisées, origines, calculs, exclusions."""

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
