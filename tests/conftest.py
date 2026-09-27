"""Fixtures partagées : la base PHAROS de test (rechargée une fois par session, sans politique)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.aides import DSN_TEST


@pytest.fixture(scope="session")
def base_de_test():
    """Recharge pharos-db depuis PHAROS_DSN_TEST ; oriente pharos.base.dsn() vers le même serveur. Rend les données."""
    if not DSN_TEST:
        pytest.skip("PHAROS_DSN_TEST absent")
    from donnees.base.__main__ import charger

    adresse = urlsplit(DSN_TEST)
    with pytest.MonkeyPatch.context() as m:
        m.setenv("PHAROS_DB_HOTE", adresse.hostname)
        m.setenv("PHAROS_DB_PORT", str(adresse.port or 5432))
        m.setenv("PHAROS_DB_MOT_DE_PASSE", adresse.password or "pharos-salle-2026")
        yield asyncio.run(charger(DSN_TEST, politique=Path("/nulle-part/politique.sql")))
