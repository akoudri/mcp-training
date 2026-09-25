import ast
from datetime import date
from pathlib import Path

from pharos import horloge

RACINE = Path(__file__).resolve().parents[1]


def test_aujourdhui_est_le_mardi_fictif(monkeypatch):
    monkeypatch.delenv("PHAROS_AUJOURDHUI", raising=False)
    assert horloge.aujourdhui() == date(2026, 10, 6)
    assert horloge.aujourdhui().isoweekday() == 2


def test_surcharge_par_variable(monkeypatch):
    monkeypatch.setenv("PHAROS_AUJOURDHUI", "2026-10-08")
    assert horloge.aujourdhui() == date(2026, 10, 8)


def test_maintenant_est_le_jour_fictif_a_paris(monkeypatch):
    monkeypatch.delenv("PHAROS_AUJOURDHUI", raising=False)
    m = horloge.maintenant()
    assert m.date() == date(2026, 10, 6)
    assert m.tzinfo is not None and m.utcoffset() is not None
    assert str(m.tzinfo) == "Europe/Paris"


def _appels_interdits(chemin: Path) -> list[str]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    trouves = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Attribute) and noeud.attr in {"today", "now", "utcnow"}:
            cible = noeud.value
            nom = cible.id if isinstance(cible, ast.Name) else getattr(cible, "attr", "")
            if nom in {"date", "datetime"}:
                trouves.append(f"{chemin.relative_to(RACINE)}:{noeud.lineno}")
    return trouves


def test_aucun_appel_direct_a_l_horloge_systeme():
    fichiers = [
        p for p in RACINE.rglob("*.py")
        if ".venv" not in p.parts and "tests" not in p.parts
        and p != RACINE / "src" / "pharos" / "horloge.py"
    ]
    fautifs = [f for p in fichiers for f in _appels_interdits(p)]
    assert fautifs == [], f"Utiliser pharos.horloge : {fautifs}"
