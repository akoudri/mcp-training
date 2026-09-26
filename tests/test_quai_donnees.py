"""Données de pharos-quai : quais, créneaux générés, fenêtres de marée."""

import yaml

from donnees import corpus
from donnees.quai import creneaux

QUAIS = yaml.safe_load((creneaux.FICHIER.parent / "quais.yaml").read_text(encoding="utf-8"))


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def test_le_fichier_versionne_est_celui_que_produit_le_generateur():
    versionne = yaml.safe_load(creneaux.FICHIER.read_text(encoding="utf-8"))
    assert versionne == creneaux.generer(), "relancer : python -m donnees.quai.creneaux"


def test_chaque_escale_tient_dans_son_quai():
    tirants = {q["quai"]: q["tirant_eau_max_m"] for q in QUAIS["quais"]}
    assert sorted(tirants) == [1, 2, 3, 4]
    for e in corpus.charger().escales:
        assert e.tirant_eau_m <= tirants[e.quai], f"{e.escale_id} : {e.tirant_eau_m} m > quai {e.quai}"


def test_chaque_journee_est_couverte_sans_trou():
    for jour, par_quai in creneaux.generer()["creneaux"].items():
        assert sorted(par_quai) == [1, 2, 3, 4]
        for quai, lignes in par_quai.items():
            bornes = [(_minutes(c["debut"]), _minutes(c["fin"])) for c in lignes]
            assert bornes[0][0] == 0 and bornes[-1][1] == 24 * 60, (jour, quai)
            assert all(a[1] == b[0] for a, b in zip(bornes, bornes[1:])), (jour, quai)


def test_jeudi_matin_au_quai_3_un_creneau_libre_et_une_fenetre_de_maree():
    jeudi = creneaux.generer()["creneaux"]["2026-10-08"][3]
    libres_le_matin = [c for c in jeudi if c["escale_id"] is None and _minutes(c["debut"]) < 12 * 60]
    reserves = {c["escale_id"] for c in jeudi if c["escale_id"]}
    assert libres_le_matin and reserves == {"ESC-2026-0412"}
    assert creneaux.generer()["marees"]["2026-10-08"]


def test_seuil_de_maree_entre_les_tirants():
    seuil = QUAIS["maree"]["seuil_tirant_eau_m"]
    vent = corpus.charger().escale("ESC-2026-0412")
    assert vent.tirant_eau_m > seuil                    # le Vent d'Autan attend la marée
    assert any(e.tirant_eau_m <= seuil for e in corpus.charger().escales)
