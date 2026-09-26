"""Métier de pharos-legacy : état d'escale et pages de mouvements."""

from datetime import datetime

import pytest

from pharos import horloge
from serveurs.pharos_legacy import metier


def test_pages_de_l_escale_de_reference():
    tailles = [len(metier.page_de_mouvements("ESC-2026-0412", n)["mouvements"]) for n in (1, 2, 3)]
    assert tailles == [20, 20, 17]
    page = metier.page_de_mouvements("ESC-2026-0412", 2)
    assert (page["page"], page["pages"], page["total"]) == (2, 3, 57)


def test_escale_sans_mouvement_a_une_page_vide():
    page = metier.page_de_mouvements("ESC-2026-0409", 1)
    assert (page["pages"], page["total"], page["mouvements"]) == (1, 0, [])


def test_page_hors_limites_et_escale_inconnue():
    with pytest.raises(metier.PageHorsLimites):
        metier.page_de_mouvements("ESC-2026-0412", 4)
    with pytest.raises(metier.EscaleInconnue):
        metier.page_de_mouvements("ESC-2026-9999", 1)
    with pytest.raises(metier.EscaleInconnue):
        metier.etat_escale("ESC-2026-9999")


@pytest.mark.parametrize("heure, statut", [("2026-10-08T05:00:00+02:00", "prévue"),
                                           ("2026-10-08T12:00:00+02:00", "à quai"),
                                           ("2026-10-08T21:00:00+02:00", "partie")])
def test_statut_selon_l_heure_fictive(monkeypatch, heure, statut):
    monkeypatch.setattr(horloge, "maintenant", lambda: datetime.fromisoformat(heure))
    etat = metier.etat_escale("ESC-2026-0412")
    assert etat["statut"] == statut
    assert (etat["quai"], etat["tirant_eau_m"]) == (3, 12.9)
    assert etat["creneau"] == {"debut": "2026-10-08T06:00:00+02:00", "fin": "2026-10-08T20:00:00+02:00"}
