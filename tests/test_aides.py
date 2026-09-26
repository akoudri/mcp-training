"""Tests des aides partagées — en particulier, que la copie d'arbre n'embarque jamais .env."""

from tests.aides import etat_complet


def test_etat_complet_ne_copie_pas_env(tmp_path):
    destination = tmp_path / "e"
    etat_complet(destination, 1)
    assert not (destination / ".env").exists()
    assert not [p for p in destination.rglob("*") if p.name == ".env"]


def test_marqueur_origine_sans_importer_le_serveur(tmp_path, monkeypatch):
    from tests import aides
    serveur = tmp_path / "serveurs" / "pharos_legacy" / "serveur.py"
    serveur.parent.mkdir(parents=True)
    monkeypatch.setattr(aides, "RACINE_KIT", tmp_path)
    serveur.write_text('REVISION = "2025-11-25"\ndef (:\n', encoding="utf-8")     # syntaxe cassée
    assert aides.serveur_legacy_d_origine() is True
    serveur.write_text('REVISION = "2026-07-28"\n', encoding="utf-8")
    assert aides.serveur_legacy_d_origine() is False
    serveur.unlink()
    assert aides.serveur_legacy_d_origine() is False
