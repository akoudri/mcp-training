"""python -m outils.verifier labN [--url URL] — lancé par make labN-verifier."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="make labN-verifier")
    p.add_argument("lab")
    p.add_argument("--url")
    a = p.parse_args(argv)
    nom = f"outils.verifier.{a.lab}"
    try:
        module = importlib.import_module(nom)
    except ModuleNotFoundError as exc:
        if exc.name != nom:
            raise
        print(f"Aucun vérificateur pour « {a.lab} ».")
        return 2
    rapport = asyncio.run(module.v.executer(url=a.url))
    print(rapport.texte())
    return rapport.code_sortie


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
