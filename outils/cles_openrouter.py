"""Clés OpenRouter des binômes : une clé plafonnée par binôme, créée et révoquée par le formateur.

Usage :
  OPENROUTER_CLE_GESTION=… python -m outils.cles_openrouter creer --binomes 5 --plafond 5 --expiration 2026-10-10
  OPENROUTER_CLE_GESTION=… python -m outils.cles_openrouter etat
  OPENROUTER_CLE_GESTION=… python -m outils.cles_openrouter revoquer
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import httpx

API = "https://openrouter.ai/api/v1"
PREFIXE = "pharos-binome-"


def creer(client: httpx.Client, binomes: int, plafond: float, expiration: date, sortie: Path) -> list[Path]:
    sortie.mkdir(parents=True, exist_ok=True)
    chemins = []
    for n in range(1, binomes + 1):
        r = client.post("/keys", json={"name": f"{PREFIXE}{n}", "limit": plafond,
                                       "expires_at": f"{expiration.isoformat()}T23:59:59Z"})
        r.raise_for_status()
        chemin = sortie / f"binome-{n}.env"
        chemin.write_text(f"OPENROUTER_API_KEY={r.json()['key']}\nPHAROS_MODELE=google/gemini-3.6-flash\nPHAROS_BINOME={n}\n",
                          encoding="utf-8")
        chemin.chmod(0o600)
        chemins.append(chemin)
    return chemins


def _cles_pharos(client: httpx.Client) -> list[dict]:
    r = client.get("/keys")
    r.raise_for_status()
    return [c for c in r.json()["data"] if c.get("name", "").startswith(PREFIXE)]


def revoquer(client: httpx.Client) -> int:
    cles = _cles_pharos(client)
    for c in cles:
        client.delete(f"/keys/{c['hash']}").raise_for_status()
    return len(cles)


def etat(client: httpx.Client) -> list[dict]:
    return [{"nom": c["name"], "plafond": c.get("limit"), "consomme": c.get("usage")} for c in _cles_pharos(client)]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="cles_openrouter")
    sous = p.add_subparsers(dest="commande", required=True)
    c = sous.add_parser("creer")
    c.add_argument("--binomes", type=int, default=5)
    c.add_argument("--plafond", type=float, default=5.0)
    c.add_argument("--expiration", type=date.fromisoformat, required=True)
    c.add_argument("--sortie", type=Path, default=Path("sortie"))
    sous.add_parser("etat")
    sous.add_parser("revoquer")
    args = p.parse_args(argv)
    cle = os.environ.get("OPENROUTER_CLE_GESTION")
    if not cle:
        print("OPENROUTER_CLE_GESTION absente.", file=sys.stderr)
        return 2
    with httpx.Client(base_url=API, headers={"Authorization": f"Bearer {cle}"}, timeout=30) as client:
        if args.commande == "creer":
            for chemin in creer(client, args.binomes, args.plafond, args.expiration, args.sortie):
                print(chemin)
        elif args.commande == "etat":
            for ligne in etat(client):
                print(f"{ligne['nom']:<20} consommé {ligne['consomme']} / plafond {ligne['plafond']}")
        else:
            print(f"{revoquer(client)} clé(s) révoquée(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
