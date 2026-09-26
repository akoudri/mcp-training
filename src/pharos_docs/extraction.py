"""Couche d'extraction documentaire de PHAROS — fournie, à utiliser telle quelle.

Indexe les PDF nommés <escale_id>__<type>__<document_id>.pdf présents dans les
répertoires de PHAROS_DOCUMENTS (séparés par « : »).

Si deux répertoires contiennent un document de même document_id, le dernier
répertoire de PHAROS_DOCUMENTS l'emporte : son fichier masque les précédents.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

journal = logging.getLogger(__name__)

TYPES = ("contrat_manutention", "connaissement", "avis_escale")
NOM = re.compile(r"^(ESC-\d{4}-\d{4})__([a-z_]+)__([A-Za-z0-9-]+)\.pdf$")
ENTETE_SECTION = re.compile(r"^(Article \d+|Annexe [A-Z]\d*) — .+$")
DEFAUT = "donnees/documents"


@dataclass(frozen=True)
class Document:
    document_id: str
    type: str
    escale_id: str
    nb_pages: int


@dataclass(frozen=True)
class Page:
    numero: int
    texte: str


@dataclass(frozen=True)
class Occurrence:
    page: int
    texte: str
    score: float


@dataclass(frozen=True)
class Section:
    titre: str
    page_debut: int
    page_fin: int


class DocumentInconnu(LookupError):
    """Aucun document indexé ne porte cet identifiant."""


def _repertoires() -> list[Path]:
    return [Path(r) for r in os.environ.get("PHAROS_DOCUMENTS", DEFAUT).split(":") if r]


@lru_cache(maxsize=256)
def _lire(chemin: str, _mtime: float) -> tuple[Page, ...]:
    lecteur = PdfReader(chemin)
    return tuple(Page(numero=i + 1, texte=p.extract_text() or "") for i, p in enumerate(lecteur.pages))


def _pages(chemin: Path) -> tuple[Page, ...]:
    return _lire(str(chemin), chemin.stat().st_mtime)


def _index() -> dict[str, tuple[Path, Document]]:
    index: dict[str, tuple[Path, Document]] = {}
    for repertoire in _repertoires():
        if not repertoire.is_dir():
            continue
        for chemin in sorted(repertoire.glob("*.pdf")):
            m = NOM.match(chemin.name)
            if not m or m.group(2) not in TYPES:
                journal.warning("fichier ignoré, hors convention de nommage : %s", chemin.name)
                continue
            escale_id, type_, document_id = m.groups()
            try:
                nb_pages = len(_pages(chemin))
            except (PdfReadError, OSError, ValueError) as exc:
                journal.warning("fichier ignoré, PDF illisible : %s (%s)", chemin.name, exc)
                continue
            index[document_id] = (chemin, Document(document_id, type_, escale_id, nb_pages))
    return index


def documents_de_escale(escale_id: str) -> list[Document]:
    """Documents rattachés à l'escale ; liste vide si l'escale est inconnue."""
    return [doc for _, doc in _index().values() if doc.escale_id == escale_id]


def documents() -> list[Document]:
    """Tous les documents indexés, triés par identifiant."""
    return sorted((doc for _, doc in _index().values()), key=lambda d: d.document_id)


def texte_du_document(document_id: str) -> list[Page]:
    entree = _index().get(document_id)
    if entree is None:
        raise DocumentInconnu(document_id)
    return list(_pages(entree[0]))


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accents.casefold()


def rechercher_dans_texte(pages: list[Page], motif: str) -> list[Occurrence]:
    """Paragraphes contenant les mots du motif (≥ 3 lettres), du plus au moins pertinent."""
    mots = [m for m in re.findall(r"\w+", _normaliser(motif)) if len(m) >= 3]
    if not mots:
        return []
    resultats = []
    for page in pages:
        for paragraphe in re.split(r"\n(?=[A-ZÀ-Ý])", page.texte):
            normal = _normaliser(paragraphe)
            touches = sum(1 for m in mots if m in normal)
            if touches:
                frequence = sum(normal.count(m) for m in mots)
                score = touches / len(mots) + frequence / 100
                resultats.append(Occurrence(page.numero, paragraphe.strip()[:600], round(score, 3)))
    return sorted(resultats, key=lambda o: (-o.score, o.page))


def sections_du_document(document_id: str) -> list[Section]:
    """Articles et annexes, avec leurs pages de début et de fin."""
    pages = texte_du_document(document_id)
    debuts = []
    for page in pages:
        premiere = page.texte.strip().splitlines()[0] if page.texte.strip() else ""
        if ENTETE_SECTION.match(premiere):
            debuts.append((premiere, page.numero))
    sections = []
    for i, (titre, debut) in enumerate(debuts):
        fin = debuts[i + 1][1] - 1 if i + 1 < len(debuts) else len(pages)
        sections.append(Section(titre, debut, fin))
    return sections
