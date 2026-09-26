"""RessourceAvecTaille — fourni : fastmcp 4.0.10 n'annonce pas la taille d'une ressource ; cette sous-classe l'ajoute.

La taille est celle du contenu renvoyé par resources/read, en octets UTF-8 — la calculer juste est votre
travail : l'hôte décide sur elle d'attacher ou de proposer.

    mcp.add_resource(RessourceAvecTaille(uri=…, name=…, mime_type="text/plain", text=texte,
                                         taille=len(texte.encode("utf-8"))))
"""

from __future__ import annotations

from typing import Any

from fastmcp.resources import TextResource


class RessourceAvecTaille(TextResource):
    taille: int

    def to_mcp_resource(self, **overrides: Any):
        return super().to_mcp_resource(**overrides).model_copy(update={"size": self.taille})
