"""Aides partagées par les tests du kit."""

from __future__ import annotations

import contextlib
import importlib.util
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from outils.construire_etats import superposer

RACINE_KIT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def servir(app):
    """Sert une application ASGI dans un fil ; rend son URL de base."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    serveur = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"))
    fil = threading.Thread(target=serveur.run, daemon=True)
    fil.start()
    limite = time.monotonic() + 10
    while not serveur.started:
        if time.monotonic() > limite:
            raise RuntimeError("le serveur de test n'a pas démarré")
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        serveur.should_exit = True
        fil.join(10)


def charger_module(chemin: Path, nom: str):
    """Importe un fichier Python sous un nom unique (gabarits et solutions ne sont pas des paquets du kit)."""
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


def _purger(prefixe: str) -> None:
    for nom in [n for n in sys.modules if n == prefixe or n.startswith(prefixe + ".")]:
        del sys.modules[nom]


@contextlib.contextmanager
def importer_paquet(dossier: Path, *paquets: str):
    """Rend importables, depuis « dossier », les paquets nommés (purgés de sys.modules avant et après)."""
    for paquet in paquets:
        _purger(paquet)
    sys.path.insert(0, str(dossier))
    try:
        yield
    finally:
        sys.path.remove(str(dossier))
        for paquet in paquets:
            _purger(paquet)


def importer_client(dossier: Path):
    """Rend importable le paquet pharos_client situé dans « dossier »."""
    return importer_paquet(dossier, "pharos_client")


def serveur_demo() -> FastMCP:
    mcp = FastMCP("demo")

    @mcp.tool
    def etat(escale_id: str) -> dict:
        """Donne l'état d'une escale."""
        if escale_id != "ESC-2026-0412":
            raise ToolError("Escale inconnue.")
        return {"escale_id": escale_id, "quai": 3}

    @mcp.tool
    def echec() -> dict:
        """Échoue toujours."""
        raise RuntimeError("panne interne")

    return mcp


def etat_complet(destination: Path, lab: int) -> Path:
    """Copie du kit (comme une branche etat/*) avec gabarits et solutions superposés jusqu'au lab."""
    shutil.copytree(RACINE_KIT, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns(
        ".git", ".venv", "solutions", "__pycache__", ".pytest_cache", "logs", "sortie", ".superpowers"))
    superposer(destination, RACINE_KIT / "gabarits", RACINE_KIT / "solutions", lab)
    return destination
