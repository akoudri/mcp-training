import logging
import shutil
from pathlib import Path

import pytest

from pharos_docs import extraction

DOCS = Path("donnees/documents").resolve()


@pytest.fixture(autouse=True)
def corpus_de_base(monkeypatch):
    monkeypatch.setenv("PHAROS_DOCUMENTS", str(DOCS))


def test_documents_de_l_escale_de_reference():
    docs = extraction.documents_de_escale("ESC-2026-0412")
    types = sorted(d.type for d in docs)
    assert types == ["avis_escale", "connaissement", "connaissement", "contrat_manutention"]
    contrat = next(d for d in docs if d.type == "contrat_manutention")
    assert contrat.document_id == "CM-0412" and contrat.nb_pages == 56


def test_escale_inconnue_ou_mal_formee_donne_une_liste_vide():
    assert extraction.documents_de_escale("ESC-2026-9999") == []
    assert extraction.documents_de_escale("esc-2026-0412") == []


def test_texte_par_page():
    pages = extraction.texte_du_document("CM-0412")
    assert len(pages) == 56 and pages[0].numero == 1
    assert "Vent d'Autan" in pages[0].texte


def test_document_inconnu():
    with pytest.raises(extraction.DocumentInconnu):
        extraction.texte_du_document("CM-9999")


def test_recherche_insensible_aux_accents_et_a_la_casse():
    pages = extraction.texte_du_document("CM-0412")
    occ = extraction.rechercher_dans_texte(pages, "PENALITE retard")
    assert occ and occ[0].score > 0
    assert "1 850 €" in " ".join(o.texte for o in occ[:3])
    assert occ == sorted(occ, key=lambda o: -o.score)


def test_recherche_sans_resultat():
    pages = extraction.texte_du_document("AE-0412")
    assert extraction.rechercher_dans_texte(pages, "cryptomonnaie") == []


def test_sections_du_contrat():
    sections = extraction.sections_du_document("CM-0412")
    titres = [s.titre for s in sections]
    assert "Article 7 — Pénalités de retard" in titres
    penalites = next(s for s in sections if s.titre.startswith("Article 7"))
    assert penalites.page_debut <= penalites.page_fin
    assert sections[-1].page_fin == 56


def test_contrat_sans_assurance():
    titres = [s.titre for s in extraction.sections_du_document("CM-0408")]
    assert not any("Assurance" in t for t in titres)


def test_plusieurs_repertoires_et_fichiers_hors_convention(tmp_path, monkeypatch, caplog):
    depot = tmp_path / "depot"
    depot.mkdir()
    shutil.copy(DOCS / "ESC-2026-0405__avis_escale__AE-0405.pdf", depot / "ESC-2026-0412__avis_escale__AE-0412-BIS.pdf")
    (depot / "notes.pdf").write_bytes(b"%PDF-1.4 hors convention")
    (depot / "ESC-2026-0412__facture__F-1.pdf").write_bytes(b"%PDF type inconnu")
    (depot / "ESC-2026-0412__connaissement__BL-CORROMPU.pdf").write_bytes(b"pas un pdf")
    monkeypatch.setenv("PHAROS_DOCUMENTS", f"{DOCS}:{depot}")
    with caplog.at_level(logging.WARNING, logger="pharos_docs.extraction"):
        ids = {d.document_id for d in extraction.documents_de_escale("ESC-2026-0412")}
    assert "AE-0412-BIS" in ids
    assert "F-1" not in ids and "BL-CORROMPU" not in ids
    assert "notes.pdf" in caplog.text and "BL-CORROMPU" in caplog.text


def test_repertoire_absent_ignore(monkeypatch):
    monkeypatch.setenv("PHAROS_DOCUMENTS", f"{DOCS}:/inexistant")
    assert extraction.documents_de_escale("ESC-2026-0412")


def test_documents_tries_et_complets(monkeypatch):
    monkeypatch.setenv("PHAROS_DOCUMENTS", "donnees/documents")
    docs = extraction.documents()
    assert len(docs) == 27
    assert [d.document_id for d in docs] == sorted(d.document_id for d in docs)
    assert next(d for d in docs if d.document_id == "CM-0409").nb_pages == 80
