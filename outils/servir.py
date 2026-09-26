"""Sert une application ASGI dans un fil du processus courant (tests du kit, vérificateur du LAB 3)."""

from __future__ import annotations

import contextlib
import socket
import threading
import time

import uvicorn


@contextlib.contextmanager
def servir(app):
    """Sert « app » sur un port libre de 127.0.0.1 ; rend son URL de base, arrête le serveur à la sortie."""
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
