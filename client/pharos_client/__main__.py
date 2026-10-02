"""python -m pharos_client [1|2|3|"une question"] — pose une question à la boucle et affiche l'arbre."""

from __future__ import annotations

import sys

from pharos_client.boucle import ArretBoucle, executer
from pharos_client.trace import afficher

QUESTIONS = {
    "1": "Quelles sont les pénalités de retard prévues au contrat de manutention de l'escale ESC-2026-0412 ?",
    "2": "Résume les obligations de l'opérateur portuaire pour l'escale ESC-2026-0412.",
    "3": "Quelle est la météo à Marseille jeudi ?",
}


def main(argv: list[str]) -> int:
    question = QUESTIONS.get(argv[0], " ".join(argv)) if argv else QUESTIONS["1"]
    print(f"Question : {question}\n")
    try:
        reponse, trace = executer(question)
    except ArretBoucle as arret:
        print(f"Arrêt : {arret}\n")
        afficher(arret.trace)
        return 1
    afficher(trace)
    print(f"\nRéponse :\n{reponse}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
