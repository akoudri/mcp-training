import hashlib
from pathlib import Path

import pytest
from pypdf import PdfReader

from donnees import corpus, generer


@pytest.fixture(scope="module")
def pdfs(tmp_path_factory):
    return generer.generer(tmp_path_factory.mktemp("docs"))


def test_nombre_de_fichiers_et_nommage(pdfs):
    c = corpus.charger()
    attendus = sum(1 + len(e.connaissements) + (e.contrat is not None) for e in c.escales)
    assert len(pdfs) == attendus
    assert "ESC-2026-0412__contrat_manutention__CM-0412.pdf" in {p.name for p in pdfs}


def test_nombre_de_pages_exact(pdfs):
    c = corpus.charger()
    par_nom = {p.name: p for p in pdfs}
    for e in c.escales:
        if e.contrat:
            nom = generer.nom_fichier(e.escale_id, "contrat_manutention", e.contrat.document_id)
            assert len(PdfReader(par_nom[nom]).pages) == e.contrat.nb_pages, nom


def test_texte_extractible_avec_accents_et_euros(pdfs):
    chemin = next(p for p in pdfs if p.name.startswith("ESC-2026-0412__contrat"))
    lecteur = PdfReader(chemin)
    texte = "\n".join(page.extract_text() for page in lecteur.pages[:12])
    assert "Vent d'Autan" in texte
    assert "1 850 €" in texte
    assert "Article 3 — Obligations de l'opérateur portuaire" in texte


def test_chaque_article_ouvre_une_page(pdfs):
    chemin = next(p for p in pdfs if p.name.startswith("ESC-2026-0412__contrat"))
    premieres_lignes = [p.extract_text().splitlines()[0] for p in PdfReader(chemin).pages]
    articles = [l for l in premieres_lignes if l.startswith("Article ")]
    assert len(articles) == len(corpus.articles_du_contrat(corpus.charger(), corpus.charger().escale("ESC-2026-0412")))
    assert any(l.startswith("Annexe ") for l in premieres_lignes)


def test_generation_deterministe(tmp_path):
    a = generer.generer(tmp_path / "a")
    b = generer.generer(tmp_path / "b")
    empreinte = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert [empreinte(p) for p in a] == [empreinte(p) for p in b]


def test_documents_versionnes_a_jour(tmp_path):
    frais = {p.name: p.read_bytes() for p in generer.generer(tmp_path)}
    versionnes = {p.name: p.read_bytes() for p in Path("donnees/documents").glob("*.pdf")}
    assert frais == versionnes, "Lancer `make fixtures` et commiter donnees/documents/"
