"""Mouvements de conteneurs par escale, pour pharos-legacy (LAB 2, 3).

Générés une fois, de façon déterministe, et versionnés dans mouvements.yaml :
    python -m donnees.legacy.mouvements
Le test du kit vérifie que le fichier versionné est bien celui que ce script produit.
"""

from __future__ import annotations

import random
from datetime import timedelta
from pathlib import Path

import yaml

from donnees import corpus

FICHIER = Path(__file__).resolve().parent / "mouvements.yaml"
# ESC-2026-0412 fait trois pages de 20 ; les autres escales entre 0 et 45 mouvements.
NOMBRES = {"ESC-2026-0405": 38, "ESC-2026-0406": 12, "ESC-2026-0408": 45, "ESC-2026-0409": 0,
           "ESC-2026-0410": 24, "ESC-2026-0411": 31, "ESC-2026-0412": 57, "ESC-2026-0414": 7}
TYPES = ("20", "40", "reefer")
STATUTS = ("prévu", "effectué", "bloqué douane")
PREFIXES = ("PHRU", "MSKU", "CMAU", "TGHU")


def _mouvements(escale: corpus.Escale, nombre: int) -> list[dict]:
    alea = random.Random(escale.escale_id)
    duree = (escale.fin - escale.debut).total_seconds()
    heures = sorted(escale.debut + timedelta(minutes=int(alea.uniform(0, duree) // 60 // 5 * 5))
                    for _ in range(nombre))
    return [{
        "conteneur": f"{alea.choice(PREFIXES)}{alea.randrange(10**6, 10**7)}",
        "type": alea.choices(TYPES, weights=(5, 4, 1))[0],
        "sens": alea.choice(("débarquement", "embarquement")),
        "heure": h.isoformat(),
        "statut": alea.choices(STATUTS, weights=(6, 3, 1))[0],
    } for h in heures]


def generer() -> dict:
    return {"mouvements": {e.escale_id: _mouvements(e, NOMBRES[e.escale_id]) for e in corpus.charger().escales}}


def ecrire(chemin: Path = FICHIER) -> None:
    entete = "# Généré par « python -m donnees.legacy.mouvements » — ne pas modifier à la main.\n"
    chemin.write_text(entete + yaml.safe_dump(generer(), allow_unicode=True, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    ecrire()
