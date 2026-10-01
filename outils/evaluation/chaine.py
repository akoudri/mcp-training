"""La chaîne d'évaluation (LAB 15) : relancer le jeu seulement quand l'un de ses trois déclencheurs a bougé.

    lancer, motifs = decider(reference, courantes, publication=False)

Les déclencheurs (bloc 26.4) : le modèle, le catalogue agrégé, le prompt système — comparés par empreinte à celles
de evaluation/reference.json — et, en plus, toute publication (un tag v*, PUBLICATION=1). Rien n'a bougé et rien
n'est publié : « rien à lancer », la chaîne sort en vert sans exécuter le jeu (et sans rien dépenser).
"""

from __future__ import annotations

DECLENCHEURS = {"modele": "le modèle", "catalogue": "le catalogue agrégé", "prompt": "le prompt système"}


def decider(reference: dict, courantes: dict, publication: bool = False) -> tuple[bool, list[str]]:
    attendues = (reference or {}).get("empreintes") or {}
    if not attendues:
        return True, ["aucune référence (evaluation/reference.json vide) : make lab15-referencer après un premier jeu"]
    motifs = [f"{libelle} a changé ({attendues.get(cle) or '—'} → {courantes.get(cle)})"
              for cle, libelle in DECLENCHEURS.items() if attendues.get(cle) != courantes.get(cle)]
    if publication:
        motifs.append("publication demandée (tag v*)")
    return bool(motifs), motifs
