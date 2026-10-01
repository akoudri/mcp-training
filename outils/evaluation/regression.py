"""La régression du LAB 15 : renommer navire_par_nom de pharos-ops en « resoudre », sans toucher à sa description.

    python3 -m outils.evaluation.regression            (make lab15-regression)          pose la régression
    python3 -m outils.evaluation.regression --retirer  (make lab15-regression-retirer)  la retire

Modification réversible et marquée de serveurs/pharos_ops/serveur.py (le commentaire « RÉGRESSION LAB 15 ») ; la
cible make redémarre pharos-ops. Bibliothèque standard uniquement : lancé par python3 sur le poste.
"""

from __future__ import annotations

import sys
from pathlib import Path

SERVEUR = Path("serveurs/pharos_ops/serveur.py")
SAIN = '@mcp.tool(name="navire_par_nom",'
REGRESSE = '@mcp.tool(name="resoudre",  # RÉGRESSION LAB 15 — make lab15-regression-retirer'


class RegressionImpossible(Exception):
    pass


def appliquer(source: str) -> str:
    if REGRESSE in source:
        raise RegressionImpossible("la régression est déjà posée (make lab15-regression-retirer pour la retirer).")
    if source.count(SAIN) != 1:
        raise RegressionImpossible(f"déclaration introuvable dans {SERVEUR} : « {SAIN} » (pharos-ops du LAB 14 "
                                   "attendu, etat/sg1-fin).")
    return source.replace(SAIN, REGRESSE)


def retirer(source: str) -> str:
    if REGRESSE not in source:
        raise RegressionImpossible("aucune régression posée : rien à retirer.")
    return source.replace(REGRESSE, SAIN)


def main(argv: list[str]) -> int:
    retrait = "--retirer" in argv
    if not SERVEUR.exists():
        print(f"{SERVEUR} absent : ce lab part de etat/sg1-fin (make depart LAB=15).")
        return 1
    try:
        texte = (retirer if retrait else appliquer)(SERVEUR.read_text(encoding="utf-8"))
    except RegressionImpossible as exc:
        print(f"Rien de fait : {exc}")
        return 1
    SERVEUR.write_text(texte, encoding="utf-8")
    print("Régression retirée : l'outil a retrouvé son nom." if retrait else
          "Régression posée : un outil de pharos-ops a changé de nom, sa description est intacte.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
