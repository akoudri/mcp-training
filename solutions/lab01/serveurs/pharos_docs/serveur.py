"""pharos-docs v0 — solution de référence du LAB 1."""

from __future__ import annotations

import os
import re
from datetime import date
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from pharos_docs import extraction

mcp = FastMCP("pharos-docs")

EXTRAIT_MAX = 1500
Sujet = Literal["penalites", "delais", "manutention", "assurance"]
TITRES = {"penalites": "pénalités", "delais": "délais", "manutention": "manutention", "assurance": "assurance"}
MOIS = {m: i for i, m in enumerate(["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                                    "septembre", "octobre", "novembre", "décembre"], start=1)}
DATE = re.compile(r"(\d{1,2})(?:er)?\s+(" + "|".join(MOIS) + r")\s+(\d{4})")

EscaleId = Annotated[str, Field(description="Identifiant d'escale au format ESC-AAAA-NNNN, par exemple ESC-2026-0412.")]
SujetArg = Annotated[Sujet, Field(description="Sujet de la clause : penalites, delais, manutention ou assurance.")]


def _documents(escale_id: str) -> list[extraction.Document]:
    docs = sorted(extraction.documents_de_escale(escale_id), key=lambda d: d.document_id)
    if not docs:
        raise ToolError(f"Escale inconnue : {escale_id}. Le format attendu est ESC-AAAA-NNNN (par exemple "
                        "ESC-2026-0412). Vérifier l'identifiant auprès de l'utilisateur ; lister_documents "
                        "donne les documents d'une escale existante.")
    return docs


def _contrat(escale_id: str) -> extraction.Document:
    docs = _documents(escale_id)
    contrat = next((d for d in docs if d.type == "contrat_manutention"), None)
    if contrat is None:
        autres = ", ".join(f"{d.document_id} ({d.type})" for d in docs)
        raise ToolError(f"L'escale {escale_id} n'a pas de contrat de manutention. Documents disponibles : {autres}. "
                        "La question ne peut pas être tranchée par un contrat : le dire à l'utilisateur.")
    return contrat


def _articles(contrat: extraction.Document) -> list[extraction.Section]:
    return [s for s in extraction.sections_du_document(contrat.document_id) if s.titre.startswith("Article")]


@mcp.tool
def lister_documents(escale_id: EscaleId) -> dict:
    """Liste les documents rattachés à une escale — contrat de manutention, connaissements, avis d'escale — avec leur type et leur nombre de pages."""
    return {"escale_id": escale_id, "documents": [
        {"document_id": d.document_id, "type": d.type, "nb_pages": d.nb_pages} for d in _documents(escale_id)]}


@mcp.tool
def rechercher_clause(escale_id: EscaleId, sujet: SujetArg) -> dict:
    """Recherche, dans le contrat de manutention d'une escale, la clause qui traite d'un sujet, et renvoie son texte et sa page."""
    contrat = _contrat(escale_id)
    articles = _articles(contrat)
    section = next((s for s in articles if TITRES[sujet] in s.titre.casefold()), None)
    if section is None:
        presents = [c for c, t in TITRES.items() if any(t in s.titre.casefold() for s in articles)]
        raise ToolError(f"Le contrat {contrat.document_id} ne contient pas de clause « {sujet} ». "
                        f"Sujets présents dans ce contrat : {', '.join(presents)}.")
    page = extraction.texte_du_document(contrat.document_id)[section.page_debut - 1]
    texte = page.texte.split("\n", 1)[1].strip() if "\n" in page.texte else page.texte
    return {"document_id": contrat.document_id, "article": section.titre, "page": section.page_debut,
            "texte": texte[:EXTRAIT_MAX]}


@mcp.tool
def extraire_dates_contractuelles(escale_id: EscaleId) -> dict:
    """Donne les dates du contrat de manutention d'une escale : signature, prise d'effet et échéance."""
    contrat = _contrat(escale_id)
    pages = extraction.texte_du_document(contrat.document_id)
    for occurrence in extraction.rechercher_dans_texte(pages, "signé prend effet échéance"):
        dates = [date(int(a), MOIS[m], int(j)) for j, m, a in DATE.findall(occurrence.texte)]
        if len(dates) >= 3:
            return {"document_id": contrat.document_id, "page": occurrence.page, "signature": dates[0].isoformat(),
                    "prise_effet": dates[1].isoformat(), "echeance": dates[2].isoformat()}
    raise ToolError(f"Les dates du contrat {contrat.document_id} n'ont pas été trouvées dans l'article « Durée ».")


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
            path="/mcp", json_response=True, show_banner=False)
