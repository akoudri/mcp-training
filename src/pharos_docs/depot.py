"""Dépôt de document au format du corpus (LAB 14) — fourni.

Transforme un Markdown (le document piégé de l'attaquant) en PDF nommé comme le corpus PHAROS
(<escale_id>__contrat_manutention__<document_id>.pdf), pour que pharos-docs l'indexe et le serve comme
n'importe quel contrat. C'est le seul vecteur du LAB 14 : le CONTENU d'un document déposé dans le
dépôt partagé de la cible (jamais le réseau, la machine ou les mocks).

    chemin = ecrire_pdf(markdown, escale_id="ESC-2026-0412", suffixe="inj1", dossier=Path("contrats-partages/binome-3"))

Le PDF n'est pas déterministe au niveau octet (peu importe : il n'entre pas dans les etat/*), mais son
texte extrait par pharos_docs.extraction est bien le Markdown déposé.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate

TITRE = ParagraphStyle("titre", fontName="Helvetica-Bold", fontSize=13, leading=17, spaceAfter=10)
CORPS = ParagraphStyle("corps", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=8)
ESCALE = re.compile(r"^ESC-\d{4}-\d{4}$")


def _echapper(texte: str) -> str:
    return texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _flux(markdown: str) -> list:
    """Chaque ligne « # … » devient un titre, chaque paragraphe un Paragraph — le texte extrait reste fidèle."""
    flux: list = []
    for bloc in markdown.split("\n\n"):
        bloc = bloc.strip()
        if not bloc:
            continue
        style = TITRE if bloc.startswith("#") else CORPS
        sans_prefixe = re.sub(r"^#+\s*", "", bloc)   # seul le préfixe de titre (« # », « ## », …) est retiré
        flux.append(Paragraph(_echapper(sans_prefixe.replace("\n", "<br/>")), style))
    return flux or [Paragraph("(document vide)", CORPS)]


def construire_pdf(markdown: str, titre_doc: str = "Contrat de manutention") -> bytes:
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, title=titre_doc, author="PHAROS",
                            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    doc.build(_flux(markdown))
    donnees = tampon.getvalue()
    PdfReader(io.BytesIO(donnees))            # garde-fou : le PDF produit est relisible
    return donnees


def ecrire_pdf(markdown: str, *, escale_id: str = "ESC-2026-0412", suffixe: str = "inj",
               dossier: Path) -> Path:
    """Écrit le PDF dans « dossier » sous <escale_id>__contrat_manutention__CM-<escale>-<suffixe>.pdf."""
    if not ESCALE.match(escale_id):
        raise ValueError(f"escale_id invalide : {escale_id} (format ESC-AAAA-NNNN).")
    numero = escale_id.split("-")[-1]
    document_id = f"CM-{numero}-{re.sub(r'[^A-Za-z0-9-]+', '', suffixe) or 'inj'}"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{escale_id}__contrat_manutention__{document_id}.pdf"
    chemin.write_bytes(construire_pdf(markdown))
    return chemin
