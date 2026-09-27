"""Données de la base PHAROS : générées en mémoire, déterministes, et porteuses des invariants des labs."""

from datetime import date, datetime, timedelta, timezone

import pytest
import yaml

from donnees import corpus
from donnees.base import generer
from donnees.quai import creneaux

FUSEAU = generer.FUSEAU


@pytest.fixture(scope="module")
def d():
    return generer.generer()


def _jour(j: date) -> tuple[datetime, datetime]:
    debut = datetime.combine(j, datetime.min.time(), FUSEAU)
    return debut, debut + timedelta(days=1)


def test_deterministe(d):
    autre = generer.generer()
    assert autre.escales == d.escales and autre.mouvements == d.mouvements and autre.legacy == d.legacy


def test_escales_du_corpus_reprises(d):
    par_id = {e.escale_id: e for e in d.escales}
    navires = {n.navire_id: n for n in d.navires}
    for e in corpus.charger().escales:
        b = par_id[e.escale_id]
        assert (b.quai, b.debut, b.fin, b.tirant_eau_m) == (e.quai, e.debut, e.fin, e.tirant_eau_m)
        assert navires[b.navire_id].nom == e.navire
        assert generer.AGENTS[navires[b.navire_id].agent_id] == e.agent
    assert par_id["ESC-2026-0412"].navire_id == "NAV-0007"


def test_mouvements_du_corpus_identiques_a_pharos_legacy(d):
    legacy = yaml.safe_load(generer.LEGACY.read_text(encoding="utf-8"))["mouvements"]
    for escale_id, attendus in legacy.items():
        obtenus = sorted((m.conteneur_id, m.horodatage) for m in d.mouvements if m.escale_id == escale_id)
        assert obtenus == sorted((m["conteneur"], datetime.fromisoformat(m["heure"])) for m in attendus)


def test_sept_quais_dont_les_quatre_du_lab6(d):
    lab6 = yaml.safe_load((creneaux.FICHIER.parent / "quais.yaml").read_text(encoding="utf-8"))["quais"]
    assert [q.quai for q in d.quais] == [1, 2, 3, 4, 5, 6, 7]
    for q in lab6:
        b = d.quais[q["quai"] - 1]
        assert (b.longueur_m, b.tirant_eau_max_m, list(b.equipements)) == \
            (q["longueur_m"], q["tirant_eau_max_m"], q["equipements"])


def test_valeurs_categorielles_sans_accent(d):
    assert {m.type_conteneur for m in d.mouvements} == {"20", "40", "refrigere"}
    assert {m.sens for m in d.mouvements} == {"embarquement", "debarquement"}


def test_verite_de_reference_et_piege_du_fuseau(d):
    debut, fin = generer.SEMAINE_REFERENCE
    verite = generer.compter(d, debut, fin, quai=3, type_conteneur="refrigere")
    en_utc = generer.compter(d, datetime(2026, 9, 28, tzinfo=timezone.utc), datetime(2026, 10, 5, tzinfo=timezone.utc),
                             quai=3, type_conteneur="refrigere")
    assert verite == 16
    assert en_utc == verite - 1


def test_mouvements_dans_la_fenetre_de_leur_escale(d):
    par_id = {e.escale_id: e for e in d.escales}
    for m in d.mouvements:
        e = par_id[m.escale_id]
        assert e.debut <= m.horodatage <= e.fin, m
        assert e.statut != "annulee"


def test_plafond_de_200_lignes_depasse_avec_ou_sans_quai(d):
    septembre = (datetime(2026, 9, 1, tzinfo=FUSEAU), datetime(2026, 10, 1, tzinfo=FUSEAU))
    assert generer.compter(d, *septembre) > 200
    assert all(generer.compter(d, *septembre, quai=q) > 200 for q in range(1, 8))


def test_quai_5_hier_dans_les_deux_sens(d):
    hier = _jour(date(2026, 10, 5))
    assert generer.compter(d, *hier, quai=5, sens="debarquement") > 0
    assert generer.compter(d, *hier, quai=5, sens="embarquement") > 0


def test_jeudi(d):
    debut, fin = _jour(generer.JEUDI)
    jeudi = [e for e in d.escales if e.debut < fin and debut < e.fin]
    assert len(jeudi) == 24
    assert len([e for e in jeudi if e.quai == 3]) <= 4
    assert d.conflits_jeudi[0] == ("ESC-2026-0412", "ESC-2026-0413", 60)
    assert len(d.conflits_jeudi) == 2
    navires = {n.navire_id: n.agent_id for n in d.navires}
    assert {navires[e.navire_id] for e in jeudi if e.quai == 3} == {"AG-RANCE", "AG-IROISE"}


def test_vent_d_autan_a_risque_par_le_tirant_d_eau(d):
    e = next(e for e in d.escales if e.escale_id == "ESC-2026-0412")
    quai = d.quais[e.quai - 1]
    assert e.tirant_eau_m > quai.tirant_eau_max_m - generer.MARGE_TIRANT_EAU_M
    debut, fin = _jour(generer.JEUDI)
    autres = [x for x in d.escales if x.debut < fin and debut < x.fin and x.escale_id != e.escale_id]
    assert all(x.tirant_eau_m <= d.quais[x.quai - 1].tirant_eau_max_m - generer.MARGE_TIRANT_EAU_M for x in autres)


def test_planning_du_lab6_inchange_sur_les_quais_1_a_4(d):
    """pharos-quai (LAB 6) lit son propre planning : aucune escale ajoutée aux quais 1 à 4 du 5 au 9 octobre,
    sauf ESC-2026-0413 (quai 3, jeudi soir), qui porte le conflit du Vent d'Autan."""
    ids_corpus = {e.escale_id for e in corpus.charger().escales}
    debut, fin = datetime(2026, 10, 5, 8, tzinfo=FUSEAU), datetime(2026, 10, 10, tzinfo=FUSEAU)
    ajoutees = {e.escale_id for e in d.escales if e.quai <= 4 and e.debut < fin and debut < e.fin} - ids_corpus
    assert ajoutees == {"ESC-2026-0413"}
    mercredi = _jour(date(2026, 10, 7))
    assert not [e for e in d.escales if e.quai == 3 and e.debut < mercredi[1] and mercredi[0] < e.fin]


def test_legacy_et_tarifs(d):
    septembre = [m for m in d.mouvements if m.horodatage.month == 9]
    assert len(d.legacy) == len(septembre) + round(len(septembre) * 0.15)
    assert {t.navire_id for t in d.tarifs} == {n.navire_id for n in d.navires}


def test_statut_depuis_l_horloge(monkeypatch):
    debut, fin = datetime(2026, 10, 6, 8, tzinfo=FUSEAU), datetime(2026, 10, 6, 20, tzinfo=FUSEAU)
    assert generer.statut(debut, fin) == "accostee"
    monkeypatch.setenv("PHAROS_AUJOURDHUI", "2026-10-07")
    assert generer.statut(debut, fin) == "terminee"
    monkeypatch.setenv("PHAROS_AUJOURDHUI", "2026-10-05")
    assert generer.statut(debut, fin) == "prevue"
