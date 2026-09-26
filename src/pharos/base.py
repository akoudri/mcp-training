"""Accès à la base PHAROS (service pharos-db) : une adresse par rôle, et l'attente du démarrage.

Les mots de passe sont des valeurs de salle (compose/commun/base.yaml), pas des secrets : la base
n'est publiée que sur 127.0.0.1:5433, et elle ne contient que des données fictives.
"""

from __future__ import annotations

import asyncio
import os

ROLES = ("pharos_proprietaire", "pharos_app", "pharos_planification")
ADMIN = "postgres"
BASE = "pharos"


def dsn(role: str = "pharos_app") -> str:
    """Adresse de connexion pour un rôle LOGIN (pharos_app, pharos_planification…) ou l'administrateur."""
    hote = os.environ.get("PHAROS_DB_HOTE", "pharos-db")
    port = os.environ.get("PHAROS_DB_PORT", "5432")
    mot_de_passe = os.environ.get("PHAROS_DB_MOT_DE_PASSE", "pharos-salle-2026")
    return f"postgresql://{role}:{mot_de_passe}@{hote}:{port}/{BASE}"


async def attendre(delai_s: float = 60) -> None:
    """Attend que la base accepte une connexion de l'administrateur ; lève TimeoutError sinon."""
    import asyncpg

    fin = asyncio.get_running_loop().time() + delai_s
    while True:
        try:
            connexion = await asyncpg.connect(dsn(ADMIN), timeout=3)
        except (OSError, asyncpg.PostgresError, asyncio.TimeoutError):
            if asyncio.get_running_loop().time() > fin:
                raise TimeoutError(f"pharos-db ne répond pas après {delai_s:.0f} s : lancer « make lab8-base ».")
            await asyncio.sleep(1)
        else:
            await connexion.close()
            return
