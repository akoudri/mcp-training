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


@pytest.fixture
def mocks_servis(tmp_path, monkeypatch):
    """Les mocks (LAB 10 et suivants), neufs, servis dans le processus ; outils.lab10 et les serveurs les visent. Rend l'URL."""
    from outils import lab10
    from outils.servir import servir
    from serveurs.mocks import app as mocks

    monkeypatch.setattr(mocks, "etat", mocks.Etat())
    with servir(mocks.app) as url:
        monkeypatch.setattr(lab10, "URL_MOCKS", url)
        monkeypatch.setenv("METEO_URL", f"{url}/meteo")
        monkeypatch.setenv("REFERENTIEL_URL", f"{url}/referentiel")
        monkeypatch.setenv("METEO_CLE", "meteo-salle-2026")        # un vérificateur la remplace : restaurée ici
        monkeypatch.setenv("PHAROS_LOGS", str(tmp_path / "logs"))
        yield url
