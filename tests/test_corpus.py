from datetime import date

import pytest

from donnees import corpus


@pytest.fixture(scope="module")
def c():
    return corpus.charger()


def test_huit_escales_dans_la_semaine(c):
    assert len(c.escales) == 8
    jours = {e.debut.date() for e in c.escales}
    assert min(jours) >= date(2026, 10, 5) and max(jours) <= date(2026, 10, 9)


def test_escale_de_reference(c):
    e = c.escale("ESC-2026-0412")
    assert e.navire == "Vent d'Autan"
    assert e.debut.date() == date(2026, 10, 8) and e.debut.isoweekday() == 4
    assert e.contrat.valeurs["montant_horaire"] == 1850
    assert e.contrat.valeurs["franchise_h"] == 6


def test_cas_particuliers(c):
    assert sum(e.contrat is None for e in c.escales) == 1
    avec_contrat = [e for e in c.escales if e.contrat]
    assert sum("assurance" not in e.contrat.sujets for e in avec_contrat) == 1
    assert sum(e.contrat.nb_pages == 80 for e in avec_contrat) == 1
    assert all(40 <= e.contrat.nb_pages <= 80 for e in avec_contrat)


def test_identifiants_uniques_et_bien_formes(c):
    import re
    ids = [e.escale_id for e in c.escales]
    assert len(set(ids)) == 8
    assert all(re.fullmatch(r"ESC-\d{4}-\d{4}", i) for i in ids)
    docs = [d.document_id for e in c.escales for d in e.connaissements + [e.avis_escale]]
    docs += [e.contrat.document_id for e in c.escales if e.contrat]
    assert len(docs) == len(set(docs))


def test_articles_numerotes_et_rendus(c):
    articles = corpus.articles_du_contrat(c, c.escale("ESC-2026-0412"))
    titres = [t for t, _ in articles]
    assert titres[0] == "Article 1 — Objet"
    assert "Article 7 — Pénalités de retard" in titres
    texte = dict(articles)["Article 7 — Pénalités de retard"]
    assert "1 850 €" in texte and "6 heures" in texte
    assert all("{" not in t for _, t in articles)


def test_article_assurance_omis_et_numerotation_continue(c):
    articles = corpus.articles_du_contrat(c, c.escale("ESC-2026-0408"))
    titres = [t for t, _ in articles]
    assert not any("Assurance" in t for t in titres)
    numeros = [int(t.split()[1]) for t in titres]
    assert numeros == list(range(1, len(titres) + 1))


def test_escale_inconnue(c):
    with pytest.raises(KeyError):
        c.escale("ESC-2026-9999")
