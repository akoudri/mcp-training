"""Rapport du jeu d'évaluation (LAB 15) — à compléter : la comparaison à la référence est le critère décisif.

    python evaluation/rapport.py [RESULTAT] [--reference evaluation/reference.json]      (make lab15-rapport)

Fourni : lire un résultat, le tableau par cas, les taux par famille (outils.evaluation.resultats : charger, dernier,
par_cas, par_famille, global_, tableau ; un Taux a .famille, .reussites, .executions, .reussi et .valeur).

À écrire (étape 3) — comparer(courant, reference) :
  - pour chaque cas : famille, taux de référence, taux courant, écart ;
  - un seuil d'investigation par famille (SEUILS : les exécutions qu'une famille peut perdre) ;
  - une ligne « RÉGRESSION <id> (<famille>) : <avant> → <après> » par cas fautif ;
  - rouge (code de sortie 1) si une famille passe sous son seuil.
Le rapport doit se lire sans ouvrir une trace : à trois heures du matin, c'est lui seul qu'on lira.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from outils.evaluation import resultats

REFERENCE = Path("evaluation/reference.json")
# Exécutions qu'une famille peut perdre par rapport à la référence avant d'investiguer : à décider (et à justifier).
SEUILS: dict[str, int] = {}


def comparer(courant: dict, reference: dict) -> tuple[list[str], bool]:
    """Rend (les lignes de la comparaison, rouge ?)."""
    raise NotImplementedError("comparer(courant, reference) n'est pas encore écrit (LAB 15, étape 3).")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="evaluation/rapport.py")
    p.add_argument("resultat", nargs="?", help="sortie/lab15/<horodatage>.json (défaut : le plus récent)")
    p.add_argument("--reference", default=str(REFERENCE))
    a = p.parse_args(argv)
    if a.resultat and not Path(a.resultat).exists():
        print(f"Résultat introuvable : {a.resultat} (make lab15-lancer en écrit un dans sortie/lab15/).")
        return 1
    try:
        courant = resultats.charger(Path(a.resultat) if a.resultat else resultats.dernier())
    except FileNotFoundError as exc:      # sortie/lab15/ vide
        print(exc)
        return 1
    print(resultats.tableau(courant))
    chemin = Path(a.reference)
    reference = json.loads(chemin.read_text(encoding="utf-8") or "{}") if chemin.exists() else {}
    if not reference.get("cas"):
        print("\nAucune référence à comparer : make lab15-referencer fige un résultat comme référence.")
        return 0
    try:
        lignes, rouge = comparer(courant, reference)
    except NotImplementedError as exc:
        print(f"\nComparaison impossible : {exc}")
        return 2
    print("\n" + "\n".join(lignes))
    return 1 if rouge else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
