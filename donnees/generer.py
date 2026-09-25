"""Génère les PDF du corpus PHAROS, de façon déterministe (octet pour octet)."""

from __future__ import annotations

import io
import random
import sys
import zlib
from pathlib import Path

import yaml
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

from donnees import corpus as corpus_mod

SORTIE = Path(__file__).resolve().parent / "documents"
TITRE = ParagraphStyle("titre", fontName="Helvetica-Bold", fontSize=13, leading=17, spaceAfter=10)
CORPS = ParagraphStyle("corps", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=8)
LETTRES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def nom_fichier(escale_id: str, type_: str, document_id: str) -> str:
    return f"{escale_id}__{type_}__{document_id}.pdf"


def _echapper(texte: str) -> str:
    return texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _construire(flux: list, titre_doc: str) -> bytes:
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(
        tampon, pagesize=A4, invariant=1, title=titre_doc, author="PHAROS", subject=titre_doc,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    doc.build(list(flux))
    return tampon.getvalue()


def _paragraphes(texte: str) -> list:
    return [Paragraph(_echapper(p), CORPS) for p in texte.split("\n\n") if p.strip()]


def _pages_annexes(nb: int, graine: str) -> list:
    annexes = yaml.safe_load((corpus_mod.DOSSIER / "annexes.yaml").read_text(encoding="utf-8"))["annexes"]
    alea = random.Random(zlib.crc32(graine.encode()))
    flux = []
    for i in range(nb):
        annexe = annexes[i % len(annexes)]
        lignes = [annexe["colonnes"]] + [alea.choice(annexe["lignes"]) for _ in range(18)]
        table = Table(lignes, colWidths=[8 * cm, 5 * cm, 4 * cm])
        table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ]))
        flux += [Paragraph(f"Annexe {LETTRES[i % 26]}{i // 26 or ''} — {annexe['titre']}", TITRE),
                 Paragraph(f"Page {i + 1} des annexes au contrat {graine}.", CORPS), table, PageBreak()]
    return flux


def _contrat(c, e) -> bytes:
    articles = []
    for titre, texte in corpus_mod.articles_du_contrat(c, e):
        articles += [Paragraph(_echapper(titre), TITRE), *_paragraphes(texte), PageBreak()]
    cible = e.contrat.nb_pages
    pages_articles = len(PdfReader(io.BytesIO(_construire(articles[:-1], e.contrat.document_id))).pages)
    manque = cible - pages_articles
    if manque < 1:
        raise ValueError(f"{e.contrat.document_id} : {pages_articles} pages d'articles pour {cible} demandées")
    flux = articles + _pages_annexes(manque, e.contrat.document_id)
    flux = flux[:-1]  # pas de page blanche finale
    donnees = _construire(flux, e.contrat.document_id)
    obtenu = len(PdfReader(io.BytesIO(donnees)).pages)
    if obtenu != cible:
        raise ValueError(f"{e.contrat.document_id} : {obtenu} pages au lieu de {cible}")
    return donnees


def _document_simple(c, e, doc, type_: str) -> bytes:
    if type_ == "avis_escale":
        titre = f"Avis d'escale {doc.document_id}"
        texte = (f"Navire : {e.navire} (OMI {e.imo}). Armateur : {e.armateur}. Agent maritime : {e.agent}.\n\n"
                 f"Arrivée prévue au poste à quai n° {e.quai} le {corpus_mod.date_longue(e.debut.date())} "
                 f"à {e.debut:%H:%M}. Départ prévu le {corpus_mod.date_longue(e.fin.date())} à {e.fin:%H:%M}.\n\n"
                 f"Escale {e.escale_id}. Opérateur portuaire : {c.operateur}.")
    else:
        titre = f"Connaissement {doc.document_id}"
        texte = (f"Connaissement émis pour le compte de {e.armateur}, navire {e.navire}, escale {e.escale_id}.\n\n"
                 f"Marchandises : conteneurs de marchandises diverses, selon le manifeste joint. "
                 f"Port de déchargement : terminal exploité par {c.operateur}.")
    flux = [Paragraph(_echapper(titre), TITRE), *_paragraphes(texte)]
    for _ in range(doc.nb_pages - 1):
        flux += [PageBreak(), Paragraph(f"Manifeste — suite du {_echapper(titre)}", TITRE),
                 *_paragraphes("Détail des unités de charge conforme au manifeste transmis par l'agent maritime.")]
    return _construire(flux, doc.document_id)


def generer(dossier: Path = SORTIE) -> list[Path]:
    c = corpus_mod.charger()
    dossier.mkdir(parents=True, exist_ok=True)
    ecrits = []
    for e in c.escales:
        a_ecrire = [(e.avis_escale, "avis_escale", lambda d=e.avis_escale: _document_simple(c, e, d, "avis_escale"))]
        a_ecrire += [(d, "connaissement", lambda d=d: _document_simple(c, e, d, "connaissement")) for d in e.connaissements]
        if e.contrat:
            a_ecrire.append((e.contrat, "contrat_manutention", lambda: _contrat(c, e)))
        for doc, type_, fabriquer in a_ecrire:
            chemin = dossier / nom_fichier(e.escale_id, type_, doc.document_id)
            chemin.write_bytes(fabriquer())
            ecrits.append(chemin)
    return sorted(ecrits)


if __name__ == "__main__":
    for chemin in generer(Path(sys.argv[1]) if len(sys.argv) > 1 else SORTIE):
        print(chemin)
