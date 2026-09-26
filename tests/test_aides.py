"""Tests des aides partagées — en particulier, que la copie d'arbre n'embarque jamais .env."""

from tests.aides import etat_complet


def test_etat_complet_ne_copie_pas_env(tmp_path):
    destination = tmp_path / "e"
    etat_complet(destination, 1)
    assert not (destination / ".env").exists()
    assert not [p for p in destination.rglob("*") if p.name == ".env"]
