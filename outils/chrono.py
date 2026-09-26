"""python -m outils.chrono COMMANDE… — exécute la commande et affiche sa durée (make lab7-tests CHRONO=1)."""

from __future__ import annotations

import subprocess
import sys
import time

SEUIL_S = 10.0


def main(argv: list[str]) -> int:
    debut = time.perf_counter()
    code = subprocess.run(argv).returncode
    duree = time.perf_counter() - debut
    print(f"\nDurée : {duree:.2f} s ({'sous le' if duree < SEUIL_S else 'AU-DESSUS du'} seuil de {SEUIL_S:.0f} s)")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
