"""Empreintes du contexte d'évaluation (LAB 15) : catalogue, prompt, modèle — et la base (rechargée deux fois)."""

from pathlib import Path
from types import SimpleNamespace

from pharos import empreintes
from tests.aides import DSN_TEST, base_requise


def test_empreintes_de_catalogue_de_prompt_et_de_modele(tmp_path, monkeypatch):
    outil = lambda nom, d="": {"name": nom, "description": d, "inputSchema": {"type": "object"}}   # noqa: E731
    a = empreintes.empreinte_catalogue({"x": [outil("b"), outil("a")], "y": [outil("c")]})
    assert a == empreintes.empreinte_catalogue({"y": [outil("c")], "x": [outil("a"), outil("b")]}) and len(a) == 16
    assert a != empreintes.empreinte_catalogue({"x": [outil("b"), outil("resoudre")], "y": [outil("c")]})
    assert a != empreintes.empreinte_catalogue({"x": [outil("b"), outil("a", "autre")], "y": [outil("c")]})
    objet = SimpleNamespace(name="a", description="", input_schema={"type": "object"})
    assert empreintes.empreinte_catalogue({"x": [objet]}) == empreintes.empreinte_catalogue({"x": [outil("a")]})
    p = tmp_path / "consigne.md"
    p.write_text("Tu es…", encoding="utf-8")
    e = empreintes.empreinte_prompt(p)
    p.write_text("Tu es… !", encoding="utf-8")
    assert e != empreintes.empreinte_prompt(p)
    monkeypatch.setenv("PHAROS_MODELE", "mistralai/mistral-small-4")
    assert empreintes.empreinte_modele() == "mistralai/mistral-small-4"
    monkeypatch.delenv("PHAROS_MODELE")
    assert empreintes.empreinte_modele() == "google/gemini-3.6-flash"


@base_requise
async def test_l_empreinte_de_la_base_est_stable_et_suit_les_lignes(base_de_test):
    import asyncpg

    from donnees.base.__main__ import charger

    premiere = await empreintes.empreinte_base(DSN_TEST)
    await charger(DSN_TEST, politique=Path("/nulle-part.sql"))
    assert await empreintes.empreinte_base(DSN_TEST) == premiere and len(premiere) == 16
    connexion = await asyncpg.connect(DSN_TEST)
    try:
        await connexion.execute("UPDATE navires SET longueur_m = longueur_m + 1 WHERE navire_id = 'NAV-0007'")
    finally:
        await connexion.close()
    try:
        assert await empreintes.empreinte_base(DSN_TEST) != premiere
    finally:
        await charger(DSN_TEST, politique=Path("/nulle-part.sql"))
