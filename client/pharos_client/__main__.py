"""python -m pharos_client [1|2|3|"une question"] — pose une question aux trois serveurs, derrière un plan visible,
et affiche le plan, l'arbre et la réponse (LAB 13 : labs/lab13/questions.md)."""

from __future__ import annotations

import sys

from pharos_client.boucle import ArretBoucle, executer
from pharos_client.trace import afficher

QUESTIONS = {
    "1": "L'escale du Vent d'Autan de jeudi est-elle à risque ? Si oui, prépare la note d'alerte pour l'exploitant.",
    "2": "Quelles sont les pénalités de retard prévues au contrat de manutention de l'escale ESC-2026-0412 ?",
    "3": "Quelles escales sont en conflit de créneau jeudi 8 octobre ?",
}


def main(argv: list[str]) -> int:
    question = QUESTIONS.get(argv[0], " ".join(argv)) if argv else QUESTIONS["1"]
    print(f"Question : {question}\n")
    try:
        execution = executer(question)
    except ArretBoucle as arret:
        print(f"Arrêt : {arret}\n")
        afficher(arret.trace)
        return 1
    afficher(execution.trace)
    print(f"\nRéponse :\n{execution.reponse}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
