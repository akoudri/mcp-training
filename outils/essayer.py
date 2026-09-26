"""Essaie un état de lab dans Docker, comme la CI (job « solutions »).

Assemble l'état (branches préfixées essai/), l'extrait dans une copie de travail temporaire,
démarre ses services, lance « make labN-verifier SANS_MODELE=1 », puis arrête tout.
Utilise l'état COMMITÉ de --ref (HEAD par défaut). Attention : arrête la pile Compose « pharos ».
Usage : python3 -m outils.essayer N [--ref REF]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from outils.construire_etats import construire
from outils.labs import DEMARRAGE, PORTS_PRETS, SORTIES


def attendre(ports: list[int], delai: int = 90) -> None:
    """Attend que chaque port réponde via l'observateur (tout code < 500 : le serveur est là)."""
    fin = time.monotonic() + delai
    for port in ports:
        while True:
            requete = urllib.request.Request(f"http://127.0.0.1:{port}/mcp", data=b"{}", method="POST",
                                             headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(requete, timeout=3)
                break
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    break
            except (urllib.error.URLError, OSError):
                pass
            if time.monotonic() > fin:
                raise TimeoutError(f"port {port} : pas de réponse après {delai} s")
            time.sleep(1)


def essayer(racine: Path, lab: int, ref: str = "HEAD") -> int:
    if lab not in DEMARRAGE:
        print(f"LAB {lab} : aucun démarrage défini dans outils/labs.py.")
        return 2
    print("\n".join(construire(racine, base=ref, solutions=ref, labs=[lab], prefixe="essai/")))
    dossier = Path(tempfile.mkdtemp(prefix=f"pharos-essai-lab{lab}-")) / "pharos-labs"
    subprocess.run(["git", "worktree", "add", "--quiet", "--detach", str(dossier), f"essai/etat/{SORTIES[lab]}"],
                   cwd=racine, check=True)
    try:
        for cible in ["up", *DEMARRAGE[lab]]:
            subprocess.run(["make", "--no-print-directory", cible], cwd=dossier, check=True)
        attendre(PORTS_PRETS[lab])
        return subprocess.run(["make", "--no-print-directory", f"lab{lab}-verifier", "SANS_MODELE=1"],
                              cwd=dossier).returncode
    finally:
        subprocess.run(["make", "--no-print-directory", "down"], cwd=dossier)
        subprocess.run(["git", "worktree", "remove", "--force", str(dossier)], cwd=racine)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="make essayer")
    p.add_argument("lab", type=int)
    p.add_argument("--ref", default="HEAD")
    a = p.parse_args(argv)
    racine = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                                 check=True).stdout.strip())
    return essayer(racine, a.lab, a.ref)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
