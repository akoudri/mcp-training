"""Table des labs du fil documentaire : checkpoints, démarrage, gabarits.

Bibliothèque standard uniquement : ce module est lancé par python3 sur le poste, sans .venv.
"""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

DEPARTS = {1: "fa2-fin", 2: "pr2-fin", 3: "pr3-fin", 4: "pr5-fin", 5: "or1-fin", 6: "or2-fin", 7: "sr1-fin"}
SORTIES = {1: "pr2-fin", 2: "pr3-fin", 3: "pr5-fin", 4: "or1-fin", 5: "or2-fin", 6: "sr1-fin", 7: "tq1-fin"}
# Cibles make qui démarrent les services d'un lab, et ports à attendre (via l'observateur).
DEMARRAGE: dict[int, list[str]] = {}
PORTS_PRETS: dict[int, list[int]] = {}
IGNORES = {"__pycache__", ".pytest_cache"}


def nom_dossier(lab: int) -> str:
    return f"lab{lab:02d}"


def _fichiers(dossier: Path) -> list[Path]:
    return sorted(f for f in dossier.rglob("*")
                  if f.is_file() and f.suffix != ".pyc" and not IGNORES & set(f.relative_to(dossier).parts))


def copier(source: Path, destination: Path, ecraser: bool) -> tuple[list[Path], list[Path]]:
    """Copie l'arbre source dans destination ; rend (copiés, laissés tels quels), en chemins relatifs.

    Sans écrasement, un fichier déjà présent et identique n'est ni copié ni signalé ; présent et
    différent, il est laissé tel quel et signalé (c'est le travail du binôme)."""
    copies: list[Path] = []
    laisses: list[Path] = []
    if not source.is_dir():
        return copies, laisses
    for f in _fichiers(source):
        relatif = f.relative_to(source)
        cible = destination / relatif
        if cible.exists() and not ecraser:
            if not filecmp.cmp(f, cible, shallow=False):
                laisses.append(relatif)
            continue
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, cible)
        copies.append(relatif)
    return copies, laisses


def copier_gabarits(racine: Path, lab: int, destination: Path | None = None) -> tuple[list[Path], list[Path]]:
    return copier(racine / "gabarits" / nom_dossier(lab), destination or racine, ecraser=False)
