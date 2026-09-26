import pytest

from pharos import jetons
from pharos_docs import jetons as jetons_docs

CLE = "cle-de-test"


def test_aller_retour():
    j = jetons.signer({"e": "ESC-2026-0412", "d": "CM-0412"}, CLE)
    assert j.startswith("hdl_") and len(j) < 120
    assert jetons.verifier(j, CLE) == {"e": "ESC-2026-0412", "d": "CM-0412"}


def test_charge_lisible_mais_signee():
    j = jetons.signer({"e": "ESC-2026-0412"}, CLE, duree_s=900)
    charge = jetons.lire_charge(j)
    assert charge["e"] == "ESC-2026-0412" and isinstance(charge["exp"], int)


@pytest.mark.parametrize("position", [6, -3])   # dans la charge, puis dans la signature
def test_un_caractere_altere_est_refuse(position):
    j = jetons.signer({"e": "ESC-2026-0412"}, CLE)
    i = position % len(j)
    altere = j[:i] + ("A" if j[i] != "A" else "B") + j[i + 1:]
    with pytest.raises(jetons.JetonAltere):
        jetons.verifier(altere, CLE)


def test_autre_cle_refusee():
    j = jetons.signer({"e": "ESC-2026-0412"}, "une-autre-cle")
    with pytest.raises(jetons.JetonAltere):
        jetons.verifier(j, CLE)


def test_expire():
    j = jetons.signer({"e": "ESC-2026-0412"}, CLE, duree_s=-1)
    with pytest.raises(jetons.JetonExpire):
        jetons.verifier(j, CLE)


def test_expiration_suit_l_horloge(monkeypatch):
    j = jetons.signer({"e": "x"}, CLE, duree_s=5)
    instant = jetons.lire_charge(j)["exp"]
    monkeypatch.setattr(jetons, "_maintenant", lambda: instant + 1)
    with pytest.raises(jetons.JetonExpire):
        jetons.verifier(j, CLE)


def test_verifier_tolere_les_blancs():
    j = jetons.signer({"e": "ESC-2026-0412"}, CLE)
    assert jetons.verifier(f"  {j}\n", CLE) == {"e": "ESC-2026-0412"}


@pytest.mark.parametrize("brut", ["", "abc", "hdl_", "hdl_abc", "hdl_a.b.c", "tok_abc.def", None, 42])
def test_formats_invalides(brut):
    with pytest.raises(jetons.JetonAltere):
        jetons.verifier(brut, CLE)


def test_exp_reserve():
    with pytest.raises(ValueError, match="exp"):
        jetons.signer({"exp": 1}, CLE)


def test_cle_vide_refusee():
    with pytest.raises(ValueError):
        jetons.signer({"e": "x"}, "")


def test_hierarchie_et_reexport():
    assert issubclass(jetons.JetonAltere, jetons.JetonInvalide)
    assert issubclass(jetons.JetonExpire, jetons.JetonInvalide)
    assert jetons_docs.signer is jetons.signer and jetons_docs.JetonInvalide is jetons.JetonInvalide
