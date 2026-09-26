"""pharos-docs v0 — LAB 1. Squelette à compléter.

Exposer exactement trois outils, et rien d'autre : lister_documents, rechercher_clause,
extraire_dates_contractuelles (voir le brief). La couche d'extraction est fournie et testée :
    from pharos_docs import extraction
    extraction.documents_de_escale(escale_id) -> list[Document]
    extraction.texte_du_document(document_id) -> list[Page]
    extraction.rechercher_dans_texte(pages, motif) -> list[Occurrence]
    extraction.sections_du_document(document_id) -> list[Section]

Une erreur métier se signale par « raise ToolError("message") » : le client reçoit un résultat
isError, que le modèle peut lire. Une autre exception devient « Error calling tool … » : à éviter.

Laisser l'objet « mcp » au niveau du module : les tests du LAB 7 l'importent.
"""

from __future__ import annotations

import os
from typing import Annotated, Literal  # noqa: F401 — utiles pour les schémas (Literal pour une énumération)

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field  # noqa: F401 — Annotated[str, Field(description=...)] décrit un paramètre

from pharos_docs import extraction  # noqa: F401

mcp = FastMCP("pharos-docs")


@mcp.tool
def lister_documents(escale_id: str) -> dict:
    """À écrire : à quoi sert l'outil, en une ou deux phrases — pas comment il est écrit."""
    raise ToolError("Outil pas encore écrit.")


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
            path="/mcp", json_response=True, show_banner=False)
