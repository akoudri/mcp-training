"""make depart LAB=N — commence un lab.

Crée la branche binome-<B>-lab<NN> depuis le checkpoint de départ (origin/etat/…), puis copie les
gabarits du lab sans jamais écraser un fichier existant. Lancé sur le poste : il manipule git.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from outils.labs import DEPARTS, copier_gabarits


class Refus(Exception):
    """Départ refusé ; le message dit quoi faire."""


def _git(racine: Path, *args: str, verifier: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=racine, capture_output=True, text=True, check=verifier)


def lire_binome(racine: Path) -> str:
    env = racine / ".env"
    if env.exists():
        for ligne in env.read_text(encoding="utf-8").splitlines():
            cle, _, valeur = ligne.partition("=")
            if cle.strip() == "PHAROS_BINOME" and valeur.strip().isdigit():
                return valeur.strip()
    raise Refus("PHAROS_BINOME absent de .env : copier dans .env le fichier binome-N.env remis par le formateur "
                "(voir PREPARATION.md).")


def _verifier_propre(racine: Path) -> None:
    etat = _git(racine, "status", "--porcelain").stdout.rstrip()
    if etat:
        details = "\n".join(f"    {ligne}" for ligne in etat.splitlines())
        raise Refus("des modifications ne sont pas commitées :\n" + details +
                    "\nLes enregistrer d'abord :  git add -A && git commit -m \"LAB … — …\"")


def _messages_gabarits(lab: int, copies: list[Path], laisses: list[Path]) -> list[str]:
    messages = [f"Gabarit copié : {p}" for p in copies]
    messages += [f"Gabarit laissé tel quel (le fichier existe déjà) : {p}" for p in laisses]
    return messages or [f"LAB {lab} : aucun gabarit à copier."]


def gabarits(racine: Path, lab: int) -> list[str]:
    return _messages_gabarits(lab, *copier_gabarits(racine, lab))


def depart(racine: Path, lab: int, distant: str = "origin") -> list[str]:
    if lab not in DEPARTS:
        raise Refus(f"LAB {lab} : pas de départ défini (labs : {', '.join(map(str, sorted(DEPARTS)))}).")
    _verifier_propre(racine)
    binome = lire_binome(racine)
    messages: list[str] = []
    if distant in _git(racine, "remote").stdout.split():
        r = _git(racine, "fetch", "--quiet", distant, verifier=False)
        if r.returncode:
            messages.append(f"git fetch {distant} a échoué ({r.stderr.strip()}) : départ depuis les références locales.")
    branche = f"binome-{binome}-lab{lab:02d}"
    source = f"{distant}/etat/{DEPARTS[lab]}"
    if _git(racine, "rev-parse", "--verify", "--quiet", f"refs/heads/{branche}", verifier=False).returncode == 0:
        _git(racine, "switch", "--quiet", branche)
        messages.append(f"La branche {branche} existe déjà : on s'y place, rien n'est écrasé.")
    else:
        if _git(racine, "rev-parse", "--verify", "--quiet", source, verifier=False).returncode:
            raise Refus(f"le checkpoint {source} est introuvable : vérifier l'accès au dépôt (git fetch {distant}), "
                        "ou prévenir le formateur.")
        _git(racine, "switch", "--quiet", "--no-track", "-c", branche, source)
        messages.append(f"Branche {branche} créée depuis {source}.")
    messages += gabarits(racine, lab)
    messages.append(f"Cibles du LAB {lab} : make aide | grep 'LAB {lab} '")
    return messages


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="make depart")
    p.add_argument("lab", type=int)
    p.add_argument("--gabarits-seulement", action="store_true")
    a = p.parse_args(argv)
    racine = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())
    try:
        messages = gabarits(racine, a.lab) if a.gabarits_seulement else depart(racine, a.lab)
    except Refus as refus:
        print(f"Départ refusé : {refus}")
        return 1
    print("\n".join(messages))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
