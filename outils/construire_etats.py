"""make construire-etats — assemble les branches etat/<checkpoint> (poste du formateur, et CI).

etat/<sortie du lab N> = base, puis pour k = 1..N : gabarits du lab k (sans écraser), puis
instantané solutions/labkk (en écrasant) ; le dossier solutions/ est retiré. Un seul commit
par état, dont le parent est la base. etat/fa2-fin n'est jamais touché.
Bibliothèque standard uniquement : lancé par python3 sur le poste.
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from outils.labs import SORTIES, copier, nom_dossier

IDENTITE = ["-c", "user.name=pharos-kit", "-c", "user.email=kit@pharos.invalid"]


class Refus(Exception):
    """Assemblage refusé ; le message dit pourquoi."""


def _git(racine: Path, *args: str, verifier: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=racine, capture_output=True, text=True, check=verifier)


def superposer(destination: Path, gabarits: Path, solutions: Path | None, lab: int) -> list[str]:
    notes = []
    for k in range(1, lab + 1):
        copier(gabarits / nom_dossier(k), destination, ecraser=False)
        instantane = solutions / nom_dossier(k) if solutions else None
        if instantane is not None and instantane.is_dir():
            copier(instantane, destination, ecraser=True)
        else:
            notes.append(f"LAB {k} : pas d'instantané de solution — gabarits seuls.")
    return notes


def _extraire_solutions(racine: Path, ref: str, destination: Path) -> Path | None:
    if not _git(racine, "ls-tree", "-d", ref, "solutions").stdout.strip():
        return None
    archive = subprocess.run(["git", "archive", ref, "solutions"], cwd=racine, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")
    return destination / "solutions"


def construire(racine: Path, base: str = "main", solutions: str = "solutions", labs=None, prefixe: str = "",
               pousser: bool = False, distant: str = "origin") -> list[str]:
    labs = sorted(labs or SORTIES)
    courante = _git(racine, "branch", "--show-current").stdout.strip()
    cibles = {n: f"{prefixe}etat/{SORTIES[n]}" for n in labs}
    if courante in cibles.values():
        raise Refus(f"la branche {courante} est extraite ici : changer de branche avant de la reconstruire.")
    if pousser and _git(racine, "status", "--porcelain").stdout.strip():
        raise Refus("des modifications ne sont pas commitées : les enregistrer avant de pousser des états.")
    base_sha = _git(racine, "rev-parse", f"{base}^{{commit}}").stdout.strip()
    messages = []
    with tempfile.TemporaryDirectory(prefix="pharos-etats-") as tmp:
        tmp = Path(tmp)
        source_solutions = _extraire_solutions(racine, solutions, tmp / "sol")
        arbre = tmp / "arbre"
        _git(racine, "worktree", "add", "--quiet", "--detach", str(arbre), base_sha)
        try:
            for n in labs:
                _git(arbre, "reset", "--quiet", "--hard", base_sha)
                _git(arbre, "clean", "-q", "-fdx")
                shutil.rmtree(arbre / "solutions", ignore_errors=True)
                notes = superposer(arbre, arbre / "gabarits", source_solutions, n)
                _git(arbre, "add", "-A")
                _git(arbre, *IDENTITE, "commit", "-q", "--allow-empty",
                     "-m", f"etat: {SORTIES[n]} (LAB {n})" + ("\n\n" + "\n".join(notes) if notes else ""))
                sha = _git(arbre, "rev-parse", "HEAD").stdout.strip()
                _git(racine, "branch", "-f", cibles[n], sha)
                messages.append(f"{cibles[n]} ← {sha[:7]} (LAB {n})" + (f" — {'; '.join(notes)}" if notes else ""))
                if pousser:
                    _git(racine, "push", "--quiet", "--force-with-lease", distant, f"{cibles[n]}:{cibles[n]}")
                    messages.append(f"  poussée vers {distant}")
        finally:
            _git(racine, "worktree", "remove", "--force", str(arbre), verifier=False)
            _git(racine, "worktree", "prune", verifier=False)
    return messages


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="make construire-etats")
    p.add_argument("--base", default="main")
    p.add_argument("--solutions", default="solutions")
    p.add_argument("--labs", help="liste séparée par des virgules, par défaut tous")
    p.add_argument("--prefixe", default="")
    p.add_argument("--pousser", action="store_true")
    a = p.parse_args(argv)
    racine = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())
    labs = [int(x) for x in a.labs.split(",")] if a.labs else None
    try:
        messages = construire(racine, a.base, a.solutions, labs, a.prefixe, a.pousser)
    except Refus as refus:
        print(f"Assemblage refusé : {refus}")
        return 1
    print("\n".join(messages))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
