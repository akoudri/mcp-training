"""pharos-docs-demo — serveur de démonstration du LAB 0.

Ses descriptions sont volontairement longues : l'extension A du LAB 0 mesure ce
qu'elles coûtent en tokens. lister_documents et rechercher_clause portent les noms
imposés par le brief du LAB 0 et coïncident avec deux outils du LAB 1 : pour ne pas
en livrer la solution, leurs erreurs métier sont volontairement pauvres (écrire des
erreurs utiles au modèle est l'objet du LAB 1).
"""

from __future__ import annotations

import os
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from pharos_docs import extraction

MAX_PAGES = 20
Sujet = Literal["penalites", "delais", "manutention", "assurance"]
TITRES_SUJETS = {"penalites": "pénalités", "delais": "délais", "manutention": "manutention", "assurance": "assurance"}

EscaleId = Annotated[str, Field(description=(
    "Identifiant de l'escale au format ESC-AAAA-NNNN, où AAAA est l'année et NNNN le numéro "
    "d'ordre sur quatre chiffres, par exemple ESC-2026-0412. Respecter les majuscules."))]
DocumentId = Annotated[str, Field(description=(
    "Identifiant du document tel que renvoyé par lister_documents, par exemple CM-0412 pour un "
    "contrat de manutention, BL-0412-1 pour un connaissement ou AE-0412 pour un avis d'escale."))]
SujetArg = Annotated[Sujet, Field(description=(
    "Sujet de la clause recherchée : penalites (pénalités de retard et leur plafond), delais "
    "(délais de mise à quai et durée d'escale), manutention (opérations et moyens engagés), "
    "assurance (couverture de responsabilité de l'opérateur)."))]


def _contrat(escale_id: str) -> extraction.Document:
    docs = extraction.documents_de_escale(escale_id)
    if not docs:
        raise ToolError("Escale inconnue.")
    contrat = next((d for d in docs if d.type == "contrat_manutention"), None)
    if contrat is None:
        raise ToolError("Pas de contrat de manutention pour cette escale.")
    return contrat


def creer_serveur(outil_jumeau: bool = False) -> FastMCP:
    mcp = FastMCP("pharos-docs-demo", instructions=(
        "Serveur de démonstration PHAROS : documents déposés par les agents maritimes pour chaque escale."))

    @mcp.tool
    def lister_documents(escale_id: EscaleId) -> dict:
        """Liste tous les documents rattachés à une escale du port : contrats de manutention,
        connaissements et avis d'escale, avec pour chacun son identifiant, son type et son nombre
        de pages. À appeler en premier pour savoir quels documents existent avant de les lire ou d'y
        rechercher une clause. Une escale sans document renvoie une liste vide."""
        docs = extraction.documents_de_escale(escale_id)
        return {"escale_id": escale_id, "documents": [
            {"document_id": d.document_id, "type": d.type, "nb_pages": d.nb_pages} for d in docs]}

    @mcp.tool
    def lire_document(document_id: DocumentId,
                      page_debut: Annotated[int, Field(ge=1, description="Première page à lire, à partir de 1.")] = 1,
                      page_fin: Annotated[int, Field(ge=1, description=f"Dernière page à lire, incluse ; au plus {MAX_PAGES} pages par appel.")] = 1) -> dict:
        """Renvoie le texte intégral d'un document, page par page, sur une plage de pages donnée.
        Utile pour lire un avis d'escale ou un connaissement en entier, ou pour parcourir un
        contrat de manutention par morceaux. Les contrats font de quarante à quatre-vingts pages :
        préférer rechercher_clause pour une question précise."""
        try:
            pages = extraction.texte_du_document(document_id)
        except extraction.DocumentInconnu:
            raise ToolError(f"Document inconnu : {document_id}. Utiliser lister_documents pour obtenir les identifiants d'une escale.")
        if page_fin < page_debut:
            raise ToolError(f"page_debut ({page_debut}) doit être inférieure ou égale à page_fin ({page_fin}).")
        if page_fin - page_debut + 1 > MAX_PAGES:
            raise ToolError(f"Au plus {MAX_PAGES} pages par appel ; découper la lecture en plusieurs appels.")
        if page_fin > len(pages):
            raise ToolError(f"Le document {document_id} compte {len(pages)} pages ; demander une plage comprise entre 1 et {len(pages)}.")
        return {"document_id": document_id, "pages": [
            {"numero": p.numero, "texte": p.texte} for p in pages[page_debut - 1:page_fin]]}

    def _rechercher_clause(escale_id: str, sujet: str) -> dict:
        contrat = _contrat(escale_id)
        sections = [s for s in extraction.sections_du_document(contrat.document_id) if s.titre.startswith("Article")]
        cible = TITRES_SUJETS[sujet]
        section = next((s for s in sections if cible in s.titre.casefold()), None)
        if section is None:
            raise ToolError("Clause introuvable.")
        pages = extraction.texte_du_document(contrat.document_id)[section.page_debut - 1:section.page_fin]
        return {"document_id": contrat.document_id, "article": section.titre, "page": section.page_debut,
                "texte": "\n".join(p.texte for p in pages)[:4000]}

    @mcp.tool
    def rechercher_clause(escale_id: EscaleId, sujet: SujetArg) -> dict:
        """Recherche, dans le contrat de manutention d'une escale, l'article qui traite d'un sujet
        donné, et renvoie son titre, sa page de début et son texte. C'est le moyen le plus direct de
        répondre à une question sur les pénalités de retard, les délais de mise à quai, les moyens
        de manutention engagés ou l'assurance de l'opérateur portuaire, sans lire le contrat entier."""
        return _rechercher_clause(escale_id, sujet)

    if outil_jumeau:
        @mcp.tool
        def chercher_clause_contrat(escale_id: EscaleId, sujet: SujetArg) -> dict:
            """Recherche dans le contrat de manutention d'une escale la clause correspondant à un
            sujet, et renvoie le texte de cette clause avec sa page. Permet de répondre à une question
            sur les pénalités, les délais, la manutention ou l'assurance sans lire tout le contrat."""
            return _rechercher_clause(escale_id, sujet)

    return mcp


def main() -> None:
    from pathlib import Path

    from starlette.middleware import Middleware

    from labs.lab0.serveur.journal import JournalJSONL

    serveur = creer_serveur(outil_jumeau=os.environ.get("PHAROS_OUTIL_JUMEAU") == "1")
    intergiciels = []
    if os.environ.get("VERBEUX") == "1":
        intergiciels.append(Middleware(JournalJSONL, chemin=Path("logs/pharos-docs-demo.jsonl")))
    serveur.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
                path="/mcp", json_response=True, show_banner=False, middleware=intergiciels)


if __name__ == "__main__":
    main()
