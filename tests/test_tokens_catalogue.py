from pathlib import Path

import pytest

from labs.lab0.serveur.serveur import creer_serveur
from outils import tokens_catalogue


@pytest.fixture(autouse=True)
def corpus(monkeypatch):
    monkeypatch.setenv("PHAROS_DOCUMENTS", str(Path("donnees/documents").resolve()))


async def test_mesure_des_trois_outils():
    mesures = await tokens_catalogue.mesurer_serveur(creer_serveur())
    assert {m.nom for m in mesures} == {"lister_documents", "lire_document", "rechercher_clause"}
    for m in mesures:
        assert m.total > m.description > 0
        assert m.proprietes > 0
    clause = next(m for m in mesures if m.nom == "rechercher_clause")
    assert clause.enums > 0


async def test_le_jumeau_augmente_le_total():
    sans = sum(m.total for m in await tokens_catalogue.mesurer_serveur(creer_serveur()))
    avec = sum(m.total for m in await tokens_catalogue.mesurer_serveur(creer_serveur(outil_jumeau=True)))
    assert avec > sans


async def test_formatage_annonce_une_approximation():
    texte = tokens_catalogue.formater(await tokens_catalogue.mesurer_serveur(creer_serveur()))
    assert "approximation" in texte and "Total" in texte and "rechercher_clause" in texte
