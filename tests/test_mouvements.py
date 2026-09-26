"""Données de pharos-legacy : mouvements de conteneurs et tirant d'eau des escales."""

from datetime import datetime

import yaml

from donnees import corpus
from donnees.legacy import mouvements


def test_le_fichier_versionne_est_celui_que_produit_le_generateur():
    versionne = yaml.safe_load(mouvements.FICHIER.read_text(encoding="utf-8"))
    assert versionne == mouvements.generer(), "relancer : python -m donnees.legacy.mouvements"


def test_nombres_par_escale():
    tous = mouvements.generer()["mouvements"]
    assert len(tous["ESC-2026-0412"]) == 57          # trois pages de 20
    assert set(tous) == {e.escale_id for e in corpus.charger().escales}
    assert all(0 <= len(m) <= 45 for e, m in tous.items() if e != "ESC-2026-0412")


def test_mouvements_dans_le_creneau_et_dans_l_ordre():
    tous = mouvements.generer()["mouvements"]
    for e in corpus.charger().escales:
        heures = [datetime.fromisoformat(m["heure"]) for m in tous[e.escale_id]]
        assert heures == sorted(heures)
        assert all(e.debut <= h <= e.fin for h in heures)
        for m in tous[e.escale_id]:
            assert m["type"] in mouvements.TYPES and m["statut"] in mouvements.STATUTS
            assert len(m["conteneur"]) == 11 and m["conteneur"][:4].isalpha()


def test_chaque_escale_a_un_tirant_d_eau():
    c = corpus.charger()
    assert c.escale("ESC-2026-0412").tirant_eau_m == 12.9
    assert all(7.0 <= e.tirant_eau_m <= 15.0 for e in c.escales)
