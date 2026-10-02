"""Trace de la boucle — fourni : le format des enregistrements, et leur affichage en arbre.

Un enregistrement par appel d'outil, portant les cinq champs du bloc 8.5 :
  1. correlation      identifiant unique de l'exécution (le même pour tous ses appels)
  2. tour             numéro du tour du modèle qui a demandé l'appel (1, 2, …)
  3. outil, arguments nom et arguments normalisés — secrets masqués À L'ÉCRITURE
  4. duree_ms, octets durée de l'appel (ms) et taille du résultat (octets)
  5. tokens_cumules   contexte estimé AVANT l'appel au modèle de ce tour
  6. resultat, serveur texte rendu par l'outil (borné : borner()) et serveur qui l'a rendu — ce qui
                      permet de retrouver l'origine d'un chiffre (LAB 8, LAB 13)
Collecter pendant la boucle, afficher à la fin : afficher(trace). Dès que la trace compte plus d'un serveur
(LAB 13), chaque appel est précédé du serveur qui l'a servi : lequel a ralenti, lequel a produit la donnée.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Enregistrement:
    correlation: str
    tour: int
    outil: str
    arguments: dict
    duree_ms: float
    octets: int
    tokens_cumules: int
    erreur: bool = False
    resultat: str = ""
    serveur: str = ""


def borner(texte: str, limite: int = 4000) -> str:
    """Le résultat tel quel s'il est court ; sinon son début, suivi de sa taille réelle."""
    if len(texte) <= limite:
        return texte
    return f"{texte[:limite]}… [{len(texte.encode('utf-8'))} octets au total]"


def afficher(trace: list[Enregistrement], sortie=print) -> str:
    """Arbre exécution → tour → appels. Rend le texte, et l'écrit avec « sortie »."""
    if not trace:
        texte = "(trace vide : aucun appel d'outil)"
    else:
        lignes = []
        for correlation in dict.fromkeys(e.correlation for e in trace):
            execution = [e for e in trace if e.correlation == correlation]
            tours = list(dict.fromkeys(e.tour for e in execution))
            plusieurs = len({e.serveur for e in execution}) > 1
            lignes.append(f"exécution {correlation} — {len(execution)} appel(s), {len(tours)} tour(s)")
            for i, tour in enumerate(tours):
                appels = [e for e in execution if e.tour == tour]
                dernier = i == len(tours) - 1
                lignes.append(f"{'└─' if dernier else '├─'} tour {tour} · contexte {appels[0].tokens_cumules} tokens")
                marge = "   " if dernier else "│  "
                for j, e in enumerate(appels):
                    arguments = ", ".join(f"{k}={w}" for k, w in e.arguments.items())
                    origine = f"{e.serveur or '?'}  " if plusieurs else ""
                    lignes.append(f"{marge}{'└─' if j == len(appels) - 1 else '├─'} {origine}{e.outil}({arguments})"
                                  f" · {e.duree_ms:.0f} ms · {e.octets} o{' · isError' if e.erreur else ''}")
        texte = "\n".join(lignes)
    sortie(texte)
    return texte
